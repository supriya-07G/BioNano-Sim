"""Tests for the real-dataset validator CLI (issue #6).

The acceptance criterion is behavioural: one command validates the dataset and
exits non-zero with clear messages. So these tests drive the CLI the way a
teammate or CI would, and assert on its exit code and its output -- not on
internals.

Each corruption is applied to a copy of the real dataset, one at a time, so a
failure names the single check that stopped working.
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
VALIDATOR = REPO / "scripts" / "validate_dataset.py"
REAL_CSV = REPO / "data" / "ml" / "stiffness_results_REAL_v1.csv"

pytestmark = pytest.mark.skipif(
    not REAL_CSV.exists(), reason="real dataset not present"
)


def run(dataset: Path, manifest: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(VALIDATOR), "--dataset", str(dataset),
         "--manifest", str(manifest), *extra],
        capture_output=True, text=True, cwd=REPO,
    )


@pytest.fixture(scope="module")
def rows() -> list[dict[str, str]]:
    with REAL_CSV.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: list[dict[str, str]]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


def corrupt(tmp_path: Path, rows: list[dict[str, str]], mutate) -> Path:
    copy = [dict(r) for r in rows]
    mutate(copy)
    return write_csv(tmp_path / "corrupt.csv", copy)


# --------------------------------------------------------------------------- #
# The happy path
# --------------------------------------------------------------------------- #
def test_the_real_dataset_passes(tmp_path):
    result = run(REAL_CSV, tmp_path / "m.json")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "dataset validated" in result.stdout


def test_a_manifest_is_written(tmp_path):
    manifest_path = tmp_path / "m.json"
    run(REAL_CSV, manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["rows_total"] == 520
    assert manifest["rows_accepted"] == 130
    assert manifest["validation_passed"] is True
    assert manifest["n_proteins"] == len(manifest["proteins"]) == 4
    assert len(manifest["dataset_sha256"]) == 64
    assert manifest["contract_version"] == "1.0"
    assert manifest["duplicate_experiment_ids"] == []


def test_the_manifest_records_coverage(tmp_path):
    manifest_path = tmp_path / "m.json"
    run(REAL_CSV, manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["severity_levels"] == ["EXTREME", "MILD", "MODERATE", "SEVERE"]
    assert manifest["damage_proxies"] == ["SIDE_CHAIN_LOSS"]
    assert manifest["seeds"] == [1, 2, 3, 4, 5]


def test_rejected_rows_are_excluded_from_accepted(tmp_path):
    """A QC-failed experiment must never reach the training set."""
    manifest_path = tmp_path / "m.json"
    run(REAL_CSV, manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["rows_accepted"] + manifest["rows_rejected_by_status"] == 520
    assert manifest["rows_rejected_by_status"] > 0, "this dataset does reject rows"


# --------------------------------------------------------------------------- #
# The corruptions, one at a time
# --------------------------------------------------------------------------- #
def test_a_duplicate_experiment_id_is_rejected(tmp_path, rows):
    path = corrupt(tmp_path, rows, lambda r: r.append(dict(r[0])))
    result = run(path, tmp_path / "m.json")
    assert result.returncode == 1
    assert "duplicate experiment_id" in result.stderr


def test_a_wrong_stiffness_unit_is_rejected(tmp_path, rows):
    def mutate(r):
        r[0]["stiffness_unit"] = "kJ/mol/nm^2"

    result = run(corrupt(tmp_path, rows, mutate), tmp_path / "m.json")
    assert result.returncode == 1
    assert "stiffness_unit" in result.stderr


def test_broken_degradation_arithmetic_is_rejected(tmp_path, rows):
    """The CSV feeds training, so it must not be the weaker check."""
    def mutate(r):
        r[0]["mechanical_degradation_pct"] = "99.0"

    result = run(corrupt(tmp_path, rows, mutate), tmp_path / "m.json")
    assert result.returncode == 1
    assert "mechanical_degradation_pct" in result.stderr


def test_an_implausible_stiffness_is_rejected(tmp_path, rows):
    """A kJ/mol/nm^2 value lands near 1e5 and must not pass as pN/nm.

    Degradation is recomputed to stay self-consistent, so the row is otherwise
    valid and only the range check can reject it.
    """
    def mutate(r):
        baseline, damaged = 1_445_000.0, float(r[0]["damaged_stiffness"])
        r[0]["baseline_stiffness"] = str(baseline)
        r[0]["mechanical_degradation_pct"] = str(
            (baseline - damaged) / baseline * 100.0
        )

    result = run(corrupt(tmp_path, rows, mutate), tmp_path / "m.json")
    assert result.returncode == 1
    assert "outside the plausible range" in result.stderr


def test_mixed_protocols_are_rejected(tmp_path, rows):
    def mutate(r):
        r[5]["sim_config_hash"] = "f" * 64

    result = run(corrupt(tmp_path, rows, mutate), tmp_path / "m.json")
    assert result.returncode == 1
    assert "sim_config_hash" in result.stderr


def test_a_synthetic_row_is_rejected(tmp_path, rows):
    def mutate(r):
        r[0]["is_synthetic"] = "True"

    result = run(corrupt(tmp_path, rows, mutate), tmp_path / "m.json")
    assert result.returncode == 1
    assert "is_synthetic" in result.stderr


def test_an_empty_dataset_is_rejected(tmp_path, rows):
    path = write_csv(tmp_path / "empty.csv", [dict.fromkeys(rows[0], "")])
    path.write_text(",".join(rows[0]) + "\n", encoding="utf-8")
    result = run(path, tmp_path / "m.json")
    assert result.returncode == 1
    assert "empty" in result.stderr


def test_a_missing_dataset_exits_two(tmp_path):
    result = run(tmp_path / "nope.csv", tmp_path / "m.json")
    assert result.returncode == 2
    assert "not found" in result.stderr


# --------------------------------------------------------------------------- #
# Paired artifacts
# --------------------------------------------------------------------------- #
def test_missing_experiment_directories_are_reported(tmp_path):
    """--experiments-dir turns on the on-disk checks; an empty root must fail."""
    empty = tmp_path / "experiments"
    empty.mkdir()
    result = run(REAL_CSV, tmp_path / "m.json", "--experiments-dir", str(empty))
    assert result.returncode == 1
    assert "have no directory" in result.stderr


def test_the_skip_is_announced_when_no_experiments_dir_is_given(tmp_path):
    """Silence would read as 'checked and fine'. It must say it skipped."""
    result = run(REAL_CSV, tmp_path / "m.json")
    assert "paired-artifact and hash checks skipped" in result.stdout


# --------------------------------------------------------------------------- #
# Quality gates barring rows from training (issue #13)
# --------------------------------------------------------------------------- #
def test_a_hopeless_fit_is_barred_from_training(tmp_path, rows):
    """Detection is not enough: the row must not reach the accepted set."""
    def mutate(r):
        r[0]["fit_quality"] = "0.05"

    result = run(corrupt(tmp_path, rows, mutate), tmp_path / "m.json")
    assert result.returncode == 1
    assert "barred from training" in result.stderr
    assert "not a measurement" in result.stderr


def test_the_gate_barred_count_is_reported(tmp_path, rows):
    def mutate(r):
        for row in r[:3]:
            row["fit_quality"] = "0.05"

    result = run(corrupt(tmp_path, rows, mutate), tmp_path / "m.json")
    assert "gate-barred  3" in result.stdout


def test_the_manifest_records_gate_barred_rows(tmp_path):
    manifest_path = tmp_path / "m.json"
    run(REAL_CSV, manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["rows_barred_by_quality_gate"] == 0


def test_a_marginal_fit_is_flagged_but_admitted(tmp_path, rows):
    """Warning, not rejection: usable in aggregate, worth a human's eye."""
    def mutate(r):
        r[0]["fit_quality"] = "0.35"

    result = run(corrupt(tmp_path, rows, mutate), tmp_path / "m.json")
    assert result.returncode == 0
    assert "flagged by a quality gate" in result.stdout
    assert "still admissible" in result.stdout
