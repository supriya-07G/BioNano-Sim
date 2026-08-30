"""Tests for the reproducibility manifest builder (issue #25).

The acceptance criterion is that, given a report, the team can identify exactly
which code, structures, model and settings produced every displayed number. So
these assert the manifest actually carries those things -- and that the release
gate refuses to write one with holes.

A manifest that silently omits the model hash is worse than no manifest: it
looks like provenance. The gate is the point of the feature, so it is tested
harder than the happy path.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
BUILDER = REPO / "scripts" / "build_reproducibility_manifest.py"


def run(out: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(BUILDER), "--out", str(out), *extra],
        capture_output=True, text=True, cwd=REPO,
    )


def repo_env() -> dict[str, str]:
    """A copy of the script placed elsewhere resolves REPO to its own parent,
    so the real package roots have to reach it through PYTHONPATH."""
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(REPO), str(REPO / "backend")])
    return env


@pytest.fixture(scope="module")
def manifest(tmp_path_factory) -> dict:
    out = tmp_path_factory.mktemp("repro") / "manifest.json"
    result = run(out)
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(out.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# What a reader needs to reproduce a number
# --------------------------------------------------------------------------- #
def test_the_code_is_identified(manifest):
    assert len(manifest["git"]["commit"]) == 40
    assert manifest["code"]["contract_version"] == "1.0"


def test_the_damage_transformation_is_versioned(manifest):
    """Two proxy versions produce different lesions from the same input."""
    assert manifest["code"]["damage_proxy_type"] == "SIDE_CHAIN_LOSS"
    assert manifest["code"]["damage_proxy_version"]


def test_the_environment_is_recorded(manifest):
    env = manifest["environment"]
    assert env["python"].startswith("3.11")
    assert env["openmm"]
    assert env["forcefield"] == ["amber14-all.xml", "implicit/gbn2.xml"]
    assert env["openmm_platforms"], "the resolved platform changes results"


def test_the_model_bundles_are_hashed(manifest):
    models = manifest["models"]
    assert len(models["real_bundle_sha256"]) == 64
    assert len(models["mock_bundle_sha256"]) == 64
    assert models["real_bundle_sha256"] != models["mock_bundle_sha256"]


def test_the_dataset_is_hashed_and_counted(manifest):
    dataset = manifest["dataset"]
    assert len(dataset["dataset_sha256"]) == 64
    assert len(dataset["manifest_sha256"]) == 64
    assert dataset["rows_total"] == 520
    assert dataset["rows_accepted"] == 130


def test_the_input_structures_are_hashed(manifest):
    structures = manifest["structures"]
    assert len(structures) >= 5
    assert all(len(digest) == 64 for digest in structures.values())


def test_the_full_protocol_is_recorded(manifest):
    """Every parameter that changes the measured stiffness."""
    protocol = manifest["protocol"]
    for key in ("production_steps", "equilibration_steps", "minimisation_steps",
                "spring_constant_kj_mol_nm2", "pull_velocity_nm_per_ps",
                "temperature_kelvin", "timestep_fs", "friction_per_ps",
                "pull_anchor", "pull_attachment", "sim_config_hash"):
        assert protocol.get(key) is not None, f"{key} is missing"


def test_the_seeds_are_recorded(manifest):
    assert manifest["protocol"]["seeds"] == [1, 2, 3, 4, 5]


def test_a_protocol_mismatch_is_reported_not_hidden(manifest):
    """The dataset came from the Kaggle notebook, which hashes its own dict.

    The two hashes therefore disagree today. The manifest must say so plainly:
    a reader who assumed this checkout's protocol produced those rows would be
    wrong, and silence would let them assume it.
    """
    match = manifest["protocol_matches_dataset"]
    assert isinstance(match["matches"], bool)
    assert len(match["local_sim_config_hash"]) == 64
    assert match["dataset_sim_config_hashes"]

    if not match["matches"]:
        assert match["local_sim_config_hash"] not in match["dataset_sim_config_hashes"]
        assert "not evidence" in match["note"]
    else:
        assert match["local_sim_config_hash"] in match["dataset_sim_config_hashes"]


# --------------------------------------------------------------------------- #
# The release gate
# --------------------------------------------------------------------------- #
def test_provenance_is_reported_complete(manifest):
    assert manifest["provenance_complete"] is True
    assert manifest["provenance_missing"] == []


def test_a_tag_is_recorded_when_given(tmp_path):
    out = tmp_path / "m.json"
    run(out, "--tag", "v9.9.9")
    assert json.loads(out.read_text(encoding="utf-8"))["release_tag"] == "v9.9.9"


def test_the_release_gate_rejects_missing_provenance(tmp_path, monkeypatch):
    """Simulated by requiring a field that cannot be present."""
    script = BUILDER.read_text(encoding="utf-8")
    patched = script.replace(
        '    "structures",\n)', '    "structures",\n    "does.not.exist",\n)'
    )
    fake = tmp_path / "builder.py"
    fake.write_text(patched, encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(fake), "--out", str(tmp_path / "m.json"), "--release"],
        capture_output=True, text=True, cwd=REPO, env=repo_env(),
    )
    assert result.returncode == 1
    assert "refusing to publish" in result.stderr
    assert "does.not.exist" in result.stdout


def test_without_release_an_incomplete_manifest_only_warns(tmp_path):
    script = BUILDER.read_text(encoding="utf-8")
    patched = script.replace(
        '    "structures",\n)', '    "structures",\n    "does.not.exist",\n)'
    )
    fake = tmp_path / "builder.py"
    fake.write_text(patched, encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(fake), "--out", str(tmp_path / "m.json")],
        capture_output=True, text=True, cwd=REPO, env=repo_env(),
    )
    assert result.returncode == 0
    assert "WARN" in result.stdout


def test_the_manifest_records_whether_the_tree_was_dirty(manifest):
    """A number produced from uncommitted code is not reproducible."""
    assert isinstance(manifest["git"]["dirty"], bool)
