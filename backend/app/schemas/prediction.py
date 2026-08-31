"""Prediction request/response schemas.

The request carries the full experiment configuration the user set in the UI,
but only a subset reaches the model. Fields the model cannot consume are marked
in their descriptions and echoed back in ``input_summary.not_used_by_model`` so
the interface can be explicit rather than implying a coupling that is not there.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PredictionRequest(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    # --- Structure selection -----------------------------------------------
    pdb_id: str | None = Field(
        default=None,
        description="A four-character approved PDB id. Mutually exclusive with upload_id.",
    )
    upload_id: str | None = Field(
        default=None,
        description="Id returned by POST /proteins/upload. Mutually exclusive with pdb_id.",
    )
    chain_id: str = Field(default="A", max_length=4)

    # --- Consumed by the model ---------------------------------------------
    scenario_id: str = Field(description="Must be a scenario with ml_supported=true.")

    # --- Not consumed by the model (simulation / provenance only) ----------
    dose: float = Field(
        default=0.5, ge=0.0, le=1.0e6,
        description="NOT an ML model input. Recorded for provenance and used by the "
                    "simulation's radiation-damage parameterisation.",
    )
    dose_unit: Literal["Gy", "mGy", "kGy", "rad"] = "Gy"
    exposure_duration_days: float = Field(
        default=180.0, ge=0.0, le=100_000.0,
        description="NOT an ML model input. Provenance only.",
    )
    temperature_kelvin: float = Field(
        default=300.0, gt=0.0, le=1000.0,
        description="NOT an ML model input. Sets the OpenMM thermostat temperature.",
    )
    mechanical_force_pn: float = Field(
        default=0.0, ge=0.0, le=10_000.0,
        description="NOT an ML model input. Provenance only in this MVP; no external "
                    "pulling force is applied by the Rapid Demo engine.",
    )
    random_seed: int = Field(default=42, ge=0, le=2**31 - 1)
    top_n_residues: int = Field(
        default=10, ge=1, le=50,
        description="How many ranked candidate residues to score. The model was "
                    "trained on the top 10; larger values extrapolate to less "
                    "susceptible residues than it ever saw.",
    )

    @model_validator(mode="after")
    def _exactly_one_structure(self) -> PredictionRequest:
        if bool(self.pdb_id) == bool(self.upload_id):
            raise ValueError(
                "Provide exactly one of 'pdb_id' (approved protein) or 'upload_id' "
                "(uploaded structure)."
            )
        return self


class ResiduePredictionOut(BaseModel):
    residue_id: str
    residue_type: str
    proxy_rank: float
    degradation_percent: float
    residue_sasa_norm: float
    residue_contact_count: float
    qualitative_susceptibility: str
    residue_type_in_model_vocabulary: bool


class PredictionResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    prediction_id: str
    model_version: str
    model_status: str = Field(
        description="Scientific status of the bundle, e.g. MOCK_PUBLIC_DATA_BOOTSTRAP."
    )
    degradation_percent: float = Field(
        description="Protein-level ML degradation estimate: the mean over the ranked "
                    "candidate residues. See 'aggregation' for how it is built."
    )
    risk_level: Literal["low", "moderate", "elevated", "high"]
    confidence: float | None = Field(
        default=None,
        description="Always null: the bundle exposes no calibrated uncertainty. "
                    "See held_out_error for retrospective dataset-level metrics.",
    )
    warnings: list[str]
    input_summary: dict[str, Any]
    residue_predictions: list[ResiduePredictionOut] = Field(default_factory=list)
    aggregation: dict[str, Any] = Field(default_factory=dict)
    held_out_error: dict[str, Any] = Field(default_factory=dict)
    prediction_dispersion: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Spread of the per-residue predictions behind the protein-level "
            "figure. Not a confidence interval: the bundle exposes no "
            "calibrated uncertainty, so no coverage probability applies."
        ),
    )
    applicability_domain: dict[str, Any] = Field(
        default_factory=dict,
        description="Residue-vocabulary coverage of the input. Carries no numeric score.",
    )
    nearest_neighbors: list[dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "Closest proteins in the measured dataset by scaled sequence-descriptor "
            "distance. Empty when the queried protein is not itself measured."
        ),
    )
    local_feature_attributions: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Exact tree SHAP contributions for the top-ranked candidate residue.",
    )
    global_feature_importance: dict[str, float] = Field(
        default_factory=dict,
        description="The fitted estimator's own feature importances, largest first.",
    )
    attribution_disclaimer: str | None = None


class ModelInfoResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    available: bool
    status: str = Field(description="ready | degraded | unavailable")
    model_name: str | None = None
    model_version: str
    scientific_status: str
    label_source: str | None = None
    scientifically_validated: bool = False
    approved_use: str | None = None
    created_at_utc: str | None = None
    bundle_sha256: str | None = None
    sha256_verified: bool = False
    schema_verified: bool = False
    load_error: str | None = None
    warnings: list[str] = Field(default_factory=list)
    target_column: str | None = None
    feature_order: list[str] = Field(default_factory=list)
    numeric_features: list[str] = Field(default_factory=list)
    categorical_features: list[str] = Field(default_factory=list)
    categorical_vocabulary: dict[str, list[str]] = Field(default_factory=dict)
    n_transformed_features: int | None = None
    supports_uncertainty: bool = False
    uncertainty_note: str | None = None
    validation_metrics: dict[str, Any] | None = None
    test_metrics: dict[str, Any] | None = None
    train_proteins: list[str] = Field(default_factory=list)
    validation_proteins: list[str] = Field(default_factory=list)
    test_proteins: list[str] = Field(default_factory=list)
    replacement_requirement: str | None = None
    limitations: list[str] = Field(default_factory=list)
    top_feature_importances: list[dict[str, Any]] = Field(default_factory=list)
