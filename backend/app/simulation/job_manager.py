"""Local job manager: one simulation at a time, state on disk, atomic writes.

Design constraints from the spec:

* jobs run outside the request/response cycle (a ``ThreadPoolExecutor``),
* concurrency is capped at one (raising it needs a real queue, not a bigger pool),
* ``status.json`` is written atomically because the UI polls it every second,
* a failed job is **never** marked completed,
* every job directory is self-describing so History can be rebuilt from disk
  alone after a restart.

State lives on disk rather than in memory so a backend restart does not lose
history. In-memory structures hold only the cancel flags for live jobs.
"""

from __future__ import annotations

import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config import settings
from app.core.exceptions import (
    InvalidSimulationInputError,
    JobConflictError,
    NotFoundError,
)
from app.core.logging import get_logger
from app.core.security import new_job_id, resolve_within, validate_job_id
from app.schemas.simulation import STAGE_LABELS, STAGE_ORDER, JobStage, JobStatus
from app.simulation.engine import _CancelledError, run_simulation
from app.simulation.presets import SAFE_RETRY_PRESET_ID, get_preset
from app.utils.files import atomic_write_json, read_json, tail_lines
from app.utils.serialization import to_jsonable, utc_now_iso

logger = get_logger("bionano.simulation.jobs")

# Progress weights per stage. They sum to 1.0 and are used only for the overall
# progress bar; the underlying step counts remain exact in the payload.
_STAGE_WEIGHTS: dict[JobStage, float] = {
    JobStage.INPUT_VALIDATION: 0.03,
    JobStage.PROTEIN_PREPARATION: 0.07,
    JobStage.SYSTEM_CONSTRUCTION: 0.10,
    JobStage.ENERGY_MINIMIZATION: 0.10,
    JobStage.EQUILIBRATION: 0.15,
    JobStage.PRODUCTION: 0.40,
    JobStage.TRAJECTORY_ANALYSIS: 0.12,
    JobStage.REPORT_GENERATION: 0.03,
}


@dataclass
class _LiveJob:
    job_id: str
    cancel: threading.Event
    started_monotonic: float


