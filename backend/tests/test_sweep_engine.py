"""Tests for damage-severity and parameter sweep experiments (issue #33)."""

from __future__ import annotations

import time

import pytest

from app.core.exceptions import ValidationFailedError
from app.schemas.sweep import SweepConfig, SweepItem
from app.simulation.sweep import (
    aggregate_severity_response,
    build_experiment_id,
    estimate_sweep_cost,
    expand_sweep_grid,
)


def test_build_experiment_id():
    assert build_experiment_id("1UBQ", "MILD", 1, 42) == "1UBQ_MILD_rank1_seed42"
    assert build_experiment_id("1UBQ", "SEVERE", 1, 42) == "1UBQ_SEVERE_seed42"


def test_expand_sweep_grid():
    config = SweepConfig(
        protein_id="1UBQ",
        severities=["MILD", "MODERATE"],
        ranks=[1, 2],
        seeds=[42, 43],
    )
    existing = {"1UBQ_MILD_rank1_seed42"}
    combinations = expand_sweep_grid(config, existing)

    # MILD has 2 ranks * 2 seeds = 4, MODERATE has 1 * 2 seeds = 2 -> Total = 6
    assert len(combinations) == 6
    dup = next(c for c in combinations if c.experiment_id == "1UBQ_MILD_rank1_seed42")
    assert dup.is_duplicate is True


def test_estimate_sweep_cost_bounds():
    # Valid config
    config = SweepConfig(protein_id="1UBQ", severities=["MILD"], ranks=[1], seeds=[42])
    preview = estimate_sweep_cost(config)
    assert preview.total_experiments == 1
    assert preview.estimated_time_seconds > 0.0
    assert preview.estimated_storage_mb > 0.0

    # Exceeding safety limit (50)
    huge_seeds = list(range(100))
    huge_config = SweepConfig(protein_id="1UBQ", severities=["MILD"], ranks=[1], seeds=huge_seeds)
    with pytest.raises(ValidationFailedError, match="exceeds the safety limit"):
        estimate_sweep_cost(huge_config)


def test_aggregate_severity_response():
    items = [
        SweepItem(experiment_id="1", severity_label="MILD", proxy_rank=1, random_seed=1, status="COMPLETED", mechanical_degradation_pct=10.0),
        SweepItem(experiment_id="2", severity_label="MILD", proxy_rank=1, random_seed=2, status="COMPLETED", mechanical_degradation_pct=20.0),
        SweepItem(experiment_id="3", severity_label="MODERATE", proxy_rank=1, random_seed=1, status="COMPLETED", mechanical_degradation_pct=40.0),
    ]
    curves = aggregate_severity_response(items)
    assert len(curves) == 3

    mild = next(c for c in curves if c.severity_label == "MILD")
    assert mild.mean_degradation_pct == 15.0
    assert mild.n_experiments == 2

    moderate = next(c for c in curves if c.severity_label == "MODERATE")
    assert moderate.mean_degradation_pct == 40.0
    assert moderate.n_experiments == 1


def test_sweep_api_preview_and_submission(client, api):
    payload = {
        "protein_id": "1UBQ",
        "severities": ["MILD"],
        "ranks": [1],
        "seeds": [42],
    }

    # 1. Preview
    res_prev = client.post(f"{api}/sweeps/preview", json=payload)
    assert res_prev.status_code == 200
    prev_body = res_prev.json()
    assert prev_body["total_experiments"] == 1

    # 2. Submit
    res_sub = client.post(f"{api}/sweeps", json=payload)
    assert res_sub.status_code == 202
    sub_body = res_sub.json()
    assert "SWEEP_1UBQ_" in sub_body["sweep_id"]
    assert sub_body["status"] in ("PENDING", "RUNNING", "COMPLETED")

    sweep_id = sub_body["sweep_id"]
    time.sleep(0.2)

    # 3. Get Detail
    res_get = client.get(f"{api}/sweeps/{sweep_id}")
    assert res_get.status_code == 200
    assert res_get.json()["sweep_id"] == sweep_id

    # 4. List Sweeps
    res_list = client.get(f"{api}/sweeps")
    assert res_list.status_code == 200
    assert any(s["sweep_id"] == sweep_id for s in res_list.json())

    # 5. Cancel Sweep
    res_cancel = client.post(f"{api}/sweeps/{sweep_id}/cancel")
    assert res_cancel.status_code == 200
    assert res_cancel.json()["status"] in ("CANCELLED", "COMPLETED")

    # 6. Export CSV
    res_exp = client.get(f"{api}/sweeps/{sweep_id}/export/csv")
    assert res_exp.status_code == 200
    assert "experiment_id" in res_exp.text
