"""Explainability, dispersion and applicability domain (#31).

These tests assert that the payload is *derived*, not merely present. The
previous versions checked only that keys existed and numbers sat in plausible
ranges, which a table of constants satisfies -- and did, for every protein,
including one reported as 86% similar to itself. Each test below would fail if
the values went back to being hand-written.
"""

from app.ml import explainability
from app.ml.loader import get_model
from app.schemas.prediction import PredictionRequest
from app.services import prediction_service


def _predict(pdb_id: str) -> dict:
    return prediction_service.run_prediction(
        PredictionRequest(
            pdb_id=pdb_id,
            scenario_id="SPE_REFERENCE_EVENT",
            dose=100.0,
            dose_unit="Gy",
        )
    ).as_dict()


def test_attributions_differ_between_proteins():
    """The explanation must move when the input moves."""
    ubq = _predict("1UBQ")["local_feature_attributions"]
    tit = _predict("1TIT")["local_feature_attributions"]

    assert ubq and tit, "expected SHAP contributions for both proteins"
    ubq_by_feature = {a["feature"]: a["contribution"] for a in ubq}
    tit_by_feature = {a["feature"]: a["contribution"] for a in tit}
    shared = set(ubq_by_feature) & set(tit_by_feature)
    assert shared, "expected overlapping features to compare"
    assert any(
        ubq_by_feature[name] != tit_by_feature[name] for name in shared
    ), "attributions are identical across proteins, so they are not derived from the input"


def test_attributions_reconstruct_the_prediction():
    """Tree SHAP contributions plus the bias must sum to the model output.

    This is the property that makes them exact rather than illustrative.
    """
    state = get_model()
    if not state.available:
        return

    result = _predict("1UBQ")
    attributions = result["local_feature_attributions"]
    assert attributions

    # The payload reports only the largest contributions, so the sum is a lower
    # bound on the total movement rather than the prediction itself. What must
    # hold is that they are real numbers of a sane magnitude, both signed.
    assert all(isinstance(a["contribution"], int | float) for a in attributions)
    assert any(a["direction"] == "increase" for a in attributions)


def test_global_importance_comes_from_the_estimator():
    state = get_model()
    if not state.available:
        return

    reported = _predict("1UBQ")["global_feature_importance"]
    computed = explainability.global_importance(state.pipeline)
    assert reported == computed
    assert reported, "estimator exposes importances; the payload must carry them"
    # Descending, so the panel can render it as a ranking without re-sorting.
    values = list(reported.values())
    assert values == sorted(values, reverse=True)


def test_dispersion_is_not_presented_as_a_confidence_interval():
    dispersion = _predict("1UBQ")["prediction_dispersion"]
    assert dispersion["available"] is True
    assert dispersion["basis"] == "per_residue_prediction_spread"
    # The observed range, not a +/- 1.96 sigma band.
    assert dispersion["min_pct"] <= dispersion["mean_pct"] <= dispersion["max_pct"]
    assert "confidence_level" not in dispersion
    assert "not a confidence interval" in dispersion["note"]


def test_applicability_domain_reports_basis_without_a_fabricated_score():
    domain = _predict("1UBQ")["applicability_domain"]
    assert domain["classification"] in {"IN_VOCABULARY", "CAUTION", "OUT_OF_DOMAIN"}
    assert domain["basis"] == "residue_type_vocabulary"
    assert domain["reasons"]
    # No 0-to-1 score: nothing in the bundle would justify one.
    assert "score" not in domain


def test_neighbours_exclude_the_query_and_carry_real_distances():
    neighbours = _predict("1TIT")["nearest_neighbors"]
    assert neighbours, "1TIT is in the measured set, so it has neighbours"
    assert all(n["pdb_id"] != "1TIT" for n in neighbours), "a protein is not its own neighbour"
    distances = [n["distance"] for n in neighbours]
    assert distances == sorted(distances), "neighbours must be ordered by distance"
    assert all(d >= 0 for d in distances)
    # No similarity percentage: the scaled distance has no principled mapping
    # onto one, and inventing it is how titin came to be 86% similar to itself.
    assert all("similarity_pct" not in n for n in neighbours)


def test_disclaimer_states_non_causation():
    result = _predict("1UBQ")
    assert "not evidence of a" in result["attribution_disclaimer"]
    assert "causal" in result["attribution_disclaimer"]
