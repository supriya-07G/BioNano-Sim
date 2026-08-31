"""Multi-Objective Candidate Ranking Schemas (#30)."""

from typing import Any, Literal
from pydantic import BaseModel, Field


class RankingWeights(BaseModel):
    """User-adjustable weights for multi-objective candidate ranking."""

    stiffness_retention: float = Field(
        default=0.35, ge=0.0, le=1.0, description="Weight for % stiffness retained post-damage"
    )
    baseline_strength: float = Field(
        default=0.20, ge=0.0, le=1.0, description="Weight for pristine mechanical stiffness (pN/nm)"
    )
    structural_stability: float = Field(
        default=0.20, ge=0.0, le=1.0, description="Weight for SASA and hydrophobic core preservation"
    )
    uncertainty_penalty: float = Field(
        default=0.15, ge=0.0, le=1.0, description="Penalty multiplier for prediction variance (sigma)"
    )
    out_of_domain_penalty: float = Field(
        default=0.10, ge=0.0, le=1.0, description="Penalty multiplier for out-of-domain distance"
    )


class CandidateObjectiveScore(BaseModel):
    """Multi-objective score breakdown for a single candidate protein."""

    rank: int = Field(..., description="1-indexed rank position")
    pdb_id: str = Field(..., description="PDB accession code")
    name: str = Field(..., description="Protein name")
    uniprot: str = Field(..., description="UniProt accession")
    
    # Raw Objective Metrics
    baseline_stiffness_pnnm: float = Field(..., description="Pristine stiffness in pN/nm")
    damaged_stiffness_pnnm: float = Field(..., description="Damaged stiffness in pN/nm")
    stiffness_retained_pct: float = Field(..., description="Percentage of stiffness retained")
    uncertainty_sigma: float = Field(..., description="Model prediction uncertainty (sigma)")
    sasa_preservation_pct: float = Field(..., description="SASA compactness preservation %")
    ood_distance: float = Field(..., description="Out-of-domain distance metric (0 = in-domain)")
    
    # Normalized Sub-Scores (0 to 100)
    subscores: dict[str, float] = Field(..., description="Normalized 0..100 objective subscores")
    penalties: dict[str, float] = Field(..., description="Deducted penalty points")
    
    # Composite Final Score & Pareto Status
    composite_score: float = Field(..., description="Final multi-objective composite score (0..100)")
    is_pareto_optimal: bool = Field(..., description="True if candidate lies on the non-dominated Pareto frontier")
    
    explanation: str = Field(..., description="Human-readable justification of score and rank")
    provenance: dict[str, Any] = Field(..., description="Experiment & model provenance details")


class RankingResponse(BaseModel):
    """Response payload for multi-objective candidate ranking query."""

    mode: Literal["REAL_EMPIRICAL_PARETO", "MOCK_DEMO_RANKING"] = Field(
        ..., description="Execution mode: REAL_EMPIRICAL_PARETO or MOCK_DEMO_RANKING"
    )
    total_candidates: int = Field(..., description="Number of evaluated candidates")
    pareto_frontier_ids: list[str] = Field(..., description="PDB IDs on the non-dominated Pareto frontier")
    weights_used: RankingWeights = Field(..., description="Weights applied in calculation")
    candidates: list[CandidateObjectiveScore] = Field(..., description="Ranked list of candidates")
