"""Unit tests for the curated protein candidate onboarding workflow (#34)."""

import json
from pathlib import Path

import pytest

from app.core.exceptions import InvalidProteinError
from app.schemas.onboarding import CandidateReviewAction, CandidateSubmission
from app.services import protein_onboarding_service


@pytest.fixture
def sample_pdb_bytes() -> bytes:
    """Read a real sample PDB (1UBQ.pdb) for testing onboarding."""
    path = Path(__file__).resolve().parents[2] / "data" / "proteins" / "pdb" / "1UBQ.pdb"
    return path.read_bytes()


def test_submit_valid_candidate(sample_pdb_bytes: bytes, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    meta_dir = tmp_path / "metadata"
    candidates_dir = tmp_path / "candidates_pdb"
    monkeypatch.setattr(protein_onboarding_service, "CANDIDATES_JSON", meta_dir / "candidates.json")
    monkeypatch.setattr(protein_onboarding_service, "CANDIDATES_PDB_DIR", candidates_dir)

    submission = CandidateSubmission(
        pdb_id="2F4K",
        name="Barnase ribonuclease domain",
        uniprot="P00648",
        proposed_role="Rigid structural connector",
        why_selected="High-resolution bacterial ribonuclease domain used as a mechanical reference.",
        chain_id="A",
    )

    record = protein_onboarding_service.submit_candidate(sample_pdb_bytes, submission)

    assert record["candidate_id"] == "2F4K"
    assert record["review_state"] == "pending"
    assert record["protein_length"] == 76
    assert record["sha256_structure_hash"] is not None
    assert record["sha256_metadata_hash"] is not None
    assert (candidates_dir / "2F4K.pdb").exists()

    candidates = protein_onboarding_service.list_candidates("pending")
    assert len(candidates) == 1
    assert candidates[0]["pdb_id"] == "2F4K"


def test_validation_rejects_empty_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    meta_dir = tmp_path / "metadata"
    candidates_dir = tmp_path / "candidates_pdb"
    monkeypatch.setattr(protein_onboarding_service, "CANDIDATES_JSON", meta_dir / "candidates.json")
    monkeypatch.setattr(protein_onboarding_service, "CANDIDATES_PDB_DIR", candidates_dir)

    submission = CandidateSubmission(
        pdb_id="TEST",
        name="Empty Test",
        uniprot="N/A",
        proposed_role="None",
        why_selected="Testing empty file validation",
        chain_id="A",
    )

    with pytest.raises(InvalidProteinError) as exc_info:
        protein_onboarding_service.submit_candidate(b"", submission)
    assert "empty" in str(exc_info.value).lower()


def test_validation_rejects_missing_chain(sample_pdb_bytes: bytes, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    meta_dir = tmp_path / "metadata"
    candidates_dir = tmp_path / "candidates_pdb"
    monkeypatch.setattr(protein_onboarding_service, "CANDIDATES_JSON", meta_dir / "candidates.json")
    monkeypatch.setattr(protein_onboarding_service, "CANDIDATES_PDB_DIR", candidates_dir)

    submission = CandidateSubmission(
        pdb_id="TEST",
        name="Missing Chain Test",
        uniprot="N/A",
        proposed_role="None",
        why_selected="Testing chain missing validation",
        chain_id="Z",  # Non-existent chain
    )

    with pytest.raises(InvalidProteinError):
        protein_onboarding_service.submit_candidate(sample_pdb_bytes, submission)


def test_review_approve_candidate(sample_pdb_bytes: bytes, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    data_dir = tmp_path / "data"
    meta_dir = data_dir / "proteins" / "metadata"
    meta_dir.mkdir(parents=True, exist_ok=True)
    proteins_json = meta_dir / "proteins.json"
    proteins_json.write_text(json.dumps({"approved_proteins": []}), encoding="utf-8")

    pdb_dir = data_dir / "proteins" / "pdb"
    candidates_dir = data_dir / "proteins" / "candidates_pdb"

    monkeypatch.setattr(protein_onboarding_service, "CANDIDATES_JSON", meta_dir / "candidates.json")
    monkeypatch.setattr(protein_onboarding_service, "CANDIDATES_PDB_DIR", candidates_dir)
    monkeypatch.setattr(protein_onboarding_service.settings, "data_dir", data_dir)

    submission = CandidateSubmission(
        pdb_id="2F4K",
        name="Barnase ribonuclease domain",
        uniprot="P00648",
        proposed_role="Rigid structural connector",
        why_selected="High-resolution bacterial ribonuclease domain.",
        chain_id="A",
    )
    protein_onboarding_service.submit_candidate(sample_pdb_bytes, submission)

    # Approve candidate
    review_action = CandidateReviewAction(
        candidate_id="2F4K",
        action="approve",
        reviewer="supriya-07G",
        notes="Validated structure, standard residues confirmed.",
    )
    approved_record = protein_onboarding_service.review_candidate(review_action)

    assert approved_record["review_state"] == "approved"
    assert approved_record["reviewed_by"] == "supriya-07G"
    assert (pdb_dir / "2F4K.pdb").exists()

    # Check official proteins.json
    doc = json.loads(proteins_json.read_text(encoding="utf-8"))
    approved_list = doc["approved_proteins"]
    assert len(approved_list) == 1
    assert approved_list[0]["pdb_id"] == "2F4K"


def test_review_reject_candidate(sample_pdb_bytes: bytes, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    meta_dir = tmp_path / "metadata"
    candidates_dir = tmp_path / "candidates_pdb"

    monkeypatch.setattr(protein_onboarding_service, "CANDIDATES_JSON", meta_dir / "candidates.json")
    monkeypatch.setattr(protein_onboarding_service, "CANDIDATES_PDB_DIR", candidates_dir)

    submission = CandidateSubmission(
        pdb_id="REJ1",
        name="Rejected Candidate",
        uniprot="N/A",
        proposed_role="Test",
        why_selected="Testing rejection",
        chain_id="A",
    )
    protein_onboarding_service.submit_candidate(sample_pdb_bytes, submission)

    review_action = CandidateReviewAction(
        candidate_id="REJ1",
        action="reject",
        reviewer="vaishnaviPR-hash",
        notes="Missing critical domain annotations.",
    )
    rejected_record = protein_onboarding_service.review_candidate(review_action)

    assert rejected_record["review_state"] == "rejected"
    assert rejected_record["reviewed_by"] == "vaishnaviPR-hash"
