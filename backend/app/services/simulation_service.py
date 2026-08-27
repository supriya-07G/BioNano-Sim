"""Simulation orchestration: submit, poll, assemble results, precomputed fallback."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.analysis.degradation import PROXY_CAVEATS
from app.config import settings
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.schemas.simulation import JobStatus
from app.services import prediction_service, protein_service
from app.simulation.job_manager import get_job_manager
from app.simulation.presets import get_preset, list_presets
from app.simulation.validators import (
    mdtraj_availability,
    openmm_availability,
    require_openmm,
    validate_simulation_request,
)
from app.utils.files import read_json

logger = get_logger("bionano.services.simulation")

RESULT_LABELS = {
    "openmm": "Rapid OpenMM Simulation",
    "precomputed": "Precomputed OpenMM Result",
    "ml_only": "ML Prediction",
    "visualization": "Visualization Estimate",
    "production": "Production Simulation — Future Scope",
}


def presets() -> list[dict[str, Any]]:
    return list_presets()


def engine_health() -> dict[str, Any]:
    openmm = openmm_availability()
    mdtraj = mdtraj_availability()
    manager = get_job_manager()
    return {
        "openmm": openmm,
        "mdtraj": mdtraj,
        "max_concurrent_jobs": settings.max_concurrent_jobs,
        "active_jobs": manager.active_job_ids(),
        "trajectory_analysis": (
            f"MDTraj {mdtraj['version']}" if mdtraj["available"]
            else "BioNano-Sim built-in DCD reader"
        ),
    }


def submit_simulation(request: Any) -> dict[str, Any]:
    """Validate everything, then hand off to a worker thread."""
    require_openmm()
    source_pdb, identifier, kind = protein_service.resolve_structure(
        request.pdb_id, request.upload_id
    )
    scenario = prediction_service.get_scenario(request.scenario_id)
    structure_info, warnings = validate_simulation_request(request, source_pdb)

    preset = get_preset(request.preset_id)
    warnings = [
        *warnings,
        f"Results from this run must be labelled '{preset.scientific_label}'.",
        *preset.limitations,
    ]

    manager = get_job_manager()
    job_id = manager.submit(
        request=request,
        source_pdb=source_pdb,
        structure_info={**structure_info, "kind": kind, "identifier": identifier},
        scenario=scenario,
        validation_warnings=warnings,
    )
    return manager.detail(job_id)


def job_detail(job_id: str) -> dict[str, Any]:
    return get_job_manager().detail(job_id)


def job_list(limit: int = 100) -> list[dict[str, Any]]:
    return get_job_manager().list_jobs(limit=limit)


def cancel_job(job_id: str) -> dict[str, Any]:
    return get_job_manager().cancel(job_id)


def delete_job(job_id: str) -> None:
    get_job_manager().delete(job_id)


def _comparison_block(
    ml_percent: float | None, proxy_percent: float | None
) -> dict[str, Any]:
    """Build the ML-vs-simulation comparison, with its interpretation limits."""
    block: dict[str, Any] = {
        "ml_degradation_percent": (
            round(ml_percent, 4) if ml_percent is not None else None
        ),
        "ml_label": RESULT_LABELS["ml_only"],
        "simulation_degradation_proxy_percent": (
            round(proxy_percent, 4) if proxy_percent is not None else None
        ),
        "simulation_label": "Simulation-derived degradation proxy",
        "difference_percentage_points": None,
        "agreement": "unavailable",
        "interpretation": (
            "These two numbers are different quantities. The ML value is a "
            "mock-model estimate of per-residue side-chain-loss degradation, "
            "aggregated over ranked candidate residues. The simulation value is a "
            "structural-drift score computed from the trajectory. Their difference "
            "measures disagreement between two proxies; it does NOT indicate which "
            "is closer to physical reality, and neither has been validated against "
            "experiment."
        ),
        "caveats": list(PROXY_CAVEATS),
    }
    if ml_percent is None or proxy_percent is None:
        block["agreement_note"] = (
            "No comparison is possible: "
            + (
                "the scenario has no ML estimate."
                if ml_percent is None
                else "the run produced no degradation proxy."
            )
        )
        return block

    diff = float(proxy_percent) - float(ml_percent)
    block["difference_percentage_points"] = round(diff, 4)
    magnitude = abs(diff)
    if magnitude <= 10:
        block["agreement"] = "close"
    elif magnitude <= 25:
        block["agreement"] = "moderate"
    else:
        block["agreement"] = "divergent"
    block["agreement_note"] = (
        f"The proxies differ by {magnitude:.1f} percentage points "
        f"({'simulation higher' if diff > 0 else 'ML higher'}). Bands (10 / 25 pp) "
        "are presentational only."
    )
    return block


def job_results(job_id: str) -> dict[str, Any]:
    """Assemble the results payload for a finished job."""
    manager = get_job_manager()
    status = manager.read_status(job_id)
    state = JobStatus(status.get("status", "queued"))

    if state is not JobStatus.COMPLETED:
        raise NotFoundError(
            f"Job {job_id} is '{state.value}', so there are no results to show. "
            + (
                f"Failure: {status.get('error_message')}"
                if state is JobStatus.FAILED
                else "Poll GET /simulations/{job_id} until it completes."
            )
        )

    metrics_doc = manager.metrics(job_id)
    if metrics_doc is None:
        raise NotFoundError(
            f"Job {job_id} is marked completed but metrics.json is missing. "
            "The job directory may have been modified."
        )

    request = read_json(manager.job_dir(job_id) / "request.json", {}) or {}
    preset_info = request.get("preset", {})
    scenario = request.get("scenario", {})
    metrics = metrics_doc.get("metrics", {})
    proxy = metrics_doc.get("degradation_proxy") or {}

    result_label = metrics.get("result_label") or preset_info.get(
        "scientific_label", RESULT_LABELS["openmm"]
    )

    limitations = list(preset_info.get("limitations", []))
    limitations.append(
        "Standard OpenMM does not model ionising-radiation events. The requested "
        "dose and particle class are recorded as provenance only; no radiation "
        "physics was simulated in this trajectory."
    )

    return {
        "job_id": job_id,
        "status": state.value,
        "engine": status.get("engine", "openmm"),
        "result_label": result_label,
        "metrics": metrics,
        "series": metrics_doc.get("series", {}),
        "rmsf": metrics_doc.get("rmsf", []),
        "highest_mobility_residues": metrics_doc.get("highest_mobility_residues", []),
        "stability_summary": metrics_doc.get("stability_summary", {}),
        "comparison": _comparison_block(
            status.get("ml_degradation_percent"), proxy.get("percent")
        ),
        "metadata": {
            "pdb_id": status.get("pdb_id"),
            "upload_id": status.get("upload_id"),
            "chain_id": status.get("chain_id"),
            "scenario": scenario,
            "preset": preset_info,
            "created_at": status.get("created_at"),
            "started_at": status.get("started_at"),
            "finished_at": status.get("finished_at"),
            "duration_seconds": status.get("duration_seconds"),
            "prediction_id": status.get("prediction_id"),
            "topology": metrics_doc.get("topology", {}),
            "engine_notes": metrics_doc.get("notes", []),
        },
        "reproducibility": status.get("reproducibility", {}),
        "warnings": status.get("warnings", []),
        "limitations": limitations,
    }


# --------------------------------------------------------------------------- #
# Precomputed fallback
# --------------------------------------------------------------------------- #
def precomputed_available() -> list[str]:
    if not settings.precomputed_dir.exists():
        return []
    return sorted(
        d.name
        for d in settings.precomputed_dir.iterdir()
        if d.is_dir() and (d / "metrics.json").exists()
    )


def precomputed_results(pdb_id: str) -> dict[str, Any]:
    """Load a labelled precomputed result.

    This is a genuinely different provenance from a live run and is labelled
    'Precomputed OpenMM Result' everywhere it surfaces. It is never presented as
    a live simulation.
    """
    from app.core.security import validate_pdb_id

    safe = validate_pdb_id(pdb_id)
    directory = settings.precomputed_dir / safe
    doc = read_json(directory / "metrics.json")
    if doc is None:
        raise NotFoundError(
            f"No precomputed result available for '{safe}'. Available: "
            f"{', '.join(precomputed_available()) or 'none'}."
        )

    payload = dict(doc)
    payload.setdefault("job_id", f"precomputed-{safe}")
    payload["status"] = JobStatus.COMPLETED.value
    payload["engine"] = "precomputed"
    payload["result_label"] = RESULT_LABELS["precomputed"]
    payload.setdefault("warnings", []).insert(
        0,
        "This is a PRECOMPUTED result shipped with the repository, not a simulation "
        "run on this machine now. It is provided so the results interface remains "
        "demonstrable when a live run cannot complete.",
    )
    return payload


def precomputed_structure_path(pdb_id: str, name: str) -> Path:
    from app.core.security import resolve_within, validate_pdb_id

    safe = validate_pdb_id(pdb_id)
    if name not in {"final.pdb", "input.pdb"}:
        raise NotFoundError(f"'{name}' is not available for precomputed results.")
    path = resolve_within(settings.precomputed_dir / safe, name)
    if not path.exists():
        raise NotFoundError(f"'{name}' is not present for precomputed result {safe}.")
    return path
