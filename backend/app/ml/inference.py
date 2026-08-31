"""Inference: validate, predict, aggregate, and report every caveat.

The single most important behaviour here is **unknown-category detection**. The
bundled ``OneHotEncoder`` was fitted with ``handle_unknown='ignore'``, so a
category the model never saw is silently encoded as an all-zero block and the
model still returns a confident-looking number. We therefore compare every
categorical value against the encoder's own vocabulary *before* predicting and
attach an explicit warning. Nothing is silently absorbed.

Aggregation is equally deliberate. The model's target is per-residue
(``mechanical_degradation_pct`` for one candidate residue), so a protein-level
percentage is something this application constructs, not something the model
outputs. We use the mean over the ranked candidates and say so — and note that
because those candidates are the *most* susceptible residues, the mean is an
upper-leaning indicator for the chain rather than a whole-chain average.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from app.analysis import measured_stiffness
from app.core.exceptions import ModelUnavailableError, PredictionError
from app.core.logging import get_logger
from app.ml import explainability
from app.ml.feature_schema import FeatureSchema
from app.ml.loader import ModelState

logger = get_logger("COSMORA.ml.inference")

MVP_DISCLAIMER = (
    "MVP estimate; not experimentally validated. Labels are a synthetic "
    "public-data proxy (SYNTHETIC_PUBLIC_DATA_PROXY), not measured degradation."
)

# Band edges are the quartiles of the mock dataset's own target distribution
# (n=450: min 34.13, Q1 46.23, median 52.34, Q3 58.91, max 78.29). Using the
# training distribution rather than invented thresholds means a "high" reading
# genuinely says "in the worst quartile of what this model has ever produced".
# These are still presentational bands, NOT experimental damage criteria.
RISK_BANDS: tuple[tuple[float, str], ...] = (
    (46.23, "low"),
    (52.34, "moderate"),
    (58.91, "elevated"),
    (float("inf"), "high"),
)

RISK_BAND_BASIS = (
    "Bands are the quartiles of the mock model's own training target distribution "
    "(Q1 46.23 %, median 52.34 %, Q3 58.91 % over 450 rows). A 'high' reading means "
    "the estimate sits in the top quartile of values this model produces — it is not "
    "an experimental damage criterion."
)


def risk_level(percent: float) -> str:
    """Band a degradation percentage against the training-target quartiles."""
    for upper, label in RISK_BANDS:
        if percent < upper:
            return label
    return "high"


@dataclass
class ResiduePrediction:
    residue_id: str
    residue_type: str
    proxy_rank: float
    degradation_percent: float
    residue_sasa_norm: float
    residue_contact_count: float
    qualitative_susceptibility: str
    in_vocabulary: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "residue_id": self.residue_id,
            "residue_type": self.residue_type,
            "proxy_rank": self.proxy_rank,
            "degradation_percent": round(self.degradation_percent, 4),
            "residue_sasa_norm": round(self.residue_sasa_norm, 6),
            "residue_contact_count": self.residue_contact_count,
            "qualitative_susceptibility": self.qualitative_susceptibility,
            "residue_type_in_model_vocabulary": self.in_vocabulary,
        }


@dataclass
class ApplicabilityDomain:
    """Whether an input is one the model was trained to handle.

    Carries no numeric score. The bundle ships no training feature matrix, so
    the only membership test it genuinely supports is vocabulary coverage; a
    0-to-1 "domain score" would be a number with nothing behind it.
    """

    classification: str  # IN_VOCABULARY, CAUTION, OUT_OF_DOMAIN
    basis: str
    reasons: list[str]
    note: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "classification": self.classification,
            "basis": self.basis,
            "reasons": self.reasons,
            "note": self.note,
        }


ATTRIBUTION_DISCLAIMER = explainability.ATTRIBUTION_DISCLAIMER


@dataclass
class PredictionResult:
    prediction_id: str
    model_version: str
    model_status: str
    degradation_percent: float
    risk_level: str
    confidence: dict[str, Any] | None
    warnings: list[str]
    input_summary: dict[str, Any]
    residue_predictions: list[ResiduePrediction] = field(default_factory=list)
    aggregation: dict[str, Any] = field(default_factory=dict)
    held_out_error: dict[str, Any] = field(default_factory=dict)
    prediction_dispersion: dict[str, Any] = field(default_factory=dict)
    applicability_domain: dict[str, Any] = field(default_factory=dict)
    nearest_neighbors: list[dict[str, Any]] = field(default_factory=list)
    local_feature_attributions: list[dict[str, Any]] = field(default_factory=list)
    global_feature_importance: dict[str, float] = field(default_factory=dict)
    attribution_disclaimer: str = ATTRIBUTION_DISCLAIMER

    def as_dict(self) -> dict[str, Any]:
        return {
            "prediction_id": self.prediction_id,
            "model_version": self.model_version,
            "model_status": self.model_status,
            "degradation_percent": round(self.degradation_percent, 4),
            "risk_level": self.risk_level,
            "confidence": self.confidence,
            "warnings": self.warnings,
            "input_summary": self.input_summary,
            "residue_predictions": [r.as_dict() for r in self.residue_predictions],
            "aggregation": self.aggregation,
            "held_out_error": self.held_out_error,
            "prediction_dispersion": self.prediction_dispersion,
            "applicability_domain": self.applicability_domain,
            "nearest_neighbors": self.nearest_neighbors,
            "local_feature_attributions": self.local_feature_attributions,
            "global_feature_importance": self.global_feature_importance,
            "attribution_disclaimer": self.attribution_disclaimer,
        }


# --------------------------------------------------------------------------- #
# Validation
# --------------------------------------------------------------------------- #
def check_unknown_categories(frame, schema: FeatureSchema) -> list[dict[str, Any]]:
    """Find categorical values outside the encoder's fitted vocabulary."""
    findings: list[dict[str, Any]] = []
    for column in schema.categorical_features:
        if column not in frame.columns:
            continue
        allowed = set(schema.allowed_values(column))
        seen = {str(v) for v in frame[column].dropna().unique()}
        unknown = sorted(seen - allowed)
        if unknown:
            findings.append(
                {
                    "column": column,
                    "unknown_values": unknown,
                    "allowed_values": sorted(allowed),
                }
            )
    return findings