class JobManager:
    def __init__(self) -> None:
        self._executor = ThreadPoolExecutor(
            max_workers=settings.max_concurrent_jobs,
            thread_name_prefix="bionano-sim",
        )
        self._live: dict[str, _LiveJob] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ #
    # Paths
    # ------------------------------------------------------------------ #
    def job_dir(self, job_id: str) -> Path:
        safe = validate_job_id(job_id)
        return resolve_within(settings.jobs_dir, safe)

    def _require_job_dir(self, job_id: str) -> Path:
        path = self.job_dir(job_id)
        if not path.is_dir():
            raise NotFoundError(f"No simulation job with id '{job_id}'.")
        return path

    # ------------------------------------------------------------------ #
    # Status persistence
    # ------------------------------------------------------------------ #
    def _write_status(self, job_dir: Path, status: dict[str, Any]) -> None:
        atomic_write_json(job_dir / "status.json", to_jsonable(status))

    def read_status(self, job_id: str) -> dict[str, Any]:
        job_dir = self._require_job_dir(job_id)
        status = read_json(job_dir / "status.json")
        if status is None:
            # Directory exists but status is unreadable: report it rather than 500.
            return {
                "job_id": job_id,
                "status": JobStatus.FAILED.value,
                "error_code": "STATUS_UNREADABLE",
                "error_message": "The job's status.json is missing or unparseable.",
                "created_at": utc_now_iso(),
                "stages": _initial_stages(),
            }
        return status

    # ------------------------------------------------------------------ #
    # Submission
    # ------------------------------------------------------------------ #
    def active_job_ids(self) -> list[str]:
        """Job ids currently held by a worker thread."""
        with self._lock:
            return list(self._live)

    def submit(
        self,
        *,
        request: Any,
        source_pdb: Path,
        structure_info: dict[str, Any],
        scenario: dict[str, Any],
        validation_warnings: list[str],
    ) -> str:
        preset = get_preset(request.preset_id)

        with self._lock:
            if len(self._live) >= settings.max_concurrent_jobs:
                running = ", ".join(self._live)
                raise JobConflictError(
                    f"A simulation is already running ({running}). This local MVP runs "
                    "one job at a time; wait for it to finish or cancel it first.",
                    code="CONCURRENCY_LIMIT",
                )
            job_id = new_job_id()
            cancel = threading.Event()
            self._live[job_id] = _LiveJob(job_id, cancel, time.monotonic())

        job_dir = self.job_dir(job_id)
        job_dir.mkdir(parents=True, exist_ok=True)
        (job_dir / "analysis").mkdir(exist_ok=True)

        # Snapshot the input structure so results stay reproducible even if the
        # upload is later deleted.
        try:
            (job_dir / "input.pdb").write_bytes(source_pdb.read_bytes())
        except OSError as exc:
            with self._lock:
                self._live.pop(job_id, None)
            raise InvalidSimulationInputError(
                f"Could not stage the input structure: {exc}"
            ) from exc

        request_payload = {
            **request.model_dump(),
            "preset": preset.as_dict(),
            "scenario": scenario,
            "structure_info": structure_info,
        }
        atomic_write_json(job_dir / "request.json", to_jsonable(request_payload))

        status = {
            "job_id": job_id,
            "status": JobStatus.QUEUED.value,
            "pdb_id": request.pdb_id,
            "upload_id": request.upload_id,
            "chain_id": request.chain_id,
            "scenario_id": request.scenario_id,
            "preset_id": preset.preset_id,
            "engine": "openmm",
            "created_at": utc_now_iso(),
            "started_at": None,
            "finished_at": None,
            "duration_seconds": None,
            "progress": 0.0,
            "current_stage": None,
            "stages": _initial_stages(),
            "steps_completed": 0,
            "steps_total": preset.equilibration_steps + preset.production_steps,
            "elapsed_seconds": 0.0,
            "temperature_kelvin": None,
            "potential_energy_kj_mol": None,
            "ml_degradation_percent": request.ml_degradation_percent,
            "prediction_id": request.prediction_id,
            "simulation_degradation_proxy_percent": None,
            "warnings": list(validation_warnings),
            "error_code": None,
            "error_message": None,
            "reproducibility": _reproducibility(request, preset, structure_info),
        }
        self._write_status(job_dir, status)

        self._executor.submit(
            self._run, job_id=job_id, request=request, preset=preset, job_dir=job_dir
        )
        logger.info(
            "Job %s submitted: %s chain %s preset %s",
            job_id,
            request.pdb_id or request.upload_id,
            request.chain_id,
            preset.preset_id,
        )
        return job_id

    # ------------------------------------------------------------------ #
    # Worker
    # ------------------------------------------------------------------ #
    def _run(self, *, job_id: str, request: Any, preset: Any, job_dir: Path) -> None:
        log_path = job_dir / "simulation.log"
        started = time.monotonic()
        state: dict[str, Any] = self.read_status(job_id)
        stage_state: dict[str, Any] = {"current": None}

        def log(message: str) -> None:
            line = f"{utc_now_iso()}  {message}\n"
            try:
                with log_path.open("a", encoding="utf-8", newline="\n") as fh:
                    fh.write(line)
            except OSError:
                logger.warning("Could not append to %s", log_path)

        def cancelled() -> bool:
            with self._lock:
                live = self._live.get(job_id)
            return bool(live and live.cancel.is_set())

        def report(
            stage: JobStage, detail: str, extra: dict[str, Any] | None
        ) -> None:
            now = utc_now_iso()
            previous = stage_state["current"]
            if previous != stage:
                for entry in state["stages"]:
                    if entry["stage"] == stage.value:
                        entry["state"] = "active"
                        entry["started_at"] = now
                    elif previous is not None and entry["stage"] == previous.value:
                        if entry["state"] == "active":
                            entry["state"] = "done"
                            entry["finished_at"] = now
                stage_state["current"] = stage
                log(f"stage -> {stage.value}: {detail}")

            for entry in state["stages"]:
                if entry["stage"] == stage.value:
                    entry["detail"] = detail

            state["status"] = JobStatus.RUNNING.value
            state["current_stage"] = stage.value
            state["elapsed_seconds"] = round(time.monotonic() - started, 3)
            if extra:
                for key in (
                    "steps_completed", "steps_total",
                    "potential_energy_kj_mol", "temperature_kelvin",
                ):
                    if key in extra:
                        state[key] = extra[key]
            state["progress"] = _progress(state, stage)
            self._write_status(job_dir, state)

        try:
            state["status"] = JobStatus.RUNNING.value
            state["started_at"] = utc_now_iso()
            self._write_status(job_dir, state)
            log(f"job {job_id} started; preset={preset.preset_id}")

            report(JobStage.INPUT_VALIDATION, "Re-validating staged input", None)
            if cancelled():
                raise _CancelledError()

            result = run_simulation(
                source_pdb=job_dir / "input.pdb",
                job_dir=job_dir,
                chain_id=request.chain_id,
                preset=preset,
                temperature_kelvin=request.temperature_kelvin,
                seed=request.random_seed,
                report=report,
                should_cancel=cancelled,
                log=log,
            )

            report(JobStage.REPORT_GENERATION, "Writing metrics and analysis", None)
            payload = {
                "job_id": job_id,
                "metrics": result.metrics,
                "series": result.series,
                "rmsf": result.rmsf,
                "highest_mobility_residues": result.highest_mobility_residues,
                "stability_summary": result.stability_summary,
                "degradation_proxy": result.degradation_proxy,
                "topology": {
                    k: v
                    for k, v in result.topology.items()
                    # ca_indices is long and only useful inside the engine.
                    if k != "ca_indices"
                },
                "notes": result.notes,
                "generated_at_utc": utc_now_iso(),
            }
            atomic_write_json(job_dir / "metrics.json", to_jsonable(payload))
            log("wrote metrics.json")

            now = utc_now_iso()
            for entry in state["stages"]:
                if entry["state"] in ("active", "pending"):
                    entry["state"] = "done"
                    entry["finished_at"] = entry["finished_at"] or now
            proxy_percent = (result.degradation_proxy or {}).get("percent")
            # The preset asks for platform "auto"; record what was actually
            # selected, since GPU platforms are not bit-reproducible.
            resolved = result.topology.get("platform")
            if resolved:
                state.setdefault("reproducibility", {})["platform_resolved"] = resolved
                state["reproducibility"]["platform_properties"] = result.topology.get(
                    "platform_properties", {}
                )
                state["reproducibility"]["nonbonded_cutoff_nm"] = result.topology.get(
                    "nonbonded_cutoff_nm"
                )
                state["reproducibility"]["bitwise_reproducible"] = resolved in (
                    "CPU",
                    "Reference",
                )
            state.update(
                {
                    "status": JobStatus.COMPLETED.value,
                    "progress": 1.0,
                    "current_stage": JobStage.REPORT_GENERATION.value,
                    "finished_at": now,
                    "duration_seconds": round(time.monotonic() - started, 3),
                    "elapsed_seconds": round(time.monotonic() - started, 3),
                    "simulation_degradation_proxy_percent": proxy_percent,
                    "warnings": list(
                        dict.fromkeys([*state.get("warnings", []), *result.notes])
                    ),
                }
            )
            self._write_status(job_dir, state)
            log(f"job {job_id} completed in {state['duration_seconds']}s")
            logger.info("Job %s completed in %.1fs", job_id, state["duration_seconds"])

        except _CancelledError:
            self._finalise_failure(
                job_dir, state, started, log,
                status=JobStatus.CANCELLED,
                code="CANCELLED",
                message="The job was cancelled before it finished.",
                retry_hint=None,
            )
            logger.info("Job %s cancelled", job_id)

        except Exception as exc:  # noqa: BLE001 - must never leak from the worker
            code = getattr(exc, "code", None) or "SIMULATION_FAILED"
            message = getattr(exc, "message", None) or f"{type(exc).__name__}: {exc}"
            log(f"ERROR {code}: {message}")
            log(traceback.format_exc())
            self._finalise_failure(
                job_dir, state, started, log,
                status=JobStatus.FAILED,
                code=code,
                message=message,
                retry_hint={
                    "preset_id": SAFE_RETRY_PRESET_ID,
                    "label": "Retry with safe preset (minimisation only)",
                    "reason": (
                        "Minimisation-only skips dynamics entirely, which succeeds for "
                        "structures that fail to equilibrate. It produces no trajectory, "
                        "so RMSD/RMSF charts and the degradation proxy stay unavailable."
                    ),
                },
            )
            logger.error("Job %s failed: %s: %s", job_id, code, message)

        finally:
            with self._lock:
                self._live.pop(job_id, None)

    def _finalise_failure(
        self,
        job_dir: Path,
        state: dict[str, Any],
        started: float,
        log: Any,
        *,
        status: JobStatus,
        code: str,
        message: str,
        retry_hint: dict[str, Any] | None,
    ) -> None:
        """Mark a job terminal-but-not-successful. Never writes 'completed'."""
        now = utc_now_iso()
        for entry in state.get("stages", []):
            if entry["state"] == "active":
                entry["state"] = "failed" if status is JobStatus.FAILED else "skipped"
                entry["finished_at"] = now
            elif entry["state"] == "pending":
                entry["state"] = "skipped"
        state.update(
            {
                "status": status.value,
                "finished_at": now,
                "duration_seconds": round(time.monotonic() - started, 3),
                "elapsed_seconds": round(time.monotonic() - started, 3),
                "error_code": code,
                "error_message": message,
                "retry_hint": retry_hint,
            }
        )
        self._write_status(job_dir, state)

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #
    def cancel(self, job_id: str) -> dict[str, Any]:
        status = self.read_status(job_id)
        current = JobStatus(status.get("status", JobStatus.QUEUED.value))
        if current.is_terminal:
            raise JobConflictError(
                f"Job {job_id} is already {current.value} and cannot be cancelled.",
                code="JOB_ALREADY_TERMINAL",
            )
        with self._lock:
            live = self._live.get(job_id)
        if live is None:
            # Not held by a worker but not terminal either: reconcile the record.
            job_dir = self._require_job_dir(job_id)
            self._finalise_failure(
                job_dir, status, time.monotonic(), lambda _m: None,
                status=JobStatus.CANCELLED,
                code="CANCELLED",
                message="Job was not running (backend may have restarted); "
                        "marked cancelled.",
                retry_hint=None,
            )
            return self.read_status(job_id)

        live.cancel.set()
        logger.info("Cancellation requested for job %s", job_id)
        return {
            **status,
            "cancellation_requested": True,
            "note": "The worker stops at its next step-chunk boundary, normally "
                    "within a second.",
        }

    def detail(self, job_id: str) -> dict[str, Any]:
        job_dir = self._require_job_dir(job_id)
        status = self.read_status(job_id)
        request = read_json(job_dir / "request.json", {})
        return {
            **status,
            "request": request,
            "log_tail": tail_lines(job_dir / "simulation.log", 200),
            "artifacts": {
                "input_pdb": (job_dir / "input.pdb").exists(),
                "prepared_pdb": (job_dir / "prepared.pdb").exists(),
                "topology_pdb": (job_dir / "topology.pdb").exists(),
                "final_pdb": (job_dir / "final.pdb").exists(),
                "trajectory_dcd": (job_dir / "trajectory.dcd").exists(),
                "state_csv": (job_dir / "state.csv").exists(),
                "metrics_json": (job_dir / "metrics.json").exists(),
                "analysis_csvs": (job_dir / "analysis" / "rmsd.csv").exists(),
                "simulation_log": (job_dir / "simulation.log").exists(),
            },
        }

    def metrics(self, job_id: str) -> dict[str, Any] | None:
        job_dir = self._require_job_dir(job_id)
        return read_json(job_dir / "metrics.json")

    def list_jobs(self, limit: int = 100) -> list[dict[str, Any]]:
        """Rebuild history from the job directories on disk."""
        if not settings.jobs_dir.exists():
            return []
        rows: list[dict[str, Any]] = []
        for entry in settings.jobs_dir.iterdir():
            if not entry.is_dir():
                continue
            status = read_json(entry / "status.json")
            if status is None:
                # A directory with no readable status is surfaced, not hidden.
                rows.append(
                    {
                        "job_id": entry.name,
                        "status": JobStatus.FAILED.value,
                        "error_code": "STATUS_UNREADABLE",
                        "error_message": "status.json missing or unparseable.",
                        "created_at": utc_now_iso(),
                    }
                )
                continue
            rows.append(status)
        rows.sort(key=lambda r: str(r.get("created_at") or ""), reverse=True)
        return rows[:limit]

    def delete(self, job_id: str) -> None:
        import shutil

        job_dir = self._require_job_dir(job_id)
        status = self.read_status(job_id)
        if not JobStatus(status.get("status", "queued")).is_terminal:
            raise JobConflictError(
                f"Job {job_id} is still {status.get('status')}. Cancel it before "
                "deleting.",
                code="JOB_STILL_ACTIVE",
            )
        shutil.rmtree(job_dir)
        logger.info("Deleted job %s", job_id)

    def artifact_path(self, job_id: str, name: str) -> Path:
        """Resolve a named artifact inside a job directory, with confinement."""
        allowed = {
            "input.pdb", "prepared.pdb", "topology.pdb", "final.pdb", "trajectory.dcd",
            "state.csv", "metrics.json", "request.json", "status.json",
            "simulation.log",
        }
        if name not in allowed:
            raise NotFoundError(f"'{name}' is not a downloadable job artifact.")
        job_dir = self._require_job_dir(job_id)
        path = resolve_within(job_dir, name)
        if not path.exists():
            raise NotFoundError(
                f"Artifact '{name}' does not exist for job {job_id}. It may not have "
                "been produced (for example, a minimisation-only run writes no "
                "trajectory)."
            )
        return path

    def shutdown(self) -> None:
        for job_id in self.active_job_ids():
            with self._lock:
                live = self._live.get(job_id)
            if live:
                live.cancel.set()
        self._executor.shutdown(wait=False, cancel_futures=True)


