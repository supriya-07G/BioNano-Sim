"""Protein registry, structure serving, upload, and candidate onboarding routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, Form, Query, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse

from app.config import settings
from app.core.exceptions import InvalidProteinError
from app.core.security import new_job_id
from app.schemas.onboarding import CandidateRecord, CandidateReviewAction, CandidateSubmission
from app.schemas.protein import ProteinDetail, ProteinSummary, UploadedProtein
from app.services import protein_onboarding_service, protein_service

router = APIRouter(prefix="/proteins", tags=["proteins"])


@router.get("", response_model=list[ProteinSummary], summary="List approved proteins")
def list_proteins() -> list[dict[str, Any]]:
    return protein_service.list_proteins()


@router.get("/onboard/candidates", response_model=list[CandidateRecord], summary="List onboarding candidates")
def list_onboarding_candidates(
    state: str | None = Query(default=None, description="Filter by state: pending, approved, or rejected")
) -> list[dict[str, Any]]:
    return protein_onboarding_service.list_candidates(state)


@router.post("/onboard/submit", response_model=CandidateRecord, summary="Submit a candidate for onboarding")
async def submit_candidate(
    file: UploadFile = File(...),
    pdb_id: str = Form(...),
    name: str = Form(...),
    uniprot: str = Form("N/A"),
    proposed_role: str = Form(...),
    why_selected: str = Form(...),
    chain_id: str = Form("A"),
    source: str = Form("RCSB PDB (files.rcsb.org)"),
    license_note: str = Form("PDB coordinate data is distributed by RCSB PDB under CC0 1.0 Universal."),
) -> dict[str, Any]:
    content = await file.read()
    submission = CandidateSubmission(
        pdb_id=pdb_id,
        name=name,
        uniprot=uniprot,
        proposed_role=proposed_role,
        why_selected=why_selected,
        chain_id=chain_id,
        source=source,
        license_note=license_note,
    )
    return protein_onboarding_service.submit_candidate(content, submission)


@router.post("/onboard/review", response_model=CandidateRecord, summary="Review a candidate (approve/reject)")
def review_candidate(action: CandidateReviewAction) -> dict[str, Any]:
    return protein_onboarding_service.review_candidate(action)


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
    """Serve the PDB file for the molecular viewer."""
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
    """Validate an uploaded structure and stage it under ``runtime/uploads``."""
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
