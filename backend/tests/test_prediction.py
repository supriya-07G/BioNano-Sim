"""ML model loading, inference, and the honesty guarantees around it."""

from __future__ import annotations

import pytest

ML_SCENARIOS = [
    "GCR_DEEP_SPACE_REFERENCE",
    "MARS_SURFACE_REFERENCE",
    "SPE_REFERENCE_EVENT",
]
NON_ML_SCENARIOS = ["BASELINE_NO_RADIATION", "MECHANICAL_STRESS_TEST"]


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #
def test_model_loads_and_verifies_itself(model_state):
    assert model_state.available, model_state.load_error
    assert model_state.model_version == "0.2.0-mock"
    assert model_state.scientific_status == "MOCK_PUBLIC_DATA_BOOTSTRAP"
    assert model_state.sha256_verified, "bundle hash must match release_manifest.json"
    assert model_state.schema_verified, "feature schema must match the live pipeline"


def test_model_is_loaded_once_and_reused(model_state):
    from app.ml.loader import get_model

    assert get_model() is model_state


def test_model_endpoint_is_honest_about_status(client, api):
    body = client.get(f"{api}/model").json()
    assert body["available"] is True
    assert body["scientific_status"] == "MOCK_PUBLIC_DATA_BOOTSTRAP"
    assert body["label_source"] == "SYNTHETIC_PUBLIC_DATA_PROXY"
    assert body["scientifically_validated"] is False
    assert body["supports_uncertainty"] is False
    assert len(body["limitations"]) >= 5
    assert body["feature_order"] and len(body["feature_order"]) == 14
    assert body["n_transformed_features"] == 33


def test_model_exposes_the_exact_trained_vocabulary(client, api):
    vocab = client.get(f"{api}/model").json()["categorical_vocabulary"]
    assert vocab["scenario_id"] == ML_SCENARIOS
    assert vocab["radiation_class"] == ["GCR", "SPE"]
    assert vocab["environment"] == ["free_space", "mars_surface"]
    assert vocab["proxy_type"] == ["SIDE_CHAIN_LOSS"]
    # Only 14 of 20 amino acids were seen. This gap is why OOV detection exists.
    assert len(vocab["residue_type"]) == 14
    assert "GLY" not in vocab["residue_type"]
    assert "PHE" not in vocab["residue_type"]