def check_numeric_bounds(frame, schema: FeatureSchema) -> tuple[list[str], list[str]]:
    """Split numeric problems into hard-bound violations and envelope notices."""
    hard_errors: list[str] = []
    envelope_notes: list[str] = []
    for column in schema.numeric_features:
        if column not in frame.columns:
            hard_errors.append(f"Required numeric feature '{column}' is missing.")
            continue
        series = frame[column]
        values = series.dropna().astype(float)
        if values.empty:
            continue

        bounds = schema.hard_bounds(column)
        if bounds is not None:
            bad = values[(values < bounds.min) | (values > bounds.max)]
            if not bad.empty:
                hard_errors.append(
                    f"'{column}' has {len(bad)} value(s) outside the admissible "
                    f"range [{bounds.min}, {bounds.max}] (e.g. {bad.iloc[0]})."
                )

        env = schema.train_envelope(column)
        if env is not None:
            out = values[(values < env.min) | (values > env.max)]
            if not out.empty:
                envelope_notes.append(
                    f"'{column}' has {len(out)} value(s) outside the training "
                    f"envelope [{env.min:.4g}, {env.max:.4g}] "
                    f"(min {values.min():.4g}, max {values.max():.4g}). "
                    "Gradient-boosted trees do not extrapolate, so the estimate "
                    "is effectively clipped to behaviour learned at the boundary."
                )
    return hard_errors, envelope_notes


def validate_frame(frame, schema: FeatureSchema) -> dict[str, Any]:
    """Full pre-flight check. Raises on hard failures, returns soft warnings."""
    missing = [c for c in schema.feature_order if c not in frame.columns]
    if missing:
        raise PredictionError(
            "Feature frame is missing required columns.",
            details=[{"missing_features": missing}],
        )
    unexpected = [c for c in frame.columns if c not in schema.feature_order]
    if unexpected:
        raise PredictionError(
            "Feature frame contains unexpected columns.",
            details=[{"unexpected_features": unexpected}],
        )
    if frame.empty:
        raise PredictionError("Feature frame contains no rows to predict on.")

    hard_errors, envelope_notes = check_numeric_bounds(frame, schema)
    if hard_errors:
        raise PredictionError(
            "One or more numeric features are outside their admissible range.",
            details=hard_errors,
        )

    return {
        "unknown_categories": check_unknown_categories(frame, schema),
        "envelope_notes": envelope_notes,
    }


