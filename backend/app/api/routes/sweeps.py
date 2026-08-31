"""FastAPI endpoints for damage-severity and parameter sweeps (issue #33)."""

from __future__ import annotations

from fastapi import APIRouter, Query, status
from fastapi.responses import FileResponse

from app.schemas.sweep import (
    SweepConfig,
    SweepDetail,
    SweepPreviewResponse,
)
from app.services import sweep_service

router = APIRouter(prefix="/sweeps", tags=["sweeps"])


@router.post(
    "/preview",
    response_model=SweepPreviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Preview cost, combinations, and storage for a proposed parameter sweep",
)
def preview_sweep(config: SweepConfig) -> SweepPreviewResponse:
    """Validate bounds and preview compute time and storage before launching a sweep."""
    return sweep_service.create_sweep_preview(config)


@router.post(
    "",
    response_model=SweepDetail,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit and execute a new parameter sweep batch",
)
def submit_sweep(config: SweepConfig) -> SweepDetail:
    """Submit a sweep batch job for execution through the backend queue."""
    return sweep_service.submit_sweep(config)


@router.get(
    "",
    response_model=list[SweepDetail],
    summary="List all historical parameter sweeps",
)
def list_sweeps(
    limit: int = Query(default=100, ge=1, le=500, description="Max sweeps to return"),
) -> list[SweepDetail]:
    """Return summary list of parameter sweep runs."""
    return sweep_service.list_sweeps(limit=limit)


@router.get(
    "/{sweep_id}",
    response_model=SweepDetail,
    summary="Get status and details of a parameter sweep",
)
def get_sweep(sweep_id: str) -> SweepDetail:
    """Retrieve detailed progress, items, and severity-response curves for a sweep."""
    return sweep_service.get_sweep_detail(sweep_id)


@router.post(
    "/{sweep_id}/cancel",
    response_model=SweepDetail,
    summary="Cancel an active parameter sweep",
)
def cancel_sweep(sweep_id: str) -> SweepDetail:
    """Cancel an active sweep without discarding completed valid experiment pairs."""
    return sweep_service.cancel_sweep(sweep_id)


@router.get(
    "/{sweep_id}/export/{format}",
    summary="Download sweep result table (CSV or JSON manifest)",
)
def export_sweep(sweep_id: str, format: str) -> FileResponse:
    """Download sweep results as CSV or JSON manifest."""
    file_path = sweep_service.export_sweep_file(sweep_id, format)
    media_type = "text/csv" if format.lower() == "csv" else "application/json"
    filename = f"{sweep_id}_results.{format.lower()}"
    return FileResponse(
        file_path,
        media_type=media_type,
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