def _reproducibility(
    request: Any, preset: Any, structure_info: dict[str, Any]
) -> dict[str, Any]:
    """Everything needed to reproduce this exact run.

    Recorded at submission time rather than derived later, so the record survives
    a change to the presets or to the code.
    """
    import platform
    import sys

    def _version(module: str) -> str | None:
        try:
            import importlib

            return getattr(importlib.import_module(module), "__version__", None)
        except Exception:  # noqa: BLE001
            return None

    return {
        "structure_kind": structure_info.get("kind"),
        "structure_identifier": structure_info.get("identifier"),
        "chain_id": request.chain_id,
        "n_residues_simulated": structure_info.get("n_residues"),
        "scenario_id": request.scenario_id,
        "preset_id": preset.preset_id,
        "forcefield": list(preset.forcefield),
        "solvent_model": preset.solvent,
        "constraints": preset.constraints,
        "platform_requested": preset.platform,
        "integrator": "LangevinMiddleIntegrator",
        "friction_per_ps": preset.friction_per_ps,
        "timestep_fs": preset.timestep_fs,
        "minimisation_steps": preset.minimisation_steps,
        "equilibration_steps": preset.equilibration_steps,
        "production_steps": preset.production_steps,
        "temperature_kelvin": request.temperature_kelvin,
        "random_seed": request.random_seed,
        "seed_note": (
            "The integrator random seed and initial-velocity seed are both set from "
            "random_seed, so re-running with the same preset, structure, seed and "
            "OpenMM build reproduces the trajectory."
        ),
        "dose_recorded": f"{request.dose} {request.dose_unit}",
        "dose_note": (
            "Recorded for provenance only. No radiation physics is simulated: "
            "standard OpenMM models no particle tracks, energy deposition or bond "
            "scission."
        ),
        "software": {
            "python": sys.version.split()[0],
            "platform": platform.platform(),
            "openmm": _version("openmm"),
            "mdtraj": _version("mdtraj"),
            "numpy": _version("numpy"),
            "biopython": _version("Bio"),
        },
    }


