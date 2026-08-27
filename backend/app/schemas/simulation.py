"""Simulation job schemas: presets, submission, status and results."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def is_terminal(self) -> bool:
        return self in {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}


class JobStage(str, Enum):
    """The eight reported stages (spec 5D). Order is significant."""

    INPUT_VALIDATION = "input_validation"
    PROTEIN_PREPARATION = "protein_preparation"
    SYSTEM_CONSTRUCTION = "system_construction"
    ENERGY_MINIMIZATION = "energy_minimization"
    EQUILIBRATION = "equilibration"
    PRODUCTION = "production"
    TRAJECTORY_ANALYSIS = "trajectory_analysis"
    REPORT_GENERATION = "report_generation"


STAGE_ORDER: list[JobStage] = list(JobStage)

STAGE_LABELS: dict[str, str] = {
    JobStage.INPUT_VALIDATION: "Input validation",
    JobStage.PROTEIN_PREPARATION: "Protein preparation",
    JobStage.SYSTEM_CONSTRUCTION: "System construction",
    JobStage.ENERGY_MINIMIZATION: "Energy minimization",
    JobStage.EQUILIBRATION: "Equilibration",
    JobStage.PRODUCTION: "Production steps",
    JobStage.TRAJECTORY_ANALYSIS: "Trajectory analysis",
    JobStage.REPORT_GENERATION: "Report generation",
}


class SimulationPreset(BaseModel):
    preset_id: str
    label: str
    summary: str
    platform: str
    solvent: str
    forcefield: list[str] = Field(default_factory=list)
    constraints: str | None = None
    nonbonded_cutoff_nm: float = Field(
        default=0.0,
        description="Nonbonded cutoff in nm. Implicit-solvent GBn2 with no cutoff is "
                    "~8x slower; the cutoff neglects long-range electrostatics.",
    )
    production_steps: int
    equilibration_steps: int
    minimisation_steps: int
    timestep_fs: float
    report_interval: int
    friction_per_ps: float
    simulated_time_ps: float = Field(
        default=0.0,
        description="(equilibration + production) steps × timestep. Picoseconds — "
                    "orders of magnitude below any real degradation timescale.",
    )
    estimated_runtime_note: str
    is_default: bool = False
    scientific_label: str = Field(
        description="How results from this preset must be labelled in the UI."
    )
    limitations: list[str] = Field(default_factory=list)


class SimulationRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    pdb_id: str | None = None
    upload_id: str | None = None
    chain_id: str = Field(default="A", max_length=4)
    scenario_id: str
    preset_id: str = "rapid_demo"

    temperature_kelvin: float = Field(default=300.0, gt=0.0, le=1000.0)
    dose: float = Field(default=0.5, ge=0.0, le=1.0e6)
    dose_unit: Literal["Gy", "mGy", "kGy", "rad"] = "Gy"
    exposure_duration_days: float = Field(default=180.0, ge=0.0, le=100_000.0)
    mechanical_force_pn: float = Field(default=0.0, ge=0.0, le=10_000.0)
    random_seed: int = Field(default=42, ge=0, le=2**31 - 1)

    prediction_id: str | None = Field(
        default=None, description="Links this run to the ML prediction that preceded it."
    )
    ml_degradation_percent: float | None = Field(
        default=None, ge=0.0, le=100.0,
        description="The ML estimate, stored alongside the job so the results page "
                    "can compare prediction against simulation without a second call.",
    )

    @model_validator(mode="after")
    def _exactly_one_structure(self) -> SimulationRequest:
        if bool(self.pdb_id) == bool(self.upload_id):
            raise ValueError(
                "Provide exactly one of 'pdb_id' or 'upload_id'."
            )
        return self


class StageProgress(BaseModel):
    stage: JobStage
    label: str
    state: Literal["pending", "active", "done", "failed", "skipped"]
    started_at: str | None = None
    finished_at: str | None = None
    detail: str | None = None


class SimulationJobSummary(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    job_id: str
    status: JobStatus
    pdb_id: str | None
    upload_id: str | None
    chain_id: str
    scenario_id: str
    preset_id: str
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    duration_seconds: float | None = None
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    current_stage: JobStage | None = None
    ml_degradation_percent: float | None = None
    simulation_degradation_proxy_percent: float | None = None
    engine: str = Field(
        default="openmm",
        description="'openmm' for a live run, 'precomputed' for the labelled fallback.",
    )
    error_code: str | None = None
    error_message: str | None = None


class SimulationJobDetail(SimulationJobSummary):
    request: dict[str, Any] = Field(default_factory=dict)
    stages: list[StageProgress] = Field(default_factory=list)
    steps_completed: int = 0
    steps_total: int = 0
    elapsed_seconds: float = 0.0
    temperature_kelvin: float | None = None
    potential_energy_kj_mol: float | None = None
    log_tail: list[str] = Field(default_factory=list)
    reproducibility: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    retry_hint: dict[str, Any] | None = None
    artifacts: dict[str, bool] = Field(default_factory=dict)


class SeriesPoint(BaseModel):
    x: float
    y: float


class SimulationResults(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    job_id: str
    status: JobStatus
    engine: str
    result_label: str = Field(
        description="Exact scientific label for this result, e.g. "
        "'Rapid OpenMM Simulation' or 'Precomputed OpenMM Result'."
    )
    metrics: dict[str, Any] = Field(default_factory=dict)
    series: dict[str, list[dict[str, float]]] = Field(default_factory=dict)
    rmsf: list[dict[str, Any]] = Field(default_factory=list)
    highest_mobility_residues: list[dict[str, Any]] = Field(default_factory=list)
    stability_summary: dict[str, Any] = Field(default_factory=dict)
    comparison: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    reproducibility: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
