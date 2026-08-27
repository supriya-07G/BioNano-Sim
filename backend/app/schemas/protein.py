"""Protein registry and upload response schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ChainSummary(BaseModel):
    chain_id: str
    n_residues: int = Field(description="Standard amino acids carrying a Cα atom.")
    n_atoms: int
    first_residue: int | None = None
    last_residue: int | None = None
    is_default: bool = False


class ProteinSummary(BaseModel):
    """Registry listing entry."""

    model_config = ConfigDict(protected_namespaces=())

    pdb_id: str
    name: str
    uniprot: str | None = None
    proposed_role: str
    chain_id: str
    protein_length: int
    molecular_weight: float
    experiment_method: str | None = None
    resolution_angstrom: float | None = None
    ml_dataset_split: str = Field(
        description="Which split of the mock model's data this protein was in: "
        "train, validation or test. A protein in 'train' will look optimistically "
        "accurate; 1UBQ (validation) and 1TEN (test) are the honest held-out cases."
    )
    is_rapid_demo_default: bool = False


class ProteinDetail(ProteinSummary):
    why_selected: str
    hydrophobic_fraction: float
    charged_fraction: float
    n_reference_residues: int
    deposited: str | None = None
    pdb_title: str | None = None
    n_models_in_file: int = 1
    source: str
    license_note: str
    chains: list[ChainSummary] = Field(default_factory=list)
    feature_source: str = Field(
        default="reference_table",
        description="'reference_table' means features come from the exact table "
        "the model was trained on; 'recomputed' means they were derived from the "
        "structure and are approximate.",
    )
    candidate_residues: list[dict[str, Any]] = Field(
        default_factory=list,
        description="The ranked candidate residues used for ML prediction.",
    )


class UploadedProtein(BaseModel):
    upload_id: str
    filename: str
    size_bytes: int
    n_models: int
    chains: list[ChainSummary]
    default_chain: str
    n_atoms: int
    n_residues: int
    warnings: list[str] = Field(default_factory=list)
    feature_source: str = "recomputed"
    expires_note: str = (
        "Uploaded structures live in runtime/uploads and are not committed to git. "
        "Remove them with `make clean` or scripts/clean_runtime.py."
    )
