"""Tests for paired mechanical experiments API endpoints (issue #7)."""

from __future__ import annotations

import csv
import json

import pytest


@pytest.fixture
def sample_experiment(tmp_path, monkeypatch):
    from app.config import settings

    root = tmp_path / "runtime" / "experiments"
    root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(settings, "runtime_dir", tmp_path / "runtime")

    exp_id = "1UBQ_MILD_74_seed1"
    exp_dir = root / exp_id
    exp_dir.mkdir(parents=True, exist_ok=True)

    result_json = {
        "experiment_id": exp_id,
        "schema_version": "1.0",
        "status": "COMPLETED",
        "protein_id": "1UBQ",
        "pdb_id": "1UBQ",
        "chain_id": "A",
        "uniprot_id": "P0CG48",
        "scenario_id": "GCR_DEEP_SPACE_REFERENCE",
        "scenario_version": "1.0",
        "damage_residue_id": "A:74",
        "residue_type": "ARG",
        "residue_index_norm": 0.973,
        "proxy_type": "SIDE_CHAIN_LOSS",
        "proxy_rank": 1,
        "severity_label": "MILD",
        "n_residues_damaged": 1,
        "damage_residue_ids": ["A:74"],
        "n_side_chain_atoms_removed": 7,
        "severity_is_a_dose": False,
        "random_seed": 1,
        "sim_config_hash": "779b297ee54d560c11b07397c92fa69e593a32de7fc748657547006a26ac50d5",
        "is_synthetic": False,
        "baseline_stiffness": 603.0,
        "damaged_stiffness": 504.0,
        "stiffness_unit": "pN/nm",
        "fit_quality": 0.98,
        "mechanical_degradation_pct": 16.4179,
        "baseline_fit": {
            "slope_pn_per_nm": 603.0,
            "intercept_pn": 0.0,
            "r_squared": 0.98,
            "n_points": 10,
            "fit_start_nm": 0.1,
            "fit_end_nm": 1.0,
            "reliable": True,
            "unreliable_reasons": [],
        },
        "damaged_fit": {
            "slope_pn_per_nm": 504.0,
            "intercept_pn": 0.0,
            "r_squared": 0.97,
            "n_points": 10,
            "fit_start_nm": 0.1,
            "fit_end_nm": 1.0,
            "reliable": True,
            "unreliable_reasons": [],
        },
        "qc_failures": [],
    }
    (exp_dir / "result.json").write_text(json.dumps(result_json, indent=2), encoding="utf-8")
    (exp_dir / "manifest.json").write_text(json.dumps({"protocol": "pulling_v1"}, indent=2), encoding="utf-8")
    (exp_dir / "damage_manifest.json").write_text(json.dumps({"removed_atoms": 7}, indent=2), encoding="utf-8")
    (exp_dir / "baseline_features.json").write_text(json.dumps({"rmsd_mean_nm": 0.15}, indent=2), encoding="utf-8")
    (exp_dir / "damaged_features.json").write_text(json.dumps({"rmsd_mean_nm": 0.22}, indent=2), encoding="utf-8")

    # Write force extension CSVs
    fe_header = ["time_ps", "restraint_center_nm", "end_to_end_nm", "extension_nm", "force_pn", "work_kj_mol", "potential_energy_kj_mol"]
    fe_rows = [
        ["0.0", "3.0", "3.0", "0.0", "0.0", "0.0", "-1000.0"],
        ["1.0", "3.05", "3.02", "0.02", "12.0", "0.1", "-995.0"],
    ]
    with (exp_dir / "baseline_force_extension.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(fe_header)
        w.writerows(fe_rows)

    with (exp_dir / "damaged_force_extension.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(fe_header)
        w.writerows(fe_rows)

    # Write dummy PDBs
    base_job = exp_dir / "baseline_job"
    base_job.mkdir(parents=True, exist_ok=True)
    (base_job / "final.pdb").write_text("ATOM      1  N   ALA A   1       0.0   0.0   0.0\nEND\n", encoding="utf-8")
    (base_job / "prepared.pdb").write_text("ATOM      1  N   ALA A   1       0.0   0.0   0.0\nEND\n", encoding="utf-8")

    dmg_job = exp_dir / "damaged_job"
    dmg_job.mkdir(parents=True, exist_ok=True)
    (dmg_job / "final.pdb").write_text("ATOM      1  N   ALA A   1       0.0   0.0   0.0\nEND\n", encoding="utf-8")

    return exp_id, exp_dir


def test_list_experiments(client, api, sample_experiment):
    exp_id, _ = sample_experiment
    response = client.get(f"{api}/experiments")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) >= 1
    item = next(i for i in body if i["experiment_id"] == exp_id)
    assert item["status"] == "COMPLETED"
    assert item["baseline_stiffness"] == 603.0
    assert item["damaged_stiffness"] == 504.0
    assert item["mechanical_degradation_pct"] == 16.4179
    assert item["stiffness_unit"] == "pN/nm"


def test_get_experiment_detail(client, api, sample_experiment):
    exp_id, _ = sample_experiment
    response = client.get(f"{api}/experiments/{exp_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["experiment_id"] == exp_id
    assert body["quality_status"] in ("valid", "warning")
    assert body["artifacts"]["result_json"] is True
    assert body["artifacts"]["baseline_force_extension"] is True
    assert body["baseline_fit"]["r_squared"] == 0.98


def test_get_experiment_not_found(client, api, sample_experiment):
    response = client.get(f"{api}/experiments/non_existent_id")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "NOT_FOUND"
    assert "request_id" in body["error"]


def test_get_experiment_invalid_id_traversal(client, api):
    response = client.get(f"{api}/experiments/..%2f..%2fsecret")
    assert response.status_code in (400, 404)
    body = response.json()
    assert "error" in body


def test_get_force_extension_series(client, api, sample_experiment):
    exp_id, _ = sample_experiment
    response = client.get(f"{api}/experiments/{exp_id}/force-extension")
    assert response.status_code == 200
    body = response.json()
    assert body["experiment_id"] == exp_id
    assert body["stiffness_unit"] == "pN/nm"
    assert len(body["baseline"]) == 2
    assert len(body["damaged"]) == 2
    assert body["baseline"][1]["force_pn"] == 12.0


def test_get_experiment_structures(client, api, sample_experiment):
    exp_id, _ = sample_experiment
    # baseline condition
    res_base = client.get(f"{api}/experiments/{exp_id}/structures/baseline")
    assert res_base.status_code == 200
    assert "ATOM" in res_base.text
    assert res_base.headers["content-type"].startswith("chemical/x-pdb")

    # damaged condition
    res_dmg = client.get(f"{api}/experiments/{exp_id}/structures/damaged")
    assert res_dmg.status_code == 200
    assert "ATOM" in res_dmg.text

    # invalid condition
    res_inv = client.get(f"{api}/experiments/{exp_id}/structures/invalid_cond")
    assert res_inv.status_code == 422


def test_get_experiment_report(client, api, sample_experiment):
    exp_id, _ = sample_experiment
    response = client.get(f"{api}/experiments/{exp_id}/report")
    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    body = response.json()
    assert body["experiment_id"] == exp_id
    assert body["result"]["baseline_stiffness"] == 603.0
    assert body["manifest"]["protocol"] == "pulling_v1"
    assert body["damage_manifest"]["removed_atoms"] == 7
    assert body["baseline_features"]["rmsd_mean_nm"] == 0.15


def test_import_experiment_success(client, api, sample_experiment, tmp_path):
    _, exp_dir = sample_experiment

    # Create an external directory
    ext_dir = tmp_path / "external_exp"
    import shutil
    shutil.copytree(exp_dir, ext_dir)

    response = client.post(
        f"{api}/experiments/import",
        json={"source_path": str(ext_dir), "experiment_id": "IMPORTED_EXP_1"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "imported"
    assert body["experiment_id"] == "IMPORTED_EXP_1"
    assert body["detail"]["baseline_stiffness"] == 603.0


def test_import_experiment_invalid_contract(client, api, tmp_path):
    bad_dir = tmp_path / "bad_exp"
    bad_dir.mkdir(parents=True)
    (bad_dir / "result.json").write_text(json.dumps({"invalid": True}), encoding="utf-8")

    response = client.post(
        f"{api}/experiments/import",
        json={"source_path": str(bad_dir)},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION_FAILED"