# --------------------------------------------------------------------------- #
# Prediction
# --------------------------------------------------------------------------- #
def predict_residues(
    state: ModelState, frame, *, extra_warnings: list[str] | None = None
) -> tuple[np.ndarray, list[str], list[dict[str, Any]]]:
    """Run the pipeline and collect every caveat. Returns (values, warnings, unknowns)."""
    if not state.available or state.pipeline is None or state.schema is None:
        raise ModelUnavailableError(
            state.load_error
            or "The ML model bundle is not loaded, so predictions are unavailable."
        )

    schema = state.schema
    checks = validate_frame(frame, schema)
    warnings_out: list[str] = [MVP_DISCLAIMER]
    warnings_out.extend(extra_warnings or [])

    for finding in checks["unknown_categories"]:
        warnings_out.append(
            f"Unknown category in '{finding['column']}': "
            f"{', '.join(finding['unknown_values'])}. The bundled OneHotEncoder "
            "was fitted with handle_unknown='ignore', so these rows are encoded "
            "as an all-zero block for that feature — the model has no information "
            "about them and the estimate for those rows is unreliable. "
            f"Trained values: {', '.join(finding['allowed_values'])}."
        )
    warnings_out.extend(checks["envelope_notes"])

    try:
        raw = np.asarray(state.pipeline.predict(frame), dtype=float).ravel()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Pipeline prediction failed")
        raise PredictionError(
            f"The model pipeline failed to produce a prediction: "
            f"{type(exc).__name__}: {exc}"
        ) from exc

    if raw.shape[0] != len(frame):
        raise PredictionError(
            f"Model returned {raw.shape[0]} values for {len(frame)} input rows."
        )
    if not np.all(np.isfinite(raw)):
        raise PredictionError("Model returned non-finite values.")

    clamp = schema.clamp
    clamped = np.clip(raw, clamp.min, clamp.max)
    n_clamped = int((clamped != raw).sum())
    if n_clamped:
        warnings_out.append(
            f"{n_clamped} raw prediction(s) fell outside [{clamp.min}, {clamp.max}] % "
            "and were clamped, because the target is a percentage. Raw range was "
            f"[{raw.min():.4f}, {raw.max():.4f}]."
        )

    target_range = schema.target_train_range
    outside = clamped[(clamped < target_range.min) | (clamped > target_range.max)]
    if outside.size:
        warnings_out.append(
            f"{outside.size} estimate(s) fall outside the training target range "
            f"[{target_range.min:.2f}, {target_range.max:.2f}] %."
        )

    if not state.sha256_verified:
        warnings_out.append(
            "Model bundle integrity was not confirmed against release_manifest.json."
        )
    if not state.schema_verified:
        warnings_out.append(
            "The feature schema could not be verified against the loaded pipeline."
        )
    warnings_out.extend(state.warnings)

    return clamped, warnings_out, checks["unknown_categories"]


