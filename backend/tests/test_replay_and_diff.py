"""Tests for experiment replay and configuration diff (issue #32).

The acceptance criterion has two halves: a teammate can reproduce an earlier
configuration, *or* immediately identify why two results are not directly
comparable. The second half carries most of the weight here, because a diff
that lists a seed change and a force-field change identically leaves the reader
to know which one invalidates the pair -- and the reader usually doesn't.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.exceptions import NotFoundError, ValidationFailedError
from app.services import replay_service

BASE_REQUEST = {
    "pdb_id": "1UBQ", "upload_id": None, "chain_id": "A",
    "scenario_id": "GCR_DEEP_SPACE_REFERENCE", "preset_id": "rapid_demo",
    "temperature_kelvin": 300.0, "dose": 0.5, "dose_unit": "Gy",
    "exposure_duration_days": 180.0, "mechanical_force_pn": 0.0,
    "random_seed": 42,
    "preset": {
        "preset_id": "rapid_demo", "label": "Rapid Demo",
        "forcefield": ["amber14-all.xml", "implicit/gbn2.xml"],
        "solvent": "implicit_gbn2", "nonbonded_cutoff_nm": 1.2,
        "timestep_fs": 2.0, "production_steps": 5000,
        "equilibration_steps": 1000, "minimisation_steps": 500,
    },
}


@pytest.fixture
def jobs(tmp_path, monkeypatch):
    root = tmp_path / "runtime"
    (root / "jobs").mkdir(parents=True)
    (root / "uploads").mkdir(parents=True)
    monkeypatch.setattr(replay_service.settings, "runtime_dir", root)
    return root / "jobs"


def make_job(jobs: Path, job_id: str, **overrides) -> str:
    payload = json.loads(json.dumps(BASE_REQUEST))
    preset_overrides = overrides.pop("preset", None)
    payload.update(overrides)
    if preset_overrides:
        payload["preset"].update(preset_overrides)
    directory = jobs / job_id
    directory.mkdir(parents=True)
    (directory / "request.json").write_text(json.dumps(payload), encoding="utf-8")
    return job_id


# --------------------------------------------------------------------------- #
# Replay
# --------------------------------------------------------------------------- #
def test_a_draft_reproduces_the_stored_configuration(jobs):
    make_job(jobs, "source", random_seed=7, temperature_kelvin=310.0)
    result = replay_service.replay_draft("source")

    assert result["replay_of"] == "source"
    assert result["draft"]["random_seed"] == 7
    assert result["draft"]["temperature_kelvin"] == 310.0
    assert result["draft"]["pdb_id"] == "1UBQ"


def test_replay_returns_a_draft_and_starts_nothing(jobs):
    """Replaying an expensive run must be a confirmation, not a page load."""
    make_job(jobs, "source")
    result = replay_service.replay_draft("source")
    assert result["requires_confirmation"] is True
    assert "not be overwritten" in result["note"]
    assert "job_id" not in result["draft"]


def test_replay_is_possible_for_a_healthy_job(jobs):
    make_job(jobs, "source")
    assert replay_service.replay_draft("source")["can_replay"] is True


def test_a_missing_job_is_a_not_found(jobs):
    with pytest.raises(NotFoundError):
        replay_service.replay_draft("nope")


def test_a_job_without_a_stored_request_cannot_be_replayed(jobs):
    (jobs / "legacy").mkdir()
    with pytest.raises(NotFoundError, match="no stored request"):
        replay_service.replay_draft("legacy")


def test_an_unavailable_preset_blocks_replay(jobs):
    make_job(jobs, "source", preset_id="retired_preset")
    result = replay_service.replay_draft("source")

    assert result["can_replay"] is False
    assert any("no longer exists" in b for b in result["blocking"])
    assert result["draft"]["preset_id"] is None


def test_a_drifted_preset_warns_without_blocking(jobs):
    """The run can proceed, but it will not reproduce the original numbers."""
    make_job(jobs, "source", preset={"production_steps": 999_999})
    result = replay_service.replay_draft("source")

    assert result["can_replay"] is True
    assert any("has changed since the original run" in w for w in result["warnings"])
    assert any("production_steps" in w for w in result["warnings"])


def test_a_missing_upload_blocks_replay(jobs):
    make_job(jobs, "source", pdb_id=None, upload_id="gone-123")
    result = replay_service.replay_draft("source")
    assert result["can_replay"] is False
    assert any("no longer present" in b for b in result["blocking"])


def test_a_present_upload_does_not_block(jobs, tmp_path):
    (tmp_path / "runtime" / "uploads" / "here-123").write_text("ATOM", encoding="utf-8")
    make_job(jobs, "source", pdb_id=None, upload_id="here-123")
    assert replay_service.replay_draft("source")["can_replay"] is True


# --------------------------------------------------------------------------- #
# Configuration diff
# --------------------------------------------------------------------------- #
def test_identical_configurations_are_reported_as_such(jobs):
    make_job(jobs, "a")
    make_job(jobs, "b")
    diff = replay_service.configuration_diff("a", "b")

    assert diff["comparable"] is True
    assert diff["differences"] == []
    assert "stochastic variation" in diff["verdict"]


def test_a_seed_difference_is_isolating_not_invalidating(jobs):
    make_job(jobs, "a", random_seed=1)
    make_job(jobs, "b", random_seed=2)
    diff = replay_service.configuration_diff("a", "b")

    assert diff["comparable"] is True
    assert diff["counts"]["invalidating"] == 0
    seed = next(d for d in diff["differences"] if d["field"] == "random_seed")
    assert seed["kind"] == "isolating"
    assert seed["a"] == 1 and seed["b"] == 2


def test_a_temperature_difference_invalidates_the_pair(jobs):
    make_job(jobs, "a", temperature_kelvin=300.0)
    make_job(jobs, "b", temperature_kelvin=350.0)
    diff = replay_service.configuration_diff("a", "b")

    assert diff["comparable"] is False
    assert "Not directly comparable" in diff["verdict"]
    assert "temperature_kelvin" in diff["verdict"]


def test_a_force_field_difference_invalidates_the_pair(jobs):
    """The distinction the whole feature exists to make."""
    make_job(jobs, "a")
    make_job(jobs, "b", preset={"forcefield": ["charmm36.xml"]})
    diff = replay_service.configuration_diff("a", "b")

    assert diff["comparable"] is False
    field = next(d for d in diff["differences"]
                 if d["field"] == "preset.forcefield")
    assert field["kind"] == "invalidating"
    assert "not measurements of the same thing" in field["explanation"]


def test_a_trajectory_length_difference_invalidates_the_pair(jobs):
    make_job(jobs, "a", preset={"production_steps": 5000})
    make_job(jobs, "b", preset={"production_steps": 20000})
    diff = replay_service.configuration_diff("a", "b")
    assert diff["comparable"] is False
    assert any(d["field"] == "preset.production_steps"
               for d in diff["differences"])


def test_a_provenance_only_difference_does_not_invalidate(jobs):
    """Dose is recorded but enters no calculation, so it changes nothing."""
    make_job(jobs, "a", dose=0.5)
    make_job(jobs, "b", dose=99.0)
    diff = replay_service.configuration_diff("a", "b")

    assert diff["comparable"] is True
    dose = next(d for d in diff["differences"] if d["field"] == "dose")
    assert dose["kind"] == "provenance"
    assert "does not enter any calculation" in dose["explanation"]


def test_the_protein_under_study_is_isolating(jobs):
    make_job(jobs, "a", pdb_id="1UBQ")
    make_job(jobs, "b", pdb_id="1TIT")
    diff = replay_service.configuration_diff("a", "b")

    assert diff["comparable"] is True
    assert "variable under study" in diff["verdict"]


def test_invalidating_differences_are_listed_first(jobs):
    """A reader who stops after one line must see the one that matters."""
    make_job(jobs, "a", random_seed=1, temperature_kelvin=300.0)
    make_job(jobs, "b", random_seed=2, temperature_kelvin=350.0)
    diff = replay_service.configuration_diff("a", "b")
    assert diff["differences"][0]["kind"] == "invalidating"


def test_identical_fields_are_reported_too(jobs):
    make_job(jobs, "a", random_seed=1)
    make_job(jobs, "b", random_seed=2)
    diff = replay_service.configuration_diff("a", "b")
    assert "pdb_id" in diff["identical_fields"]
    assert "preset.forcefield" in diff["identical_fields"]
    assert "random_seed" not in diff["identical_fields"]


def test_comparing_a_job_with_itself_is_refused(jobs):
    make_job(jobs, "a")
    with pytest.raises(ValidationFailedError, match="two different"):
        replay_service.configuration_diff("a", "a")


def test_the_diff_counts_each_category(jobs):
    make_job(jobs, "a", random_seed=1, dose=0.5, temperature_kelvin=300.0)
    make_job(jobs, "b", random_seed=2, dose=9.0, temperature_kelvin=350.0)
    counts = replay_service.configuration_diff("a", "b")["counts"]
    assert counts["invalidating"] == 1
    assert counts["isolating"] == 1
    assert counts["provenance"] == 1


def test_a_json_round_trip_is_not_reported_as_drift(jobs):
    """forcefield is a tuple on the preset and a list in request.json.

    Comparing them raw fired a drift warning on every replay of an unchanged
    preset, and a warning that always fires is one nobody reads.
    """
    make_job(jobs, "source")
    result = replay_service.replay_draft("source")
    assert result["warnings"] == [], result["warnings"]
