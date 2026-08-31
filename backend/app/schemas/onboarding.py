"""Pydantic schemas for curated protein library candidate onboarding."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

ReviewState = Literal["pending", "approved", "rejected"]


class CandidateSubmission(BaseModel):
    pdb_id: str = Field(..., description="Unique 4-character PDB ID or candidate identifier.", json_schema_extra={"example": "2F4K"})
    name: str = Field(..., description="Descriptive protein name.", json_schema_extra={"example": "Barnase ribonuclease domain"})
    uniprot: str = Field(..., description="UniProt Accession ID.", json_schema_extra={"example": "P00648"})
    proposed_role: str = Field(..., description="Proposed mechanical or structural role in nanomachinery.")
    why_selected: str = Field(..., description="Scientific rationale for candidate selection.")
    chain_id: str = Field("A", description="Chain ID to extract and validate.")
    source: str = Field("RCSB PDB (files.rcsb.org)", description="Source repository or database.")
    license_note: str = Field(
        "PDB coordinate data is distributed by RCSB PDB under CC0 1.0 Universal.",
        description="Licensing attribution.",
    )


class CandidateReviewAction(BaseModel):
    candidate_id: str = Field(..., description="Candidate identifier.")
    action: Literal["approve", "reject"] = Field(..., description="Review decision.")
    reviewer: str = Field(..., description="Reviewer handle or name.")
    notes: str = Field("", description="Review notes or feedback.")


class CandidateValidationReport(BaseModel):
    valid: bool
    chain_id: str
    n_residues: int
    n_atoms_heavy: int
    hydrophobic_fraction: float
    charged_fraction: float
    non_standard_residues_dropped: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    sha256_structure_hash: str
    sha256_metadata_hash: str


class CandidateRecord(BaseModel):
    candidate_id: str
    pdb_id: str
    name: str
    uniprot: str
    proposed_role: str
    why_selected: str
    chain_id: str
    protein_length: int
    molecular_weight: float
    hydrophobic_fraction: float
    charged_fraction: float
    experiment_method: str
    resolution_angstrom: float | None
    source: str
    license_note: str
    review_state: ReviewState
    submitted_at: str
    reviewed_by: str | None = None
    reviewed_at: str | None = None
    review_notes: str | None = None
    sha256_structure_hash: str
    sha256_metadata_hash: str
    structure_file: str