def aggregate_prediction(
    state: ModelState,
    frame,
    candidates: list[dict[str, Any]],
    *,
    input_summary: dict[str, Any],
    extra_warnings: list[str] | None = None,
) -> PredictionResult:
    """Predict per candidate residue, then aggregate to one protein-level figure."""
    values, warnings_out, unknowns = predict_residues(
        state, frame, extra_warnings=extra_warnings
    )
    schema = state.schema
    assert schema is not None  # predict_residues raises otherwise

    vocab = set(schema.allowed_values("residue_type"))
    residue_predictions = [
        ResiduePrediction(
            residue_id=c["residue_id"],
            residue_type=c["residue_type"],
            proxy_rank=float(c["proxy_rank"]),
            degradation_percent=float(v),
            residue_sasa_norm=float(c["residue_sasa_norm"]),
            residue_contact_count=float(c["residue_contact_count"]),
            qualitative_susceptibility=c["qualitative_susceptibility"],
            in_vocabulary=c["residue_type"] in vocab,
        )
        for c, v in zip(candidates, values, strict=True)
    ]

    # Rows whose residue_type was unknown carry no residue identity signal.
    # They stay in the reported list (transparency) but are excluded from the
    # headline mean so one all-zero encoding cannot skew the summary.
    trusted = np.array([v for r, v in zip(residue_predictions, values, strict=True) if r.in_vocabulary])
    used = trusted if trusted.size else values
    excluded = len(values) - int(used.size)

    mean = float(used.mean())
    aggregation = {
        "method": "mean_over_ranked_candidate_residues",
        "risk_band_basis": RISK_BAND_BASIS,
        "explanation": (
            "The model's target is per-residue degradation of a single candidate "
            "residue. This protein-level figure is the arithmetic mean over the "
            f"{len(values)} highest-susceptibility candidate residues (proxy_rank "
            "1..N), computed by COSMORA rather than emitted by the model. "
            "Because those residues are the most susceptible in the chain, the "
            "mean is an upper-leaning indicator, not a whole-chain average."
        ),
        "n_residues_predicted": len(values),
        "n_residues_used_in_mean": int(used.size),
        "n_residues_excluded_unknown_type": excluded,
        "per_residue_min": round(float(used.min()), 4),
        "per_residue_max": round(float(used.max()), 4),
        "per_residue_std": round(float(used.std(ddof=0)), 4),
        "whole_chain_mean_note": (
            "A whole-chain mean is not available: the model was trained only on "
            "top-ranked candidate residues, so applying it to every residue would "
            "be an unsupported extrapolation."
        ),
    }
    if excluded:
        aggregation["exclusion_note"] = (
            f"{excluded} residue(s) were excluded from the mean because their "
            "residue_type is outside the model's 14-value vocabulary. Their "
            "individual estimates are still reported."
        )

    metadata = state.metadata or {}
    held_out = {
        "supported": False,
        "note": schema.uncertainty_note,
        "validation": metadata.get("validation_metrics"),
        "test": metadata.get("test_metrics"),
    }

    # --- Explainability payload (#31) ---
    # Every field below is computed from the fitted model or the measured
    # dataset. See app/ml/explainability.py for why that matters here.
    uncertainty = explainability.dispersion(used, mean)

    # Applicability domain. The only membership test this bundle actually
    # supports is its residue vocabulary: a residue type it never saw is
    # genuinely outside the domain. Anything finer -- a distance to the
    # training manifold -- would need the training features, and the bundle
    # does not carry them, so no numeric domain score is invented.
    domain_reasons: list[str] = []
    if excluded > 0:
        domain_reasons.append(
            f"{excluded} candidate residue(s) fall outside the model's "
            f"{len(schema.residue_vocabulary) if getattr(schema, 'residue_vocabulary', None) else 14}"
            "-value residue vocabulary and were dropped from the mean."
        )
    if extra_warnings:
        domain_reasons.extend(extra_warnings)

    if excluded and excluded >= len(values) / 2:
        domain_classif = "OUT_OF_DOMAIN"
    elif domain_reasons:
        domain_classif = "CAUTION"
    else:
        domain_classif = "IN_VOCABULARY"
        domain_reasons.append(
            "Every candidate residue type is one the model was trained on."
        )

    app_domain = ApplicabilityDomain(
        classification=domain_classif,
        basis="residue_type_vocabulary",
        reasons=domain_reasons,
        note=(
            "Vocabulary membership only. The bundle ships no training feature "
            "matrix, so distance to the training distribution is not computed "
            "and no domain score is reported."
        ),
    ).as_dict()

    # Nearest measured proteins, by scaled distance over the sequence
    # descriptors the model consumes. Empty when this protein is not itself in
    # the measured set -- there is no basis for a neighbour list then.
    neighbors = measured_stiffness.nearest_measured(
        str((input_summary.get("structure") or {}).get("identifier") or "")
    )

    # Exact tree SHAP contributions for the top-ranked candidate residue.
    local_attributions = explainability.local_attributions(state.pipeline, frame, row=0)
    global_importance = explainability.global_importance(state.pipeline)

    return PredictionResult(
        prediction_id=str(uuid.uuid4()),
        model_version=state.model_version,
        model_status=state.scientific_status,
        degradation_percent=mean,
        risk_level=risk_level(mean),
        confidence=None,  # bundle exposes no calibrated uncertainty; see prediction_dispersion
        warnings=list(dict.fromkeys(warnings_out)),  # de-dupe, keep order
        input_summary=input_summary,
        residue_predictions=residue_predictions,
        aggregation=aggregation,
        held_out_error=held_out,
        prediction_dispersion=uncertainty,
        applicability_domain=app_domain,
        nearest_neighbors=neighbors,
        local_feature_attributions=local_attributions,
        global_feature_importance=global_importance,
        attribution_disclaimer=ATTRIBUTION_DISCLAIMER,
    )
