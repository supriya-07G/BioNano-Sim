"""Paired mechanical experiments API endpoints (issue #7)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, status
from fastapi.responses import FileResponse, JSONResponse

from app.schemas.experiment import (
    ExperimentDetail,
    ExperimentImportRequest,
    ExperimentImportResponse,
    ExperimentSummary,
    PairedForceExtensionResponse,
)
from app.services import experiment_service

router = APIRouter(prefix="/experiments", tags=["experiments"])


@router.post(
    "/import",
    response_model=ExperimentImportResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Import an experiment dataset directory",
)
def import_experiment(request: ExperimentImportRequest) -> dict[str, Any]:
    """Import and validate an experiment artifact directory into the runtime repository."""
    return experiment_service.import_experiment(
        source_path=request.source_path,
        override_id=request.experiment_id,
    )


@router.get(
    "",
    response_model=list[ExperimentSummary],
    summary="List paired mechanical experiments",
)
def list_experiments(
    limit: int = Query(default=100, ge=1, le=500, description="Max experiments to return"),
) -> list[dict[str, Any]]:
    """Return summary list of available paired mechanical experiments."""
    return experiment_service.list_experiments(limit=limit)


@router.get(
    "/{experiment_id}",
    response_model=ExperimentDetail,
    summary="Get paired experiment detail",
)
def get_experiment(experiment_id: str) -> dict[str, Any]:
    """Return full experiment metadata, metrics, stiffness fit, and quality status."""
    return experiment_service.get_experiment_detail(experiment_id)


@router.get(
    "/{experiment_id}/force-extension",
    response_model=PairedForceExtensionResponse,
    summary="Get paired force-extension series",
)
def get_force_extension(experiment_id: str) -> dict[str, Any]:
    """Return paired force-extension time series curves for pristine and damaged runs."""
    return experiment_service.get_force_extension(experiment_id)


@router.get(
    "/{experiment_id}/structures/{condition}",
    summary="Get PDB structure for pristine or damaged condition",
    responses={200: {"content": {"chemical/x-pdb": {}}}},
)
def get_structure(experiment_id: str, condition: str) -> FileResponse:
    """Serve PDB structure coordinates for condition (baseline/pristine or damaged)."""
    path = experiment_service.get_structure_file(experiment_id, condition)
    return FileResponse(
        path,
        media_type="chemical/x-pdb",
        filename=f"{experiment_id}_{condition}.pdb",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get(
    "/{experiment_id}/report",
    summary="Download full experiment report (JSON)",
)
def get_report(experiment_id: str) -> JSONResponse:
    """Return complete paired experiment report with manifests and features."""
    payload = experiment_service.get_report_payload(experiment_id)
    return JSONResponse(
        content=payload,
        headers={
            "Content-Disposition": f'attachment; filename="COSMORA-EXP-{experiment_id}.json"'
        },
    )
