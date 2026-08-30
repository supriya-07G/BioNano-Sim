"""Tests for the paired-experiment contract (issue #2).

The contract exists to stop a malformed simulation output reaching a training
set. These tests prove it accepts the documented valid shape and rejects each
documented violation -- the acceptance criterion of the issue.

Every invalid fixture differs from the valid one by exactly one field, so a
failure here names one broken rule rather than a set of them.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.contracts.paired_experiment import (
    CONTRACT_VERSION,
    FORCE_EXTENSION_COLUMNS,
    STIFFNESS_CSV_COLUMNS,
    PairedExperimentResult,
    StiffnessFit,
    validate_result_payload,
    validate_stiffness_row,
)

FIXTURES = Path(__file__).parent / "fixtures" / "contract"
INVALID_FILES = sorted(FIXTURES.glob("invalid_*.json"))
INVALID_CASES = [p for p in INVALID_FILES if p.name != "invalid_index.json"]


def load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# The valid example
# --------------------------------------------------------------------------- #
def test_the_minimal_valid_example_is_accepted():
    result = validate_result_payload(load("valid_minimal.json"))
    assert result.experiment_id == "1UBQ_MILD_74_seed1"
    assert result.status == "COMPLETED"
    assert result.stiffness_unit == "pN/nm"


def test_the_valid_example_declares_the_contract_version():
    assert load("valid_minimal.json")["schema_version"] == CONTRACT_VERSION


def test_a_richer_payload_is_still_accepted():
    """Producers may add fields; the contract must not force lockstep releases."""
    payload = load("valid_minimal.json") | {
        "uniprot_id": "P0CG48",
        "residue_rmsf": 0.21,
        "some_future_field": {"nested": True},
    }
    assert validate_result_payload(payload).experiment_id


def test_a_negative_degradation_is_accepted_as_measured():
    """A damaged construct measuring stiffer is real and must not be clamped."""
    payload = load("valid_minimal.json") | {
        "baseline_stiffness": 500.0,
        "damaged_stiffness": 650.0,
        "mechanical_degradation_pct": -30.0,
    }
    assert validate_result_payload(payload).mechanical_degradation_pct == -30.0


def test_a_qc_failed_run_with_reasons_is_accepted():
    payload = load("valid_minimal.json") | {
        "status": "QC_FAILED",
        "qc_failures": ["baseline fit r^2 below threshold"],
        "baseline_stiffness": None,
        "damaged_stiffness": None,
        "mechanical_degradation_pct": None,
    }
    assert validate_result_payload(payload).status == "QC_FAILED"


# --------------------------------------------------------------------------- #
# The invalid examples
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("path", INVALID_CASES, ids=lambda p: p.stem)
def test_every_invalid_fixture_is_rejected(path: Path):
    payload = json.loads(path.read_text(encoding="utf-8"))
    with pytest.raises(ValidationError):
        validate_result_payload(payload)


def test_the_invalid_fixtures_cover_every_documented_rule():
    """The index and the files must not drift apart."""
    index = json.loads((FIXTURES / "invalid_index.json").read_text(encoding="utf-8"))
    assert {p.name for p in INVALID_CASES} == set(index)
    assert len(INVALID_CASES) >= 10, "the contract has more rules than this"


def test_the_unit_error_names_the_offending_unit():
    """A wrong unit is the costliest failure, so its message must be specific."""
    with pytest.raises(ValidationError) as exc:
        validate_result_payload(load("invalid_wrong_stiffness_unit.json"))
    assert "stiffness_unit" in str(exc.value)


def test_the_degradation_error_shows_both_numbers():
    with pytest.raises(ValidationError) as exc:
        validate_result_payload(load("invalid_degradation_arithmetic.json"))
    message = str(exc.value)
    assert "mechanical_degradation_pct" in message
    assert "603" in message and "504" in message, "must show the inputs it used"


def test_a_rejected_run_must_explain_itself():
    with pytest.raises(ValidationError) as exc:
        validate_result_payload(load("invalid_qc_failed_without_reasons.json"))
    assert "qc_failures" in str(exc.value)


# --------------------------------------------------------------------------- #
# Stiffness fit diagnostics
# --------------------------------------------------------------------------- #
def _fit(**overrides) -> dict:
    base = {
        "slope_pn_per_nm": 603.0, "intercept_pn": -12.4, "r_squared": 0.89,
        "n_points": 42, "fit_start_nm": 0.5, "fit_end_nm": 1.8,
        "reliable": True, "unreliable_reasons": [],
    }
    return base | overrides


def test_a_reliable_fit_is_accepted():
    assert StiffnessFit.model_validate(_fit()).r_squared == 0.89


def test_a_backwards_fit_interval_is_rejected():
    with pytest.raises(ValidationError, match="increasing"):
        StiffnessFit.model_validate(_fit(fit_start_nm=1.8, fit_end_nm=0.5))


def test_an_unreliable_fit_must_give_a_reason():
    with pytest.raises(ValidationError, match="unreliable_reasons"):
        StiffnessFit.model_validate(_fit(reliable=False))


def test_an_unreliable_fit_with_a_reason_is_accepted():
    fit = StiffnessFit.model_validate(
        _fit(reliable=False, unreliable_reasons=["fewer than 5 points above noise"])
    )
    assert fit.unreliable_reasons


@pytest.mark.parametrize("bad", [-0.1, 1.1])
def test_r_squared_outside_zero_to_one_is_rejected(bad: float):
    with pytest.raises(ValidationError):
        StiffnessFit.model_validate(_fit(r_squared=bad))


# --------------------------------------------------------------------------- #
# The CSV row projection
# --------------------------------------------------------------------------- #
def _row(**overrides) -> dict:
    base = {
        "experiment_id": "1UBQ_MILD_74_seed1", "job_id": "1UBQ_MILD_74_seed1",
        "protein_id": "1UBQ", "pdb_id": "1UBQ", "chain_id": "A",
        "scenario_id": "GCR_DEEP_SPACE_REFERENCE", "damage_residue_id": "A:74",
        "residue_type": "ARG", "proxy_type": "SIDE_CHAIN_LOSS", "proxy_rank": 1,
        "random_seed": 1, "baseline_stiffness": 603.0, "damaged_stiffness": 504.0,
        "stiffness_unit": "pN/nm", "fit_quality": 0.89,
        "sim_config_hash": "779b297ee54d560c11b07397c92fa69e593a32de7fc7486575"
                           "47006a26ac50d5",
        "git_commit": "7d605ab", "status": "COMPLETED", "is_synthetic": False,
        "severity_label": "MILD", "n_residues_damaged": 1,
        "damage_residue_ids": "A:74", "mechanical_degradation_pct": 16.4179,
    }
    return base | overrides


def test_a_valid_stiffness_row_is_accepted():
    assert validate_stiffness_row(_row()).protein_id == "1UBQ"


def test_a_synthetic_row_is_refused_from_the_real_dataset():
    with pytest.raises(ValidationError, match="is_synthetic"):
        validate_stiffness_row(_row(is_synthetic=True))


def test_an_unknown_column_is_refused():
    """extra='forbid' here: a stray column means the writer drifted."""
    with pytest.raises(ValidationError):
        validate_stiffness_row(_row(dose_gy=0.5))


def test_the_declared_column_order_matches_the_producer():
    """The contract must not drift from the script that writes the file."""
    repo = str(Path(__file__).parents[2])
    if repo not in sys.path:
        sys.path.insert(0, repo)
    from scripts import run_paired_experiment as producer  # noqa: PLC0415

    assert (
        tuple(producer.STIFFNESS_CSV_COLUMNS) + tuple(producer.STIFFNESS_CSV_EXTRA)
        == STIFFNESS_CSV_COLUMNS
    )


def test_the_force_extension_columns_match_the_producer():
    from app.simulation.pulling import CSV_HEADER  # noqa: PLC0415

    assert tuple(CSV_HEADER) == FORCE_EXTENSION_COLUMNS


# --------------------------------------------------------------------------- #
# The real dataset must satisfy its own contract
# --------------------------------------------------------------------------- #
REAL_CSV = Path(__file__).parents[2] / "data" / "ml" / "stiffness_results_REAL_v1.csv"


#: Spec columns the Kaggle notebook does not emit. It is a second producer of
#: this file and predates the contract; both are pure provenance, so the rows
#: are still scientifically usable. Pinned here so the gap cannot widen
#: unnoticed -- adding a third missing column fails this test.
KAGGLE_PRODUCER_GAP = {"job_id", "git_commit"}


@pytest.mark.skipif(not REAL_CSV.exists(), reason="real dataset not present")
def test_the_kaggle_producer_gap_is_exactly_what_we_documented():
    with REAL_CSV.open(newline="", encoding="utf-8") as fh:
        header = set(next(csv.reader(fh)))
    missing = {c for c in STIFFNESS_CSV_COLUMNS if c not in header}
    assert missing == KAGGLE_PRODUCER_GAP, (
        f"the committed dataset is missing {sorted(missing)}; the documented "
        f"gap is {sorted(KAGGLE_PRODUCER_GAP)}. Either the producer regressed "
        "or the contract moved."
    )


@pytest.mark.skipif(not REAL_CSV.exists(), reason="real dataset not present")
def test_the_committed_real_dataset_validates_row_by_row():
    """The shipped dataset is the contract's only production consumer.

    Every row of all 520 experiments is checked, not a sample: a single row with
    the wrong unit or broken degradation arithmetic is enough to poison a
    training set, and there is no cost to checking all of them.
    """
    with REAL_CSV.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert rows, "the committed dataset must not be empty"

    checked = 0
    for row in rows:
        payload = {k: v for k, v in row.items() if k in STIFFNESS_CSV_COLUMNS}
        # Fill the provenance the Kaggle producer omits, so the scientific
        # fields below are still checked rather than skipped wholesale.
        payload.setdefault("job_id", payload["experiment_id"])
        payload.setdefault("git_commit", "unrecorded")
        for key in ("baseline_stiffness", "damaged_stiffness",
                    "mechanical_degradation_pct", "fit_quality"):
            payload[key] = float(payload[key]) if payload.get(key) else None
        payload["proxy_rank"] = int(float(payload["proxy_rank"]))
        payload["n_residues_damaged"] = int(float(payload["n_residues_damaged"]))
        payload["random_seed"] = int(float(payload["random_seed"]))
        payload["is_synthetic"] = str(payload["is_synthetic"]).lower() == "true"
        validate_stiffness_row(payload)
        checked += 1

    assert checked == len(rows) == 520


def test_the_contract_version_is_pinned():
    """Bumping this is a deliberate, breaking act -- it should fail a test."""
    assert CONTRACT_VERSION == "1.0"
    assert PairedExperimentResult.model_fields["schema_version"].is_required()
