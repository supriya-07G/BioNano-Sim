"""Multi-Objective Candidate Ranking Schemas (#30).

The objectives here are exactly those the measured dataset can support. Two
earlier ones -- SASA preservation and an out-of-domain distance -- were dropped
rather than kept and filled with constants: an objective nothing measures is a
weight the user can move for no effect, which is worse than an absent control
because it looks like it works.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field


class RankingWeights(BaseModel):
    """User-adjustable weights for multi-objective candidate ranking."""

    stiffness_retention: float = Field(
        default=0.40,
        ge=0.0,
        le=1.0,
        description="Weight for % of baseline stiffness retained after damage",
    )
    baseline_strength: float = Field(
        default=0.30,
        ge=0.0,
        le=1.0,
        description="Weight for measured pristine stiffness (pN/nm)",
    )
    measurement_confidence: float = Field(
        default=0.30,
        ge=0.0,
        le=1.0,
        description="Weight for mean force-extension fit quality (R^2) across passing runs",
    )
    uncertainty_penalty: float = Field(
        default=0.15,
        ge=0.0,
        le=1.0,
        description="Penalty multiplier for seed-to-seed spread (SD / mean of baseline stiffness)",
    )


class CandidateObjectiveScore(BaseModel):
    """Multi-objective score breakdown for a single candidate protein."""

    rank: int | None = Field(
        ..., description="1-indexed rank position; null for unresolved candidates"
    )
    pdb_id: str = Field(..., description="PDB accession code")
    name: str = Field(..., description="Protein name")
    uniprot: str = Field(..., description="UniProt accession")

    # Measured objective metrics. Null where the domain produced no run that
    # passed the dataset's quality gate.
    baseline_stiffness_pnnm: float | None = Field(
        ..., description="Mean pristine stiffness over passing runs, pN/nm"
    )
    baseline_stiffness_sd: float | None = Field(
        ..., description="Standard deviation of pristine stiffness across seeds, pN/nm"
    )
    damaged_stiffness_pnnm: float | None = Field(
        ..., description="Mean post-damage stiffness over passing runs, pN/nm"
    )
    stiffness_retained_pct: float | None = Field(
        ..., description="Damaged stiffness as a percentage of baseline"
    )
    relative_sd: float | None = Field(
        ..., description="Seed spread as a fraction of the mean; the uncertainty term"
    )
    mean_fit_quality: float | None = Field(
        ..., description="Mean R^2 of the force-extension fit over passing runs"
    )

    runs_passing_qc: int = Field(..., description="Runs that passed the dataset quality gate")
    runs_screened: int = Field(..., description="Runs attempted for this domain")
    resolved: bool = Field(
        ..., description="True when at least one run yielded a usable elastic constant"
    )
    unresolved_reason: str | None = Field(
        default=None, description="Why no usable stiffness could be read, when resolved is false"
    )
    qc_failure_reasons: list[str] = Field(
        default_factory=list, description="Distinct rejection reasons recorded by the producer"
    )

    subscores: dict[str, float] = Field(
        default_factory=dict, description="Normalized 0..100 objective subscores"
    )
    penalties: dict[str, float] = Field(
        default_factory=dict, description="Deducted penalty points"
    )

    composite_score: float | None = Field(
        ..., description="Final composite score (0..100); null for unresolved candidates"
    )
    is_pareto_optimal: bool = Field(
        default=False, description="True if the candidate lies on the non-dominated frontier"
    )

    explanation: str = Field(..., description="Human-readable justification of score and rank")
    provenance: dict[str, Any] = Field(..., description="Measurement provenance details")


class RankingResponse(BaseModel):
    """Response payload for multi-objective candidate ranking query."""

    mode: Literal["MEASURED_STEERED_MD", "NO_MEASUREMENTS_AVAILABLE"] = Field(
        ...,
        description=(
            "MEASURED_STEERED_MD when scores come from the measured dataset; "
            "NO_MEASUREMENTS_AVAILABLE when that dataset is absent from the checkout"
        ),
    )
    total_candidates: int = Field(..., description="Number of evaluated candidates")
    ranked_candidates: int = Field(
        ..., description="Candidates with a usable measurement, and therefore a rank"
    )
    pareto_frontier_ids: list[str] = Field(
        ..., description="PDB IDs on the non-dominated Pareto frontier"
    )
    weights_used: RankingWeights = Field(..., description="Weights applied in calculation")
    dataset: dict[str, Any] = Field(
        default_factory=dict, description="Provenance of the measurements behind these scores"
    )
    candidates: list[CandidateObjectiveScore] = Field(
        ..., description="Ranked candidates first, then unresolved ones"
    )
