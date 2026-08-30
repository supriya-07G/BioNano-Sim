"""Pydantic schemas for paired mechanical experiments API."""

from __future__ import annotations

from typing import Annotated, Any, Literal
from pydantic import BaseModel, ConfigDict, Field

from app.contracts.paired_experiment import (
    ExperimentStatus,
    ProxyType,
    ResidueId,
    SeverityLabel,
    StiffnessFit,
    StiffnessUnit,
)

ExperimentCondition = Literal[
    "baseline", "damaged", "pristine",
    "baseline_prepared", "damaged_prepared",
    "baseline_topology", "damaged_topology",
]


class ForceExtensionDataPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    time_ps: float
    restraint_center_nm: float
    end_to_end_nm: float
    extension_nm: float
    force_pn: float
    work_kj_mol: float
    potential_energy_kj_mol: float


class PairedForceExtensionResponse(BaseModel):
    experiment_id: str
    stiffness_unit: StiffnessUnit = "pN/nm"
    baseline: list[ForceExtensionDataPoint] = Field(default_factory=list)
    damaged: list[ForceExtensionDataPoint] = Field(default_factory=list)


class ExperimentSummary(BaseModel):
    model_config = ConfigDict(extra="allow")

    experiment_id: str
    protein_id: str
    pdb_id: str
    chain_id: str
    scenario_id: str
    status: ExperimentStatus
    severity_label: SeverityLabel
    damage_residue_id: str
    residue_type: str
    baseline_stiffness: float | None = None
    damaged_stiffness: float | None = None
    stiffness_unit: StiffnessUnit = "pN/nm"
    mechanical_degradation_pct: float | None = None
    random_seed: int
    is_synthetic: bool = False
    qc_failures: list[str] = Field(default_factory=list)


class ExperimentDetail(BaseModel):
    model_config = ConfigDict(extra="allow")

    experiment_id: str
    schema_version: str
    status: ExperimentStatus
    protein_id: str
    pdb_id: str
    chain_id: str
    uniprot_id: str | None = None

    scenario_id: str
    scenario_version: str | None = None

    damage_residue_id: str
    residue_type: str
    residue_index_norm: float | None = None
    proxy_type: ProxyType = "SIDE_CHAIN_LOSS"
    proxy_rank: int | None = None
    severity_label: SeverityLabel
    n_residues_damaged: int
    damage_residue_ids: list[str]
    n_side_chain_atoms_removed: int | None = None
    severity_is_a_dose: Literal[False] = False
    severity_note: str | None = None
    ineligible_candidates: list[dict[str, Any]] = Field(default_factory=list)

    random_seed: int
    sim_config_hash: str
    git_commit: str | None = None
    structure_sha256: str | None = None
    damaged_structure_sha256: str | None = None
    is_synthetic: bool = False

    baseline_stiffness: float | None = None
    damaged_stiffness: float | None = None
    stiffness_unit: StiffnessUnit = "pN/nm"
    fit_quality: float | None = None
    baseline_fit: StiffnessFit | None = None
    damaged_fit: StiffnessFit | None = None
    mechanical_degradation_pct: float | None = None
    degradation_definition: str | None = None

    baseline_rmsd_mean: float | None = None
    baseline_rmsd_std: float | None = None
    baseline_rg_mean: float | None = None
    baseline_rg_std: float | None = None
    baseline_contact_mean: float | None = None
    baseline_hbond_mean: float | None = None
    damaged_rmsd_mean: float | None = None

    structural_analysis: dict[str, Any] | None = None

    qc_failures: list[str] = Field(default_factory=list)
    quality_status: str = "valid"
    artifacts: dict[str, bool] = Field(default_factory=dict)


class ExperimentImportRequest(BaseModel):
    source_path: str = Field(description="Directory path of the experiment to import")
    experiment_id: str | None = Field(default=None, description="Optional override for experiment ID")


class ExperimentImportResponse(BaseModel):
    experiment_id: str
    status: str
    message: str
    detail: ExperimentDetail