# --------------------------------------------------------------------------- #
# Valid prediction
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("pdb_id", ["1UBQ", "1PGA", "1TIT", "1TEN", "2SPC"])
def test_prediction_succeeds_for_every_approved_protein(client, api, pdb_id):
    response = client.post(
        f"{api}/predictions",
        json={"pdb_id": pdb_id, "scenario_id": "GCR_DEEP_SPACE_REFERENCE"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert 0.0 <= body["degradation_percent"] <= 100.0
    assert body["risk_level"] in ("low", "moderate", "elevated", "high")
    assert len(body["residue_predictions"]) == 10


def test_confidence_is_null_never_invented(client, api):
    body = client.post(
        f"{api}/predictions",
        json={"pdb_id": "1UBQ", "scenario_id": "GCR_DEEP_SPACE_REFERENCE"},
    ).json()
    assert body["confidence"] is None
    assert body["held_out_error"]["supported"] is False
    # Held-out metrics are offered instead, clearly separated from confidence.
    assert body["held_out_error"]["validation"]["mae"] == pytest.approx(4.108, abs=1e-2)


def test_mvp_disclaimer_is_always_the_first_warning(client, api):
    body = client.post(
        f"{api}/predictions",
        json={"pdb_id": "1PGA", "scenario_id": "GCR_DEEP_SPACE_REFERENCE"},
    ).json()
    assert "not experimentally validated" in body["warnings"][0]


def test_aggregation_is_explained_not_implied(client, api):
    aggregation = client.post(
        f"{api}/predictions",
        json={"pdb_id": "1PGA", "scenario_id": "GCR_DEEP_SPACE_REFERENCE"},
    ).json()["aggregation"]
    assert aggregation["method"] == "mean_over_ranked_candidate_residues"
    assert "per-residue" in aggregation["explanation"]
    assert aggregation["n_residues_predicted"] == 10
    # The headline number must be reconstructible from the reported bounds.
    assert aggregation["per_residue_min"] <= aggregation["per_residue_max"]
    assert aggregation["whole_chain_mean_note"]


def test_dose_and_temperature_are_reported_as_unused_by_the_model(client, api):
    body = client.post(
        f"{api}/predictions",
        json={
            "pdb_id": "1UBQ",
            "scenario_id": "GCR_DEEP_SPACE_REFERENCE",
            "dose": 12.5,
            "dose_unit": "kGy",
            "temperature_kelvin": 285.0,
        },
    ).json()
    unused = body["input_summary"]["not_used_by_model"]
    assert unused["dose"] == 12.5
    assert unused["dose_gray_equivalent"] == pytest.approx(12500.0)
    assert unused["temperature_kelvin"] == 285.0
    assert "no dose" in unused["_note"]


def test_dose_does_not_change_the_ml_estimate(client, api):
    """The model has no dose feature, so the estimate must be dose-invariant."""
    base = {"pdb_id": "1UBQ", "scenario_id": "GCR_DEEP_SPACE_REFERENCE"}
    low = client.post(f"{api}/predictions", json={**base, "dose": 0.001}).json()
    high = client.post(f"{api}/predictions", json={**base, "dose": 900.0}).json()
    assert low["degradation_percent"] == high["degradation_percent"]


def test_scenario_does_change_the_estimate(client, api):
    """Scenario IS a model feature, and radiation_class dominates its importance."""
    results = {}
    for scenario in ML_SCENARIOS:
        results[scenario] = client.post(
            f"{api}/predictions", json={"pdb_id": "1UBQ", "scenario_id": scenario}
        ).json()["degradation_percent"]
    assert len(set(results.values())) == 3, "each scenario must give a distinct estimate"
    # SPE carries the highest mean proxy degradation in the training data.
    assert results["SPE_REFERENCE_EVENT"] > results["GCR_DEEP_SPACE_REFERENCE"]
    assert results["GCR_DEEP_SPACE_REFERENCE"] > results["MARS_SURFACE_REFERENCE"]


def test_prediction_is_deterministic(client, api):
    payload = {"pdb_id": "1TEN", "scenario_id": "SPE_REFERENCE_EVENT"}
    first = client.post(f"{api}/predictions", json=payload).json()
    second = client.post(f"{api}/predictions", json=payload).json()
    assert first["degradation_percent"] == second["degradation_percent"]
    # But each call is separately identified.
    assert first["prediction_id"] != second["prediction_id"]


# --------------------------------------------------------------------------- #
# Unknown categories must never be absorbed silently
# --------------------------------------------------------------------------- #
def test_out_of_vocabulary_residue_is_warned_and_excluded_from_the_mean(client, api):
    """1UBQ's rank-2 candidate is GLY, which the encoder never saw."""
    body = client.post(
        f"{api}/predictions",
        json={"pdb_id": "1UBQ", "scenario_id": "GCR_DEEP_SPACE_REFERENCE"},
    ).json()

    flags = {r["residue_type"]: r["residue_type_in_model_vocabulary"] for r in body["residue_predictions"]}
    assert flags.get("GLY") is False, "GLY must be flagged as outside the vocabulary"

    assert any("Unknown category in 'residue_type'" in w for w in body["warnings"])
    assert any("all-zero block" in w for w in body["warnings"])

    aggregation = body["aggregation"]
    assert aggregation["n_residues_excluded_unknown_type"] == 1
    assert aggregation["n_residues_used_in_mean"] == 9
    assert "exclusion_note" in aggregation
    # The excluded residue is still reported, for transparency.
    assert len(body["residue_predictions"]) == 10


def test_1ten_phe_candidate_is_also_flagged(client, api):
    body = client.post(
        f"{api}/predictions",
        json={"pdb_id": "1TEN", "scenario_id": "GCR_DEEP_SPACE_REFERENCE"},
    ).json()
    flags = {r["residue_type"]: r["residue_type_in_model_vocabulary"] for r in body["residue_predictions"]}
    assert flags.get("PHE") is False


def test_unknown_category_detection_runs_before_prediction(model_state):
    """The encoder ignores unknowns silently; the guard must catch them first."""
    import pandas as pd

    from app.ml.inference import check_unknown_categories

    schema = model_state.schema
    row = {
        "protein_length": 76.0, "molecular_weight": 8564.7, "hydrophobic_fraction": 0.34,
        "charged_fraction": 0.29, "residue_index_norm": 0.5, "residue_sasa_norm": 0.7,
        "residue_contact_count": 6.0, "proxy_rank": 1.0,
        "residue_type": "SEC",                  # not a trained category
        "qualitative_susceptibility": "extreme",  # not a trained category
        "scenario_id": "GCR_DEEP_SPACE_REFERENCE",
        "radiation_class": "GCR", "environment": "free_space",
        "proxy_type": "SIDE_CHAIN_LOSS",
    }
    findings = check_unknown_categories(
        pd.DataFrame([row], columns=schema.feature_order), schema
    )
    flagged = {f["column"] for f in findings}
    assert flagged == {"residue_type", "qualitative_susceptibility"}


# --------------------------------------------------------------------------- #
# Scenarios outside the trained vocabulary
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("scenario_id", NON_ML_SCENARIOS)
def test_untrained_scenario_is_refused_with_an_explanation(client, api, scenario_id):
    response = client.post(
        f"{api}/predictions", json={"pdb_id": "1UBQ", "scenario_id": scenario_id}
    )
    assert response.status_code == 400
    error = response.json()["error"]
    assert error["code"] == "SCENARIO_NOT_ML_SUPPORTED"
    assert "vocabulary" in error["message"] or "no zero-radiation" in error["message"]
    # And it must point at what IS supported (registry order is not vocab order).
    assert set(error["details"][0]["ml_supported_scenarios"]) == set(ML_SCENARIOS)


def test_scenario_registry_marks_ml_support_and_states_provenance(client, api):
    body = client.get(f"{api}/scenarios").json()
    supported = {s["scenario_id"] for s in body["scenarios"] if s["ml_supported"]}
    assert supported == set(ML_SCENARIOS)
    for scenario in body["scenarios"]:
        if not scenario["ml_supported"]:
            assert scenario["ml_unsupported_reason"]
    provenance = body["provenance"]
    assert provenance["status"] == "CONFIGURABLE_DEMONSTRATION_PRESETS"
    assert "NOT authoritative NASA" in provenance["statement"]


# --------------------------------------------------------------------------- #
# Input validation
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "payload,status",
    [
        ({"scenario_id": "GCR_DEEP_SPACE_REFERENCE"}, 422),                       # no structure
        ({"pdb_id": "1UBQ", "upload_id": "a" * 32, "scenario_id": "GCR_DEEP_SPACE_REFERENCE"}, 422),
        ({"pdb_id": "1UBQ", "scenario_id": "NOT_A_SCENARIO"}, 404),
        ({"pdb_id": "ZZ", "scenario_id": "GCR_DEEP_SPACE_REFERENCE"}, 400),
        ({"pdb_id": "1UBQ", "scenario_id": "GCR_DEEP_SPACE_REFERENCE", "dose": -1}, 422),
        ({"pdb_id": "1UBQ", "scenario_id": "GCR_DEEP_SPACE_REFERENCE", "temperature_kelvin": 0}, 422),
        ({"pdb_id": "1UBQ", "scenario_id": "GCR_DEEP_SPACE_REFERENCE", "dose_unit": "furlongs"}, 422),
        ({"pdb_id": "1UBQ", "scenario_id": "GCR_DEEP_SPACE_REFERENCE", "top_n_residues": 0}, 422),
        ({"pdb_id": "1UBQ", "scenario_id": "GCR_DEEP_SPACE_REFERENCE", "random_seed": -5}, 422),
    ],
)
def test_invalid_requests_are_rejected(client, api, payload, status):
    response = client.post(f"{api}/predictions", json=payload)
    assert response.status_code == status, response.text
    assert "error" in response.json()


def test_validation_errors_name_the_offending_field(client, api):
    response = client.post(
        f"{api}/predictions",
        json={"pdb_id": "1UBQ", "scenario_id": "GCR_DEEP_SPACE_REFERENCE", "dose": -1},
    )
    details = response.json()["error"]["details"]
    assert any(d["field"] == "dose" for d in details)


def test_missing_feature_column_is_rejected(model_state):
    import pandas as pd

    from app.core.exceptions import PredictionError
    from app.ml.inference import validate_frame

    schema = model_state.schema
    frame = pd.DataFrame([{c: 0 for c in schema.feature_order[:-1]}])
    with pytest.raises(PredictionError) as excinfo:
        validate_frame(frame, schema)
    assert "missing required columns" in str(excinfo.value)


def test_unexpected_feature_column_is_rejected(model_state):
    import pandas as pd

    from app.core.exceptions import PredictionError
    from app.ml.inference import validate_frame

    schema = model_state.schema
    row = {c: 0 for c in schema.feature_order}
    row["surprise_feature"] = 1
    with pytest.raises(PredictionError) as excinfo:
        validate_frame(pd.DataFrame([row]), schema)
    assert "unexpected columns" in str(excinfo.value)


def test_out_of_range_numeric_is_rejected_not_clamped(model_state):
    import pandas as pd

    from app.core.exceptions import PredictionError
    from app.ml.inference import validate_frame

    schema = model_state.schema
    row = {
        "protein_length": 76.0, "molecular_weight": 8564.7, "hydrophobic_fraction": 4.2,
        "charged_fraction": 0.29, "residue_index_norm": 0.5, "residue_sasa_norm": 0.7,
        "residue_contact_count": 6.0, "proxy_rank": 1.0, "residue_type": "LYS",
        "qualitative_susceptibility": "medium",
        "scenario_id": "GCR_DEEP_SPACE_REFERENCE", "radiation_class": "GCR",
        "environment": "free_space", "proxy_type": "SIDE_CHAIN_LOSS",
    }
    with pytest.raises(PredictionError) as excinfo:
        validate_frame(pd.DataFrame([row], columns=schema.feature_order), schema)
    # The column is named in the structured details, not the human-readable message.
    assert any("hydrophobic_fraction" in d for d in excinfo.value.details)
    assert "admissible range" in excinfo.value.message


def test_out_of_envelope_numeric_warns_but_still_predicts(client, api):
    """1UBQ is the held-out validation protein, so its composition sits outside
    the training envelope. That must surface as a warning, not a refusal."""
    body = client.post(
        f"{api}/predictions",
        json={"pdb_id": "1UBQ", "scenario_id": "GCR_DEEP_SPACE_REFERENCE"},
    ).json()
    assert any("training envelope" in w for w in body["warnings"])
    assert body["degradation_percent"] > 0


# --------------------------------------------------------------------------- #
# Upload prediction path
# --------------------------------------------------------------------------- #
def test_prediction_on_an_upload_is_marked_approximate(client, api, valid_pdb_text):
    upload = client.post(
        f"{api}/proteins/upload",
        files={"file": ("frag.pdb", valid_pdb_text, "chemical/x-pdb")},
    ).json()

    response = client.post(
        f"{api}/predictions",
        json={
            "upload_id": upload["upload_id"],
            "chain_id": "A",
            "scenario_id": "GCR_DEEP_SPACE_REFERENCE",
            "top_n_residues": 5,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["input_summary"]["structure"]["feature_source"] == "recomputed"
    assert any("recomputed" in w for w in body["warnings"])
    # Poly-alanine: ALA is outside the 14-value vocabulary, so this must be flagged.
    assert any("Unknown category" in w for w in body["warnings"])
