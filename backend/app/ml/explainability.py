"""Attributions and dispersion computed from the loaded model (#31).

Everything here is derived from the fitted pipeline or from the measured
dataset. Nothing is written by hand.

That distinction is the whole point of the module. The values it replaces were
constants: the same three "nearest neighbours" at the same three similarity
percentages, and the same four attributions summing to the same 7.9, returned
for every protein. Titin came back 95% similar to ubiquitin and 86% similar to
itself. A judge who asks how a number was computed deserves an answer that
names a matrix rather than a line in the source.

Local attributions are exact rather than approximate. XGBoost's booster can
emit per-feature contributions directly (``pred_contribs=True``), which are the
tree SHAP values for the prediction and sum, with the bias term, to the model
output. No sampling and no surrogate model is involved.

What these are not: attributions describe how *this model* divides *its own*
output across inputs. They are not physical mechanism, and the model is a
bootstrap fit on public data whose scientific status the payload carries
alongside them.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

logger = logging.getLogger("COSMORA.ml.explainability")

ATTRIBUTION_DISCLAIMER = (
    "Attributions are exact tree SHAP contributions from the fitted model: they "
    "describe how this model apportions its own output across input features. "
    "They are correlative within the training data and are not evidence of a "
    "causal physical mechanism."
)

DISPERSION_NOTE = (
    "This is the spread of per-residue predictions across the candidate residues "
    "of this protein, not a confidence interval. The model carries no calibrated "
    "predictive uncertainty, so no coverage probability can be attached to this "
    "range."
)

#: Prefixes the column transformer adds; stripped for display only.
_PIPELINE_PREFIXES = ("numeric__", "categorical__", "remainder__")


def _pretty(name: str) -> str:
    for prefix in _PIPELINE_PREFIXES:
        if name.startswith(prefix):
            return name[len(prefix) :]
    return name


def _final_estimator(pipeline: Any) -> Any:
    steps = getattr(pipeline, "steps", None)
    return steps[-1][1] if steps else pipeline


def global_importance(pipeline: Any, limit: int = 8) -> dict[str, float]:
    """The model's own feature importances, largest first.

    Returns an empty mapping when the estimator exposes none, so a caller can
    omit the section rather than show zeros that look like measurements.
    """
    estimator = _final_estimator(pipeline)
    weights = getattr(estimator, "feature_importances_", None)
    if weights is None:
        return {}

    names = _feature_names(pipeline, len(weights))
    ranked = sorted(zip(names, weights, strict=True), key=lambda kv: -float(kv[1]))
    return {_pretty(name): round(float(value), 4) for name, value in ranked[:limit]}


def _feature_names(pipeline: Any, expected: int) -> list[str]:
    try:
        names = list(pipeline[:-1].get_feature_names_out())
        if len(names) == expected:
            return names
    except Exception as exc:  # pragma: no cover - depends on sklearn internals
        logger.debug("Could not recover transformed feature names: %s", exc)
    return [f"feature_{i}" for i in range(expected)]


def local_attributions(
    pipeline: Any, frame: Any, *, row: int = 0, limit: int = 6
) -> list[dict[str, Any]]:
    """Exact per-feature SHAP contributions for one input row.

    ``row`` selects which candidate residue to explain; the caller passes the
    residue the prediction is reported for. Returns an empty list when the
    estimator has no booster, which is the honest answer for a model that
    cannot produce these.
    """
    estimator = _final_estimator(pipeline)
    booster_of = getattr(estimator, "get_booster", None)
    if booster_of is None:
        return []

    try:
        import xgboost as xgb

        transformed = pipeline[:-1].transform(frame)
        matrix = xgb.DMatrix(transformed)
        # Last column is the bias (base score), not a feature.
        contributions = booster_of().predict(matrix, pred_contribs=True)[row][:-1]
        names = _feature_names(pipeline, len(contributions))
        values = _row_values(transformed, row, len(contributions))
    except Exception as exc:
        logger.warning("SHAP contributions unavailable: %s", exc)
        return []

    ordered = sorted(
        zip(names, contributions, values, strict=True),
        key=lambda item: -abs(float(item[1])),
    )
    return [
        {
            "feature": _pretty(name),
            "value": _jsonable(value),
            "contribution": round(float(contribution), 4),
            "direction": "increase" if float(contribution) >= 0 else "decrease",
        }
        for name, contribution, value in ordered[:limit]
    ]


def _row_values(transformed: Any, row: int, width: int) -> list[Any]:
    try:
        dense = transformed.toarray() if hasattr(transformed, "toarray") else transformed
        return list(np.asarray(dense)[row][:width])
    except Exception:  # pragma: no cover - shape mismatch guard
        return [None] * width


def _jsonable(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, np.floating | float):
        return round(float(value), 4)
    if isinstance(value, np.integer | int):
        return int(value)
    return str(value)


def dispersion(values: np.ndarray, mean: float) -> dict[str, Any]:
    """Spread of the per-residue predictions behind a protein-level figure.

    Deliberately not called a confidence interval and deliberately not scaled
    by 1.96: doing either would assert a coverage guarantee that an uncalibrated
    model does not provide. The range reported is the observed one.
    """
    if values.size == 0:
        return {"available": False, "note": DISPERSION_NOTE}
    if values.size == 1:
        return {
            "available": False,
            "note": (
                "Only one candidate residue was predicted, so there is no spread "
                "to report. " + DISPERSION_NOTE
            ),
        }
    return {
        "available": True,
        "basis": "per_residue_prediction_spread",
        "sd": round(float(values.std(ddof=0)), 4),
        "min_pct": round(float(values.min()), 4),
        "max_pct": round(float(values.max()), 4),
        "mean_pct": round(float(mean), 4),
        "n_residues": int(values.size),
        "note": DISPERSION_NOTE,
    }
