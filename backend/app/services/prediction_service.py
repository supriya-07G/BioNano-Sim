"""Prediction orchestration and the scenario registry.

Two guards live here that the rest of the app depends on:

* A scenario with ``ml_supported: false`` is refused for prediction with an
  explanatory error rather than being pushed through the encoder, where it would
  become an all-zero block and yield a plausible-looking number.
* ``input_summary`` explicitly separates the fields the model consumed from the
  fields it did not, so the UI can never imply that the dose slider moved the
  ML estimate.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from app.config import settings
from app.core.exceptions import NotFoundError, PredictionError
from app.core.logging import get_logger
from app.ml.feature_schema import load_feature_schema
from app.ml.inference import PredictionResult, aggregate_prediction
from app.ml.loader import get_model
from app.ml.preprocessing import build_feature_frame, featurise_structure
from app.services import protein_service

logger = get_logger("COSMORA.services.prediction")

# The only proxy_type in the training data. Sent as a constant because the
# encoder has exactly one category for it.
DEFAULT_PROXY_TYPE = "SIDE_CHAIN_LOSS"


@lru_cache
def _scenario_doc() -> dict[str, Any]:
    path = settings.scenarios_file
    if not path.exists():
        logger.error("Scenario file missing at %s", path)
        return {"scenarios": [], "dose_units": [], "_provenance": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def list_scenarios() -> list[dict[str, Any]]:
    return list(_scenario_doc().get("scenarios", []))


def scenario_provenance() -> dict[str, Any]:
    return dict(_scenario_doc().get("_provenance", {}))


def dose_units() -> list[dict[str, Any]]:
    return list(_scenario_doc().get("dose_units", []))


def get_scenario(scenario_id: str) -> dict[str, Any]:
    for scenario in list_scenarios():
        if scenario["scenario_id"] == scenario_id:
            return scenario
    raise NotFoundError(
        f"Unknown scenario '{scenario_id}'. Available: "
        f"{', '.join(s['scenario_id'] for s in list_scenarios())}."
    )


def dose_to_gray(dose: float, unit: str) -> float | None:
    for entry in dose_units():
        if entry["unit"] == unit:
            return dose * float(entry["to_gray"])
    return None


def run_prediction(request: Any) -> PredictionResult:
    """Featurise, validate, predict and aggregate for one experiment request."""
    scenario = get_scenario(request.scenario_id)

    if not scenario.get("ml_supported", False):
        raise PredictionError(
            f"Scenario '{scenario['scenario_id']}' has no ML degradation estimate. "
            + scenario.get(
                "ml_unsupported_reason",
                "It is outside the model's trained scenario vocabulary.",
            )
            + " Run the simulation instead, which supports this scenario.",
            code="SCENARIO_NOT_ML_SUPPORTED",
            details=[
                {
                    "scenario_id": scenario["scenario_id"],
                    "ml_supported_scenarios": [
                        s["scenario_id"] for s in list_scenarios() if s.get("ml_supported")
                    ],
                }
            ],
        )

    state = get_model()
    schema = load_feature_schema()
    extra_warnings: list[str] = []

    # --- features ---------------------------------------------------------
    if request.pdb_id:
        pdb_id = protein_service.validate_pdb_id(request.pdb_id)
        chain_features = protein_service.reference_chain_features(pdb_id, schema)
        identifier, kind = pdb_id, "approved"
    else:
        path = protein_service.upload_path(request.upload_id)
        chain_features = featurise_structure(
            path, request.chain_id, schema, pdb_id="UPLOAD"
        )
        identifier, kind = request.upload_id, "upload"
        extra_warnings.extend(chain_features.warnings)

    candidates = protein_service.candidate_residues(
        identifier if kind == "approved" else "UPLOAD",
        chain_features,
        schema,
        top_n=request.top_n_residues,
    )
    if not candidates:
        raise PredictionError(
            "No candidate residues could be ranked for this structure."
        )
    if request.top_n_residues != 10:
        extra_warnings.append(
            f"Scoring {request.top_n_residues} candidate residues; the model was "
            "trained only on the top 10 per protein, so ranks beyond 10 are an "
            "extrapolation to residues less susceptible than any it saw."
        )

    frame = build_feature_frame(
        chain_features,
        candidates,
        scenario_id=scenario["scenario_id"],
        radiation_class=scenario["radiation_class"],
        environment=scenario["environment"],
        proxy_type=DEFAULT_PROXY_TYPE,
        schema=schema,
    )

    # --- provenance -------------------------------------------------------
    dose_gray = dose_to_gray(request.dose, request.dose_unit)
    input_summary = {
        "structure": {
            "kind": kind,
            "identifier": identifier,
            "chain_id": chain_features.chain_id,
            "protein_length": chain_features.protein_length,
            "molecular_weight": round(chain_features.molecular_weight, 4),
            "feature_source": chain_features.source,
        },
        "scenario": {
            "scenario_id": scenario["scenario_id"],
            "label": scenario["label"],
            "radiation_class": scenario["radiation_class"],
            "environment": scenario["environment"],
            "particle_group": scenario.get("particle_group"),
        },
        "used_by_model": {
            "feature_columns": schema.feature_order,
            "n_rows_scored": int(len(frame)),
            "proxy_type": DEFAULT_PROXY_TYPE,
            "chain_level_features": chain_features.chain_level(),
        },
        "not_used_by_model": {
            "_note": (
                "The ML bundle has no dose, duration, temperature or force input. "
                "These values are recorded for provenance and drive the OpenMM "
                "simulation only; changing them does not change the ML estimate. "
                "Radiation intensity reaches the model solely through the "
                "categorical scenario_id / radiation_class / environment."
            ),
            "dose": request.dose,
            "dose_unit": request.dose_unit,
            "dose_gray_equivalent": dose_gray,
            "exposure_duration_days": request.exposure_duration_days,
            "temperature_kelvin": request.temperature_kelvin,
            "mechanical_force_pn": request.mechanical_force_pn,
            "random_seed": request.random_seed,
        },
    }

    result = aggregate_prediction(
        state,
        frame,
        candidates,
        input_summary=input_summary,
        extra_warnings=extra_warnings,
    )
    logger.info(
        "Prediction %s: %s chain %s scenario %s -> %.2f%% (%s)",
        result.prediction_id,
        identifier,
        chain_features.chain_id,
        scenario["scenario_id"],
        result.degradation_percent,
        result.risk_level,
    )
    return result


def model_info() -> dict[str, Any]:
    """Everything the UI needs to describe the model honestly."""
    state = get_model()
    metadata = state.metadata or {}
    payload: dict[str, Any] = {
        "available": state.available,
        "status": state.status,
        "model_name": metadata.get("model_name"),
        "model_version": state.model_version,
        "scientific_status": state.scientific_status,
        "label_source": metadata.get("label_source"),
        "scientifically_validated": bool(metadata.get("scientifically_validated", False)),
        "approved_use": metadata.get("approved_use"),
        "created_at_utc": metadata.get("created_at_utc"),
        "bundle_sha256": state.bundle_sha256,
        "sha256_verified": state.sha256_verified,
        "schema_verified": state.schema_verified,
        "load_error": state.load_error,
        "warnings": state.warnings,
        "validation_metrics": metadata.get("validation_metrics"),
        "test_metrics": metadata.get("test_metrics"),
        "train_proteins": metadata.get("train_proteins", []),
        "validation_proteins": metadata.get("validation_proteins", []),
        "test_proteins": metadata.get("test_proteins", []),
        "replacement_requirement": metadata.get("replacement_requirement"),
        "limitations": [
            "Labels are a synthetic public-data proxy (SYNTHETIC_PUBLIC_DATA_PROXY), "
            "not experimentally measured degradation.",
            "The target is per-residue side-chain-loss degradation for a ranked "
            "candidate residue. Protein-level figures are aggregated by COSMORA.",
            "The model has no dose, exposure-duration, temperature or mechanical-force "
            "input; radiation enters only as a categorical scenario.",
            "Only three scenario configurations were trained. There is no "
            "no-radiation control and no mechanical-only condition.",
            "The residue_type vocabulary covers 14 of 20 amino acids. Unseen types are "
            "encoded as all-zero and produce unreliable per-residue estimates.",
            "The bundle exposes no calibrated uncertainty, so per-prediction "
            "confidence is null.",
            "Training used only 5 proteins and 450 rows; generalisation beyond small "
            "single-domain proteins is unverified.",
        ],
    }

    if state.schema is not None:
        schema = state.schema
        payload.update(
            {
                "target_column": schema.target_column,
                "feature_order": schema.feature_order,
                "numeric_features": schema.numeric_features,
                "categorical_features": schema.categorical_features,
                "categorical_vocabulary": schema.vocabulary,
                "n_transformed_features": schema.raw.get("n_transformed_features"),
                "supports_uncertainty": schema.supports_uncertainty,
                "uncertainty_note": schema.uncertainty_note,
            }
        )

    payload["top_feature_importances"] = _feature_importances(state)
    return payload


def _feature_importances(state: Any, top_n: int = 10) -> list[dict[str, Any]]:
    """Top transformed-feature importances, for the FeatureSummary panel."""
    if not state.available or state.pipeline is None or state.schema is None:
        return []
    try:
        import numpy as np

        estimator = state.pipeline.steps[-1][1]
        importances = np.asarray(estimator.feature_importances_, dtype=float)
        names = list(state.schema.raw.get("transformed_feature_names") or [])
        if len(names) != len(importances):
            names = [f"f{i}" for i in range(len(importances))]
        order = np.argsort(importances)[::-1][:top_n]
        return [
            {
                "feature": names[i].replace("numeric__", "").replace("categorical__", ""),
                "group": "numeric" if names[i].startswith("numeric__") else "categorical",
                "importance": round(float(importances[i]), 6),
            }
            for i in order
            if importances[i] > 0
        ]
    except Exception as exc:  # noqa: BLE001 - purely informational
        logger.warning("Could not read feature importances: %s", exc)
        return []
