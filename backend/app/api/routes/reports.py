"""Report exports (JSON and CSV)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse, PlainTextResponse

from app.services import report_service

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/{job_id}.json", summary="Full experiment report (JSON)")
def report_json(job_id: str) -> JSONResponse:
    payload: dict[str, Any] = report_service.report_json_payload(job_id)
    return JSONResponse(
        content=payload,
        headers={
            "Content-Disposition": f'attachment; filename="bionano-sim-{job_id}.json"'
        },
    )


@router.get(
    "/{job_id}.csv",
    response_class=PlainTextResponse,
    summary="Flat experiment report (CSV)",
)
def report_csv(job_id: str) -> PlainTextResponse:
    # Excel on Windows assumes the legacy ANSI codepage for .csv unless a UTF-8
    # BOM is present, which would mangle the em-dashes and units in the notice
    # rows. The BOM is ignored by pandas, R and every text editor.
    body = "﻿" + report_service.build_csv_report(job_id)
    return PlainTextResponse(
        content=body,
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="bionano-sim-{job_id}.csv"'
        },
    )
