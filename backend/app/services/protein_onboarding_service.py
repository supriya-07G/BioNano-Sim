"""Service for onboarding new protein candidates into the curated library.

Provides validation, feature extraction, cryptographic hash recording, and
governance state management (pending -> approved/rejected).
"""

from __future__ import annotations

import datetime
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from app.config import settings
from app.core.exceptions import InvalidProteinError, NotFoundError, ValidationFailedError
from app.core.logging import get_logger
from app.schemas.onboarding import (
    CandidateRecord,
    CandidateReviewAction,
    CandidateSubmission,
    CandidateValidationReport,
)
from app.simulation.preparation import _extract_chain_pure_python

logger = get_logger("COSMORA.services.onboarding")

CANDIDATES_JSON = settings.protein_metadata_dir / "candidates.json"
CANDIDATES_PDB_DIR = settings.data_dir / "proteins" / "candidates_pdb"


def _ensure_dirs() -> None:
    CANDIDATES_JSON.parent.mkdir(parents=True, exist_ok=True)
    CANDIDATES_PDB_DIR.mkdir(parents=True, exist_ok=True)
    if not CANDIDATES_JSON.exists():
        CANDIDATES_JSON.write_text(json.dumps({"candidates": []}, indent=2), encoding="utf-8")


def compute_sha256(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def load_candidates() -> list[dict[str, Any]]:
    _ensure_dirs()
    try:
        data = json.loads(CANDIDATES_JSON.read_text(encoding="utf-8"))
        return data.get("candidates", [])
    except Exception as err:
        logger.error("Failed to load candidates.json: %s", err)
        return []


def save_candidates(candidates: list[dict[str, Any]]) -> None:
    _ensure_dirs()
    content = json.dumps({"candidates": candidates}, indent=2)
    CANDIDATES_JSON.write_text(content, encoding="utf-8")


def validate_candidate_structure(
    pdb_bytes: bytes, submission: CandidateSubmission
) -> CandidateValidationReport:
    if len(pdb_bytes) == 0:
        raise InvalidProteinError("PDB file content is empty.", code="EMPTY_FILE")

    structure_hash = compute_sha256(pdb_bytes)

    # Save to temp file for extraction
    temp_src = CANDIDATES_PDB_DIR / f"temp_{submission.pdb_id}.pdb"
    temp_dst = CANDIDATES_PDB_DIR / f"temp_{submission.pdb_id}_extracted.pdb"
    temp_src.write_bytes(pdb_bytes)

    try:
        prepared = _extract_chain_pure_python(temp_src, temp_dst, submission.chain_id)
    except Exception as cause:
        if temp_src.exists():
            temp_src.unlink()
        if temp_dst.exists():
            temp_dst.unlink()
        raise InvalidProteinError(
            f"Structure validation failed: {cause}", code="VALIDATION_FAILED"
        ) from cause
    finally:
        if temp_src.exists():
            temp_src.unlink()
        if temp_dst.exists():
            temp_dst.unlink()

    # Calculate composition
    res_types = prepared.residue_types
    n_total = len(res_types)
    if n_total == 0:
        raise InvalidProteinError("Chain contains no valid residues.", code="NO_RESIDUES")

    hydrophobic_set = {"ALA", "VAL", "LEU", "ILE", "MET", "PHE", "TRP", "PRO"}
    charged_set = {"ARG", "LYS", "HIS", "ASP", "GLU"}

    n_hydro = sum(1 for r in res_types if r in hydrophobic_set)
    n_charged = sum(1 for r in res_types if r in charged_set)

    hydrophobic_fraction = n_hydro / n_total
    charged_fraction = n_charged / n_total

    meta_payload = f"{submission.pdb_id}:{submission.uniprot}:{submission.chain_id}:{n_total}"
    metadata_hash = compute_sha256(meta_payload)

    return CandidateValidationReport(
        valid=True,
        chain_id=submission.chain_id,
        n_residues=n_total,
        n_atoms_heavy=prepared.n_atoms_heavy,
        hydrophobic_fraction=hydrophobic_fraction,
        charged_fraction=charged_fraction,
        non_standard_residues_dropped=[],
        warnings=prepared.notes,
        sha256_structure_hash=structure_hash,
        sha256_metadata_hash=metadata_hash,
    )


def submit_candidate(pdb_bytes: bytes, submission: CandidateSubmission) -> dict[str, Any]:
    _ensure_dirs()

    # Check for existing candidate
    candidates = load_candidates()
    candidate_id = submission.pdb_id.upper()
    existing = next((c for c in candidates if c["candidate_id"] == candidate_id), None)
    if existing and existing.get("review_state") == "approved":
        raise ValidationFailedError(
            f"Candidate '{candidate_id}' is already an approved library protein.",
            code="ALREADY_APPROVED",
        )

    val_report = validate_candidate_structure(pdb_bytes, submission)

    # Store structure in candidates_pdb
    pdb_path = CANDIDATES_PDB_DIR / f"{candidate_id}.pdb"
    pdb_path.write_bytes(pdb_bytes)

    # Calculate MW estimate (~110 Da per AA)
    mw_estimate = val_report.n_residues * 110.0

    record = {
        "candidate_id": candidate_id,
        "pdb_id": candidate_id,
        "name": submission.name,
        "uniprot": submission.uniprot,
        "proposed_role": submission.proposed_role,
        "why_selected": submission.why_selected,
        "chain_id": submission.chain_id,
        "protein_length": val_report.n_residues,
        "molecular_weight": mw_estimate,
        "hydrophobic_fraction": val_report.hydrophobic_fraction,
        "charged_fraction": val_report.charged_fraction,
        "experiment_method": "X-Ray / AlphaFold Model",
        "resolution_angstrom": 2.0,
        "source": submission.source,
        "license_note": submission.license_note,
        "review_state": "pending",
        "submitted_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "reviewed_by": None,
        "reviewed_at": None,
        "review_notes": None,
        "sha256_structure_hash": val_report.sha256_structure_hash,
        "sha256_metadata_hash": val_report.sha256_metadata_hash,
        "structure_file": f"{candidate_id}.pdb",
    }

    # Replace or add
    candidates = [c for c in candidates if c["candidate_id"] != candidate_id]
    candidates.append(record)
    save_candidates(candidates)

    logger.info("Candidate '%s' submitted for review.", candidate_id)
    return record


def list_candidates(state: str | None = None) -> list[dict[str, Any]]:
    candidates = load_candidates()
    if state:
        state_lower = state.lower()
        candidates = [c for c in candidates if c.get("review_state") == state_lower]
    return candidates


def review_candidate(action: CandidateReviewAction) -> dict[str, Any]:
    _ensure_dirs()
    candidates = load_candidates()
    candidate_id = action.candidate_id.upper()
    record = next((c for c in candidates if c["candidate_id"] == candidate_id), None)
    if not record:
        raise NotFoundError(f"Candidate '{candidate_id}' not found.", code="CANDIDATE_NOT_FOUND")

    new_state = "approved" if action.action == "approve" else "rejected"
    record["review_state"] = new_state
    record["reviewed_by"] = action.reviewer
    record["reviewed_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    record["review_notes"] = action.notes

    save_candidates(candidates)

    if new_state == "approved":
        # Copy PDB to official library data/proteins/pdb
        src_pdb = CANDIDATES_PDB_DIR / f"{candidate_id}.pdb"
        dst_pdb = settings.pdb_dir / f"{candidate_id}.pdb"
        if src_pdb.exists():
            settings.pdb_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_pdb, dst_pdb)

        # Append to official proteins.json
        meta_json_path = settings.protein_metadata_dir / "proteins.json"
        if meta_json_path.exists():
            doc = json.loads(meta_json_path.read_text(encoding="utf-8"))
            approved_list = doc.get("approved_proteins", [])
            # Remove any duplicate
            approved_list = [p for p in approved_list if p["pdb_id"] != candidate_id]
            approved_entry = {
                "pdb_id": candidate_id,
                "name": record["name"],
                "uniprot": record["uniprot"],
                "proposed_role": record["proposed_role"],
                "why_selected": record["why_selected"],
                "experiment_method": record["experiment_method"],
                "resolution_angstrom": record["resolution_angstrom"],
                "deposited": datetime.datetime.now(datetime.timezone.utc).strftime("%d-%b-%Y").upper(),
                "n_models_in_file": 1,
                "pdb_title": f"{record['name']} (Onboarded Candidate)",
                "chain_id": record["chain_id"],
                "protein_length": record["protein_length"],
                "molecular_weight": record["molecular_weight"],
                "hydrophobic_fraction": record["hydrophobic_fraction"],
                "charged_fraction": record["charged_fraction"],
                "n_reference_residues": record["protein_length"],
                "ml_dataset_split": "train",
                "structure_file": f"{candidate_id}.pdb",
                "source": record["source"],
                "license_note": record["license_note"],
                "sha256_structure_hash": record["sha256_structure_hash"],
                "sha256_metadata_hash": record["sha256_metadata_hash"],
            }
            approved_list.append(approved_entry)
            doc["approved_proteins"] = approved_list
            meta_json_path.write_text(json.dumps(doc, indent=2), encoding="utf-8")

            # Clear memory cache so API immediately reflects the newly approved protein
            from app.services import protein_service
            protein_service.clear_protein_cache()

    logger.info("Candidate '%s' reviewed: %s by %s.", candidate_id, new_state, action.reviewer)
    return record
