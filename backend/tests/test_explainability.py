"""Unit tests for ML model explainability, uncertainty, and applicability domain (#31)."""

import pytest
from app.services import prediction_service
from app.schemas.prediction import PredictionRequest


def test_prediction_explainability_payload(client, api):
    req = PredictionRequest(
        pdb_id="1UBQ",
        scenario_id="SPE_REFERENCE_EVENT",
        dose=100.0,
        dose_unit="Gy",
    )
    result = prediction_service.run_prediction(req)
    res_dict = result.as_dict()

    # 1. Uncertainty Bounds
    assert "uncertainty_bounds" in res_dict
    unc = res_dict["uncertainty_bounds"]
    assert unc["confidence_level"] == "95%"
    assert unc["sigma"] >= 2.0
    assert unc["lower_bound_pct"] <= result.degradation_percent
    assert unc["upper_bound_pct"] >= result.degradation_percent

    # 2. Applicability Domain Classification
    assert "applicability_domain" in res_dict
    dom = res_dict["applicability_domain"]
    assert dom["classification"] in ["IN_DOMAIN", "CAUTION", "OUT_OF_DOMAIN"]
    assert 0.0 <= dom["score"] <= 1.0
    assert len(dom["reasons"]) >= 1

    # 3. Nearest Training Neighbors
    assert "nearest_neighbors" in res_dict
    nn = res_dict["nearest_neighbors"]
    assert len(nn) >= 1
    assert "pdb_id" in nn[0]
    assert "similarity_pct" in nn[0]

    # 4. Feature Attributions & Importances
    assert "local_feature_attributions" in res_dict
    assert len(res_dict["local_feature_attributions"]) >= 3
    assert "global_feature_importance" in res_dict
    assert "residue_sasa_norm" in res_dict["global_feature_importance"]

    # 5. Non-causation disclaimer
    assert "attribution_disclaimer" in res_dict
    assert "NOT causal physical mechanisms" in res_dict["attribution_disclaimer"]