def _initial_stages() -> list[dict[str, Any]]:
    return [
        {
            "stage": stage.value,
            "label": STAGE_LABELS[stage],
            "state": "pending",
            "started_at": None,
            "finished_at": None,
            "detail": None,
        }
        for stage in STAGE_ORDER
    ]


def _progress(state: dict[str, Any], stage: JobStage) -> float:
    """Overall progress: completed stage weights plus real intra-stage fraction."""
    completed = sum(
        _STAGE_WEIGHTS[JobStage(entry["stage"])]
        for entry in state.get("stages", [])
        if entry["state"] == "done"
    )
    fraction = 0.0
    total = state.get("steps_total") or 0
    done = state.get("steps_completed") or 0
    if stage in (JobStage.EQUILIBRATION, JobStage.PRODUCTION) and total > 0:
        # Step counts span equilibration+production, so split the combined weight.
        combined = _STAGE_WEIGHTS[JobStage.EQUILIBRATION] + _STAGE_WEIGHTS[JobStage.PRODUCTION]
        equil_done = any(
            e["stage"] == JobStage.EQUILIBRATION.value and e["state"] == "done"
            for e in state.get("stages", [])
        )
        base = completed - (_STAGE_WEIGHTS[JobStage.EQUILIBRATION] if equil_done else 0.0)
        return round(min(1.0, max(0.0, base + combined * (done / total))), 4)
    fraction = _STAGE_WEIGHTS.get(stage, 0.0) * 0.5
    return round(min(1.0, completed + fraction), 4)


_manager: JobManager | None = None
_manager_lock = threading.Lock()


def get_job_manager() -> JobManager:
    global _manager
    if _manager is None:
        with _manager_lock:
            if _manager is None:
                settings.ensure_runtime_dirs()
                _manager = JobManager()
    return _manager
