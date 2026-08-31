"""Multi-objective candidate protein ranking (#30).

These assert against the measured dataset. The previous versions encoded the
hand-written table they were written alongside -- "1TIT (185 pN/nm)", "1UBQ
(89.2/142.5 = 62.6%)" -- and so passed on numbers that disagree with the
measurements by three to five times, and on a frontier that included a domain
whose fits are all negative.
"""

from app.analysis import measured_stiffness
from app.schemas.ranking import RankingWeights
from app.services import ranking_service


def test_default_ranking_reports_measured_provenance(client, api):
    res = client.get(f"{api}/candidates/rank")
    assert res.status_code == 200
    data = res.json()

    assert data["mode"] == "MEASURED_STEERED_MD"
    assert len(data["candidates"]) == data["total_candidates"]

    dataset = data["dataset"]
    assert dataset["runs_passing_qc"] < dataset["runs_screened"], (
        "the dataset rejects most runs; a response claiming otherwise is not reading it"
    )
    assert dataset["source_file"] == measured_stiffness.STIFFNESS_CSV.name


def test_ranked_candidates_are_numbered_and_ordered(client, api):
    data = client.get(f"{api}/candidates/rank").json()

    ranked = [c for c in data["candidates"] if c["resolved"]]
    assert len(ranked) == data["ranked_candidates"]
    assert [c["rank"] for c in ranked] == list(range(1, len(ranked) + 1))

    scores = [c["composite_score"] for c in ranked]
    assert scores == sorted(scores, reverse=True)


def test_unresolved_candidates_are_listed_but_not_scored(client, api):
    data = client.get(f"{api}/candidates/rank").json()
    unresolved = [c for c in data["candidates"] if not c["resolved"]]
    assert unresolved, "most screened domains resolve no stiffness; they must still appear"

    for candidate in unresolved:
        # Not ranked, not scored, and never on the frontier: a domain the
        # protocol could not measure is not a domain that measured badly.
        assert candidate["rank"] is None
        assert candidate["composite_score"] is None
        assert candidate["is_pareto_optimal"] is False
        assert candidate["baseline_stiffness_pnnm"] is None
        assert candidate["unresolved_reason"]
        assert candidate["pdb_id"] not in data["pareto_frontier_ids"]


def test_titin_leads_on_measured_stiffness():
    """1TIT is the stiffest measured domain and the AFM benchmark."""
    resp = ranking_service.rank_candidates()
    ranked = [c for c in resp.candidates if c.resolved]
    assert ranked, "expected at least one measured candidate"

    assert ranked[0].pdb_id == "1TIT"
    assert "1TIT" in resp.pareto_frontier_ids
    assert ranked[0].baseline_stiffness_pnnm is not None
    assert ranked[0].baseline_stiffness_pnnm > 600


def test_reported_stiffness_matches_the_dataset():
    """The service must not hold numbers of its own."""
    resp = ranking_service.rank_candidates()
    for candidate in resp.candidates:
        if not candidate.resolved:
            continue
        measured = measured_stiffness.get(candidate.pdb_id)
        assert measured is not None
        assert candidate.baseline_stiffness_pnnm == round(measured.baseline.mean, 1)
        assert candidate.damaged_stiffness_pnnm == round(measured.damaged.mean, 1)
        assert candidate.runs_passing_qc == measured.n_runs
        assert candidate.runs_screened == measured.n_screened


def test_seed_spread_is_reported_and_is_large():
    """The uncertainty term is measured, and it is not small."""
    resp = ranking_service.rank_candidates()
    resolved = [c for c in resp.candidates if c.resolved]
    assert resolved

    for candidate in resolved:
        assert candidate.relative_sd is not None
        assert candidate.baseline_stiffness_sd is not None
        assert candidate.baseline_stiffness_sd > 0

    # Seed-to-seed scatter is over 10% of the mean for every resolving domain,
    # which is the project's central caveat and must survive into the payload.
    assert max(c.relative_sd for c in resolved) > 0.10


def test_weights_change_the_ordering_or_the_scores():
    """A weight the user can move must actually move something."""
    balanced = ranking_service.rank_candidates()
    strength_only = ranking_service.rank_candidates(
        weights=RankingWeights(
            stiffness_retention=0.0,
            baseline_strength=1.0,
            measurement_confidence=0.0,
            uncertainty_penalty=0.0,
        )
    )

    def scores(resp):
        return {c.pdb_id: c.composite_score for c in resp.candidates if c.resolved}

    assert scores(balanced) != scores(strength_only)


def test_pareto_frontier_is_consistent_with_the_flags():
    resp = ranking_service.rank_candidates()
    for candidate in resp.candidates:
        assert candidate.is_pareto_optimal == (
            candidate.pdb_id in resp.pareto_frontier_ids
        )
        if candidate.is_pareto_optimal:
            assert "Pareto-optimal" in candidate.explanation
