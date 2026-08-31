"""Simulation job endpoints: presets, submit, poll, cancel, results, artifacts."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Response, status
from fastapi.responses import FileResponse

from app.schemas.simulation import (
    SimulationJobDetail,
    SimulationJobSummary,
    SimulationPreset,
    SimulationRequest,
    SimulationResults,
)
from app.services import analysis_service, replay_service, simulation_service

router = APIRouter(tags=["simulations"])


@router.get(
    "/simulation/presets",
    response_model=list[SimulationPreset],
    summary="Available simulation presets",
)
def presets() -> list[dict[str, Any]]:
    return simulation_service.presets()


@router.get("/simulation/engine", summary="Simulation engine health")
def engine() -> dict[str, Any]:
    return simulation_service.engine_health()


@router.post(
    "/simulations",
    response_model=SimulationJobDetail,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a simulation job",
)
def submit(request: SimulationRequest) -> dict[str, Any]:
    """Validate and enqueue a job.

    Returns 202 with the initial job record; poll ``GET /simulations/{job_id}``
    for real backend progress. Returns 409 if a job is already running (this MVP
    runs one at a time) and 503 if OpenMM is unavailable.
    """
    return simulation_service.submit_simulation(request)


@router.get(
    "/simulations",
    response_model=list[SimulationJobSummary],
    summary="List jobs (history)",
)
def list_jobs(limit: int = Query(default=100, ge=1, le=500)) -> list[dict[str, Any]]:
    return simulation_service.job_list(limit=limit)


@router.get(
    "/simulations/{job_id}",
    response_model=SimulationJobDetail,
    summary="Job status and live progress",
)
def job_detail(job_id: str) -> dict[str, Any]:
    return simulation_service.job_detail(job_id)


@router.post("/simulations/{job_id}/cancel", summary="Request cancellation")
def cancel(job_id: str) -> dict[str, Any]:
    return simulation_service.cancel_job(job_id)


@router.delete(
    "/simulations/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a job and its artifacts",
)
def delete(job_id: str) -> Response:
    simulation_service.delete_job(job_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/simulations/{job_id}/results",
    response_model=SimulationResults,
    summary="Analysis results for a completed job",
)
def results(job_id: str) -> dict[str, Any]:
    return simulation_service.job_results(job_id)


@router.get(
    "/simulations/{job_id}/structure",
    summary="Final (or prepared/input) structure of a job",
)
def structure(
    job_id: str,
    which: str = Query(
        default="final",
        pattern="^(final|prepared|topology|input)$",
        description=(
            "final = end of run; prepared = cleaned heavy-atom input; "
            "topology = the exact simulated system including added hydrogens "
            "(this is the correct topology for trajectory.dcd); input = the "
            "original file as submitted."
        ),
    ),
) -> FileResponse:
    path = simulation_service.get_job_manager().artifact_path(job_id, f"{which}.pdb")
    return FileResponse(path, media_type="chemical/x-pdb", filename=f"{job_id}_{which}.pdb")


@router.get("/simulations/{job_id}/trajectory", summary="Trajectory (DCD)")
def trajectory(job_id: str) -> FileResponse:
    path = simulation_service.get_job_manager().artifact_path(job_id, "trajectory.dcd")
    return FileResponse(
        path, media_type="application/octet-stream", filename=f"{job_id}_trajectory.dcd"
    )


@router.get("/simulations/{job_id}/log", summary="Full simulation log")
def job_log(job_id: str) -> FileResponse:
    path = simulation_service.get_job_manager().artifact_path(job_id, "simulation.log")
    return FileResponse(path, media_type="text/plain", filename=f"{job_id}.log")


# --------------------------------------------------------------------------- #
# Comparison
# --------------------------------------------------------------------------- #
@router.get("/simulations/compare/{job_id_a}/{job_id_b}", summary="Compare two jobs")
def compare(job_id_a: str, job_id_b: str) -> dict[str, Any]:
    return analysis_service.compare_jobs(job_id_a, job_id_b)


@router.get(
    "/simulations/{job_id}/replay",
    summary="Draft a new run reproducing an earlier configuration",
)
def replay(job_id: str) -> dict[str, Any]:
    """Returns a draft only. The original experiment is never overwritten.

    Starting the replay is a separate POST /simulations with this draft, so
    replaying an expensive run is a deliberate confirmation rather than a side
    effect of opening a page.
    """
    return replay_service.replay_draft(job_id)


@router.get(
    "/simulations/diff/{job_id_a}/{job_id_b}",
    summary="Configuration diff, saying whether the runs are comparable",
)
def configuration_diff(job_id_a: str, job_id_b: str) -> dict[str, Any]:
    """Every setting that differs, classified by whether it invalidates the pair.

    A different seed and a different force field are both differences, but one
    is the experiment and the other means the results should never have been
    put side by side.
    """
    return replay_service.configuration_diff(job_id_a, job_id_b)


# --------------------------------------------------------------------------- #
# Precomputed fallback
# --------------------------------------------------------------------------- #
@router.get("/precomputed", summary="List precomputed results")
def precomputed_list() -> dict[str, Any]:
    return {
        "available": simulation_service.precomputed_available(),
        "notice": (
            "Precomputed results are shipped with the repository and labelled "
            "'Precomputed OpenMM Result'. They are never presented as a live run."
        ),
    }


@router.get("/precomputed/{pdb_id}/results", summary="Precomputed result payload")
def precomputed_results(pdb_id: str) -> dict[str, Any]:
    return simulation_service.precomputed_results(pdb_id)


@router.get("/precomputed/{pdb_id}/structure", summary="Precomputed final structure")
def precomputed_structure(
    pdb_id: str,
    which: str = Query(default="final", pattern="^(final|input)$"),
) -> FileResponse:
    path = simulation_service.precomputed_structure_path(pdb_id, f"{which}.pdb")
    return FileResponse(
        path, media_type="chemical/x-pdb", filename=f"{pdb_id}_precomputed_{which}.pdb"
    )


# --------------------------------------------------------------------------- #
# Evidence Bundles (#21)
# --------------------------------------------------------------------------- #
@router.get("/simulations/{job_id}/bundle", summary="Download evidence bundle (.zip)")
def simulation_bundle(job_id: str) -> FileResponse:
    from app.services import bundle_service
    zip_path = bundle_service.generate_evidence_bundle(job_id)
    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=f"{job_id}_evidence_bundle.zip",
    )


@router.get("/precomputed/{pdb_id}/bundle", summary="Download precomputed evidence bundle (.zip)")
def precomputed_bundle(pdb_id: str) -> FileResponse:
    from app.services import bundle_service
    zip_path = bundle_service.generate_precomputed_bundle(pdb_id)
    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=f"{pdb_id}_precomputed_bundle.zip",
    )
