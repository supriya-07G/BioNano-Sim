"""Pydantic schemas for parameter sweep experiments (issue #33)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SweepStatus = Literal["PENDING", "RUNNING", "COMPLETED", "CANCELLED", "FAILED"]


class SweepConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    protein_id: str = Field(default="1UBQ", description="Target PDB/protein ID")
    chain_id: str = Field(default="A", description="Chain ID")
    scenario_id: str = Field(default="GCR_DEEP_SPACE_REFERENCE", description="Scenario ID")
    severities: list[str] = Field(default_factory=lambda: ["MILD", "MODERATE", "SEVERE"], description="List of severity levels")
    ranks: list[int] = Field(default_factory=lambda: [1], description="Candidate ranks for MILD severity")
    seeds: list[int] = Field(default_factory=lambda: [42], description="Random seed list")


class SweepCombination(BaseModel):
    model_config = ConfigDict(extra="allow")

    experiment_id: str
    protein_id: str
    severity_label: str
    proxy_rank: int
    random_seed: int
    is_duplicate: bool = False


class SweepPreviewResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    protein_id: str
    total_experiments: int
    duplicates_skipped: int
    estimated_time_seconds: float
    estimated_storage_mb: float
    max_experiments_limit: int = 50
    combinations: list[SweepCombination] = Field(default_factory=list)


class SweepItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    experiment_id: str
    severity_label: str
    proxy_rank: int
    random_seed: int
    status: str = "PENDING"
    baseline_stiffness: float | None = None
    damaged_stiffness: float | None = None
    mechanical_degradation_pct: float | None = None
    error_message: str | None = None


class SeverityResponsePoint(BaseModel):
    severity_label: str
    n_residues_damaged: int
    mean_degradation_pct: float | None = None
    std_degradation_pct: float | None = None
    n_experiments: int


class SweepDetail(BaseModel):
    model_config = ConfigDict(extra="allow")

    sweep_id: str
    status: SweepStatus
    protein_id: str
    scenario_id: str
    config: SweepConfig
    total_experiments: int
    completed_experiments: int
    failed_experiments: int
    progress_pct: float
    items: list[SweepItem] = Field(default_factory=list)
    severity_response_curves: list[SeverityResponsePoint] = Field(default_factory=list)
    created_at_utc: str
    updated_at_utc: str
