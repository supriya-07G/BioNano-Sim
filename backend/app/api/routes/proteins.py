"""Protein registry, structure serving and upload."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, Query, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse

from app.config import settings
from app.core.exceptions import InvalidProteinError
from app.core.security import new_job_id
from app.schemas.protein import ProteinDetail, ProteinSummary, UploadedProtein
from app.services import protein_service

router = APIRouter(prefix="/proteins", tags=["proteins"])


@router.get("", response_model=list[ProteinSummary], summary="List approved proteins")
def list_proteins() -> list[dict[str, Any]]:
    return protein_service.list_proteins()


@router.get("/{pdb_id}", response_model=ProteinDetail, summary="Protein detail")
def get_protein(
    pdb_id: str,
    top_n: int = Query(default=10, ge=1, le=50, description="Candidate residues to return."),
) -> dict[str, Any]:
    return protein_service.get_protein_detail(pdb_id, top_n=top_n)


@router.get(
    "/{pdb_id}/structure",
    response_class=PlainTextResponse,
    summary="Raw PDB coordinates",
    responses={200: {"content": {"chemical/x-pdb": {}}}},
)
def get_structure(pdb_id: str) -> FileResponse:
    """Serve the PDB file for the molecular viewer.

    Returned as a file response so the viewer can stream it and the browser can
    cache it; the registry lookup rejects anything that is not an approved id.
    """
    path = protein_service.structure_path(pdb_id)
    return FileResponse(
        path,
        media_type="chemical/x-pdb",
        filename=path.name,
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.post(
    "/upload",
    response_model=UploadedProtein,
    summary="Upload and validate a custom PDB",
)
async def upload_protein(file: UploadFile = File(...)) -> dict[str, Any]:
    """Validate an uploaded structure and stage it under ``runtime/uploads``.

    The body is read with a hard cap so an oversized upload is rejected without
    being buffered in full.
    """
    limit = settings.max_upload_bytes
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(1 << 20)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise InvalidProteinError(
                f"Upload exceeds the {limit / 1e6:.0f} MB limit.",
                code="FILE_TOO_LARGE",
            )
        chunks.append(chunk)

    return protein_service.validate_and_store_upload(
        b"".join(chunks), file.filename or "upload.pdb", new_job_id()
    )


@router.get(
    "/upload/{upload_id}/structure",
    response_class=PlainTextResponse,
    summary="Raw coordinates of an uploaded structure",
)
def get_uploaded_structure(upload_id: str) -> FileResponse:
    path = protein_service.upload_path(upload_id)
    return FileResponse(path, media_type="chemical/x-pdb", filename=path.name)
