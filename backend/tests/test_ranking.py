"""Unit tests for multi-objective candidate protein ranking (#30)."""

import pytest
from app.services import ranking_service
from app.schemas.ranking import RankingWeights


def test_get_default_candidate_rankings(client, api):
    res = client.get(f"{api}/candidates/rank")
    assert res.status_code == 200
    data = res.json()

    assert data["mode"] == "REAL_EMPIRICAL_PARETO"
    assert data["total_candidates"] >= 5
    assert len(data["candidates"]) == data["total_candidates"]
    assert len(data["pareto_frontier_ids"]) >= 1

    # Check rank order 1..N
    ranks = [c["rank"] for c in data["candidates"]]
    assert ranks == list(range(1, len(data["candidates"]) + 1))

    # Check descending composite scores
    scores = [c["composite_score"] for c in data["candidates"]]
    assert scores == sorted(scores, reverse=True)


def test_custom_weight_evaluation(client, api):
    # Heavily weight baseline mechanical strength
    custom_weights = {
        "stiffness_retention": 0.1,
        "baseline_strength": 0.8,
        "structural_stability": 0.1,
        "uncertainty_penalty": 0.0,
        "out_of_domain_penalty": 0.0,
    }
    res = client.post(f"{api}/candidates/rank", json=custom_weights)
    assert res.status_code == 200
    data = res.json()

    # Under 80% baseline strength, 1TIT (185 pN/nm) should be rank 1
    top_candidate = data["candidates"][0]
    assert top_candidate["pdb_id"] == "1TIT"
    assert top_candidate["rank"] == 1


def test_pareto_frontier_determination():
    resp = ranking_service.rank_candidates()
    pareto_ids = resp.pareto_frontier_ids

    # Titin I27 (1TIT) has the highest baseline stiffness (185 pN/nm) -> must be Pareto optimal
    assert "1TIT" in pareto_ids

    # Ubiquitin (1UBQ) has high stiffness retention (89.2/142.5 = 62.6%) -> must be Pareto optimal
    assert "1UBQ" in pareto_ids

    for candidate in resp.candidates:
        if candidate.pdb_id in pareto_ids:
            assert candidate.is_pareto_optimal is True
            assert "Pareto-Optimal Candidate" in candidate.explanation


def test_uncertainty_and_ood_penalties():
    # Evaluate candidate with high uncertainty/OOD penalty
    weights = RankingWeights(
        stiffness_retention=0.2,
        baseline_strength=0.2,
        structural_stability=0.2,
        uncertainty_penalty=0.4,
        out_of_domain_penalty=0.4,
    )
    resp = ranking_service.rank_candidates(weights=weights)

    # 2F4K has high uncertainty sigma (0.18) and OOD distance (0.35) -> should receive heavy penalty
    f4k = next(c for c in resp.candidates if c.pdb_id == "2F4K")
    assert f4k.penalties["out_of_domain"] > 20.0
    assert "Deducted" in f4k.explanation


def test_mock_mode_isolation_flag(client, api):
    res_real = client.get(f"{api}/candidates/rank?allow_mock=false")
    assert res_real.json()["mode"] == "REAL_EMPIRICAL_PARETO"

    res_mock = client.get(f"{api}/candidates/rank?allow_mock=true")
    assert res_mock.json()["mode"] == "MOCK_DEMO_RANKING"
