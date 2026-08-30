"""Health and readiness endpoints.

``/health`` is a liveness probe and must stay trivial. ``/system/readiness``
reports each subsystem separately so the frontend can show precise indicators
instead of failing wholesale when one component is missing.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.config import settings
from app.core import diagnostics, storage
from app.schemas.report import HealthResponse, ReadinessResponse
from app.services import prediction_service, protein_service, simulation_service
from app.utils.serialization import utc_now_iso

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse, summary="Liveness probe")
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        version=settings.version,
        time_utc=utc_now_iso(),
    )


@router.get(
    "/system/readiness",
    response_model=ReadinessResponse,
    summary="Per-subsystem readiness",
)
def readiness() -> ReadinessResponse:
    components = []

    # --- ML model -------------------------------------------------------
    model = prediction_service.model_info()
    components.append(
        {
            "name": "ml_model",
            "ready": bool(model["available"]),
            "status": model["status"],
            "version": model.get("model_version"),
            "detail": (
                f"{model.get('model_name') or 'Model'} {model.get('model_version')} "
                f"({model.get('scientific_status')}); "
                f"integrity {'verified' if model.get('sha256_verified') else 'UNVERIFIED'}."
                if model["available"]
                else (model.get("load_error") or "Model bundle could not be loaded.")
            ),
            "remediation": (
                None
                if model["available"]
                else "Confirm models/bionano_mock_model_bundle.pkl exists, then run "
                     "python scripts/validate_model.py"
            ),
        }
    )

    # --- Simulation engine ----------------------------------------------
    engine = simulation_service.engine_health()
    openmm = engine["openmm"]
    components.append(
        {
            "name": "simulation_engine",
            "ready": bool(openmm["available"]),
            "status": "ready" if openmm["available"] else "unavailable",
            "version": openmm.get("version"),
            "detail": openmm["detail"],
            "remediation": openmm.get("remediation"),
        }
    )
    mdtraj = engine["mdtraj"]
    components.append(
        {
            "name": "trajectory_analysis",
            "ready": True,  # a fallback reader always exists
            "status": "ready" if mdtraj["available"] else "degraded",
            "version": mdtraj.get("version"),
            "detail": mdtraj["detail"],
            "remediation": None if mdtraj["available"] else "pip install mdtraj==1.11.1.post2",
        }
    )

    # --- Protein registry -----------------------------------------------
    proteins = protein_service.list_proteins()
    missing = []
    for record in proteins:
        try:
            protein_service.structure_path(record["pdb_id"])
        except Exception:  # noqa: BLE001
            missing.append(record["pdb_id"])
    components.append(
        {
            "name": "protein_registry",
            "ready": bool(proteins) and not missing,
            "status": "ready" if proteins and not missing else ("degraded" if proteins else "unavailable"),
            "detail": (
                f"{len(proteins)} approved proteins registered"
                + (f"; missing structure files: {', '.join(missing)}" if missing else ".")
            ),
            "remediation": "python scripts/setup_local.py" if missing else None,
        }
    )

    # --- Scenarios ------------------------------------------------------
    scenarios = prediction_service.list_scenarios()
    ml_supported = [s for s in scenarios if s.get("ml_supported")]
    components.append(
        {
            "name": "scenarios",
            "ready": bool(scenarios),
            "status": "ready" if scenarios else "unavailable",
            "detail": (
                f"{len(scenarios)} presets ({len(ml_supported)} with ML support). "
                "Values are configurable demonstration presets, not authoritative "
                "mission data."
            ),
            "remediation": None if scenarios else "Restore data/scenarios/radiation_scenarios.json",
        }
    )

    # --- Runtime storage ------------------------------------------------
    try:
        settings.ensure_runtime_dirs()
        writable = True
        detail = f"Job/upload/report directories writable under {settings.runtime_dir}."
    except OSError as exc:
        writable = False
        detail = f"Runtime directory is not writable: {exc}"
    components.append(
        {
            "name": "runtime_storage",
            "ready": writable,
            "status": "ready" if writable else "unavailable",
            "detail": detail,
            "remediation": None if writable else "Check filesystem permissions on runtime/.",
        }
    )

    # --- Precomputed fallback -------------------------------------------
    precomputed = simulation_service.precomputed_available()
    components.append(
        {
            "name": "precomputed_fallback",
            "ready": bool(precomputed),
            "status": "ready" if precomputed else "degraded",
            "detail": (
                f"Precomputed results available for: {', '.join(precomputed)}."
                if precomputed
                else "No precomputed results are bundled, so there is no fallback if a "
                     "live run fails."
            ),
            "remediation": (
                None if precomputed
                else "python scripts/run_demo_simulation.py --write-precomputed 1UBQ"
            ),
        }
    )

    jobs = simulation_service.job_list(limit=1000)
    counts = {
        "approved_proteins": len(proteins),
        "scenarios": len(scenarios),
        "ml_supported_scenarios": len(ml_supported),
        "total_jobs": len(jobs),
        "completed_jobs": sum(1 for j in jobs if j.get("status") == "completed"),
        "failed_jobs": sum(1 for j in jobs if j.get("status") == "failed"),
        "active_jobs": len(engine["active_jobs"]),
        "presets": len(simulation_service.presets()),
    }

    # Core readiness excludes the optional fallback and the degradable analyser.
    core = {"ml_model", "simulation_engine", "protein_registry", "scenarios", "runtime_storage"}
    ready = all(c["ready"] for c in components if c["name"] in core)
    degraded = any(c["status"] == "degraded" for c in components)

    return ReadinessResponse(
        ready=ready,
        status="ready" if ready and not degraded else ("degraded" if ready else "not_ready"),
        time_utc=utc_now_iso(),
        components=components,
        counts=counts,
    )


@router.get(
    "/system/storage",
    summary="Runtime storage usage, quota and cleanup pressure",
)
def system_storage() -> dict:
    """Where runtime/ space has gone, and whether cleanup is needed."""
    return storage.storage_report().as_dict()


@router.get(
    "/system/diagnostics",
    summary="One-shot diagnostics for a failed demo",
)
def system_diagnostics() -> dict:
    """Job outcomes, stage timings, engine platform, storage and logs.

    Everything a teammate needs to diagnose a failed run without opening four
    runtime directories. Uploaded structures and absolute paths are redacted,
    so the output is safe to paste into an issue.
    """
    return diagnostics.collect()


@router.get(
    "/system/support-bundle",
    summary="Diagnostics packaged for sharing, with omissions stated",
)
def system_support_bundle(include_uploads: bool = False) -> dict:
    """``include_uploads`` counts uploaded structures; it never embeds them."""
    return diagnostics.support_bundle(include_uploads=include_uploads)


@router.get(
    "/system/cleanup/preview",
    summary="What cleanup would delete, without deleting it",
)
def system_cleanup_preview() -> dict:
    """Always a dry run. Deletion is not exposed over the API on purpose.

    Removing a teammate's results should take a deliberate command on the
    machine that holds them, not an HTTP GET that a browser could prefetch.
    Use ``python scripts/cleanup_runtime.py --apply``.
    """
    candidates = storage.cleanup_candidates()
    result = storage.run_cleanup(candidates, dry_run=True)
    result["how_to_apply"] = "python scripts/cleanup_runtime.py --apply"
    return result
