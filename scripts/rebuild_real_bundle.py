#!/usr/bin/env python
"""Rebuild the real model bundle locally from the Kaggle results CSV.

The bundle Kaggle exported cannot be loaded here: it was fitted under an older
scikit-learn that pickled ``_RemainderColsList``, a private class that no longer
exists in the pinned 1.7.1. Rather than unpin scikit-learn -- which would also
invalidate the mock bundle and its CI check -- this refits the same pipeline on
the same rows under the pinned environment.

The aggregation, feature list, model hyperparameters and validation criteria are
copied from notebooks/COSMORA_kaggle_pipeline.ipynb, so the metrics reproduce.

Usage:
    .venv311/Scripts/python.exe scripts/rebuild_real_bundle.py
        --results <path to stiffness_results_REAL_v1.csv>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyRegressor
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

REPO = Path(__file__).resolve().parents[1]

GROUP = ["protein_id", "severity_label", "damage_residue_ids"]
FEATURE_COLS = [
    "protein_length", "molecular_weight", "hydrophobic_fraction",
    "charged_fraction", "residue_index_norm", "residue_sasa_norm",
    "residue_contact_count", "proxy_rank", "n_residues_damaged",
    "n_atoms_removed", "baseline_end_to_end_nm",
]
CAT_COLS = ["residue_type", "qualitative_susceptibility", "severity_label"]
MIN_SEEDS, MAX_SEM = 3, 15.0
VALIDATION_CRITERIA = {
    "min_labels": 30,
    "min_proteins": 8,
    "max_label_sem_pp": 10.0,
    "must_beat_mean_baseline": True,
}


def aggregate(raw: pd.DataFrame) -> pd.DataFrame:
    """Collapse seeds into one label per perturbation, carrying its own error."""
    ok = raw[(raw["status"] == "COMPLETED") & raw["mechanical_degradation_pct"].notna()]
    print(f"{len(raw)} experiments, {len(ok)} passed QC ({len(ok)/max(len(raw),1):.0%})")

    agg = ok.groupby(GROUP).agg(
        n_seeds=("mechanical_degradation_pct", "size"),
        target=("mechanical_degradation_pct", "mean"),
        target_std=("mechanical_degradation_pct", "std"),
        baseline_mean=("baseline_stiffness", "mean"),
        damaged_mean=("damaged_stiffness", "mean"),
        **{c: (c, "first") for c in FEATURE_COLS + CAT_COLS if c not in GROUP},
    ).reset_index()
    agg["target_sem"] = agg["target_std"] / np.sqrt(agg["n_seeds"])
    agg["usable"] = (agg["n_seeds"] >= MIN_SEEDS) & (agg["target_sem"] <= MAX_SEM)

    print(f"\n{len(agg)} perturbations, {int(agg['usable'].sum())} usable "
          f"(n>={MIN_SEEDS}, SE<={MAX_SEM} pp)")
    typical = agg["target_std"].median()
    if typical and not math.isnan(typical):
        print(f"median per-perturbation label std: {typical:.1f} pp")
        for tgt in (10, 5, 2):
            print(f"  seeds needed for SE +/-{tgt} pp: {math.ceil((typical/tgt)**2)}")
    return agg


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True, type=Path)
    ap.add_argument("--out", type=Path, default=REPO / "models")
    args = ap.parse_args()

    raw = pd.read_csv(args.results).drop_duplicates("experiment_id")
    agg = aggregate(raw)

    train = agg[agg["usable"].astype(bool)].copy()
    n_groups = train["protein_id"].nunique()
    X = pd.get_dummies(train[FEATURE_COLS + CAT_COLS], columns=CAT_COLS)
    y = train["target"].to_numpy()
    n_splits = min(5, n_groups)

    preds, base_preds = np.zeros(len(y)), np.zeros(len(y))
    for tr, te in GroupKFold(n_splits=n_splits).split(X, y, train["protein_id"]):
        m = xgb.XGBRegressor(
            n_estimators=300, max_depth=3, learning_rate=0.05, subsample=0.9,
            colsample_bytree=0.8, reg_lambda=1.0, random_state=42, n_jobs=4)
        m.fit(X.iloc[tr], y[tr])
        preds[te] = m.predict(X.iloc[te])
        base_preds[te] = DummyRegressor(strategy="mean").fit(
            X.iloc[tr], y[tr]).predict(X.iloc[te])

    cv_r2, cv_mae = r2_score(y, preds), mean_absolute_error(y, preds)
    base_r2 = r2_score(y, base_preds)
    signal_var, noise_var = float(np.var(y)), float(np.mean(train["target_sem"] ** 2))
    ceiling = max(0.0, 1 - noise_var / signal_var) if signal_var > 0 else 0.0

    print(f"\nheld-out-protein CV over {n_splits} folds, {len(y)} labels\n")
    print(f"  model     MAE {cv_mae:7.2f} pp   R2 {cv_r2:6.3f}")
    print(f"  mean-only MAE {mean_absolute_error(y, base_preds):7.2f} pp "
          f"  R2 {base_r2:6.3f}")
    print(f"\n  label-noise R2 ceiling: {ceiling:.3f}")

    X_raw = train[FEATURE_COLS + CAT_COLS].copy()
    pipeline = Pipeline([
        ("preprocessor", ColumnTransformer([
            ("num", StandardScaler(), FEATURE_COLS),
            ("cat", OneHotEncoder(handle_unknown="ignore"), CAT_COLS),
        ])),
        ("model", xgb.XGBRegressor(
            n_estimators=300, max_depth=3, learning_rate=0.05, subsample=0.9,
            colsample_bytree=0.8, reg_lambda=1.0, random_state=42)),
    ]).fit(X_raw, y)

    failed = []
    if len(train) < VALIDATION_CRITERIA["min_labels"]:
        failed.append(
            f"only {len(train)} labels, need {VALIDATION_CRITERIA['min_labels']}")
    if n_groups < VALIDATION_CRITERIA["min_proteins"]:
        failed.append(
            f"only {n_groups} proteins, need {VALIDATION_CRITERIA['min_proteins']}")
    worst_sem = float(train["target_sem"].max())
    if worst_sem > VALIDATION_CRITERIA["max_label_sem_pp"]:
        failed.append(f"worst label SE {worst_sem:.1f} pp exceeds "
                      f"{VALIDATION_CRITERIA['max_label_sem_pp']} pp")
    if cv_r2 <= base_r2:
        failed.append(f"held-out R2 {cv_r2:.3f} does not beat the mean "
                      f"baseline {base_r2:.3f}")

    metadata = {
        "model_name": "COSMORA Real Simulation Model",
        "model_version": "1.0.0-real",
        "scientific_status": "REAL_PAIRED_SIMULATION_LABELS",
        "label_source": "COSMORA_PAIRED_STEERED_MD",
        "scientifically_validated": not failed,
        "validation_criteria": VALIDATION_CRITERIA,
        "validation_failures": failed,
        "approved_use": ("SCIENTIFIC_INFERENCE_WITHIN_STATED_LIMITS" if not failed
                         else "RESEARCH_PREVIEW_LIMITATIONS_DISCLOSED"),
        "target_column": "mechanical_degradation_pct",
        "target_definition": ("(baseline_stiffness - damaged_stiffness) / "
                              "baseline_stiffness * 100, from paired steered-MD pulls"),
        "target_unit": "percent",
        "stiffness_unit": "pN/nm",
        "feature_columns": FEATURE_COLS + CAT_COLS,
        "numeric_features": FEATURE_COLS,
        "categorical_features": CAT_COLS,
        "n_training_labels": int(len(train)),
        "n_proteins": int(n_groups),
        "proteins": sorted(train["protein_id"].unique().tolist()),
        "seeds_per_label_median": float(train["n_seeds"].median()),
        "label_sem_pp_median": float(train["target_sem"].median()),
        "label_sem_pp_max": worst_sem,
        "cv_scheme": "GroupKFold by protein (held-out protein)",
        "cv_r2": float(cv_r2),
        "cv_mae_pp": float(cv_mae),
        "mean_baseline_r2": float(base_r2),
        "label_noise_r2_ceiling": float(ceiling),
        "sim_config_hash": str(raw["sim_config_hash"].iloc[0]),
        "excluded_features": {
            "scenario_id": ("does not enter the simulation, so it carries no signal "
                            "and would be fitted to noise"),
            "dose_gy / let / fluence": ("not consumed by the simulation and not "
                                        "verified against NASA references"),
        },
        "limitations": [
            "Radiation is not simulated. The damage proxy is a side-chain truncation "
            "at residues selected for literature radiosensitivity.",
            "Pulls are 40 ps of non-equilibrium steered MD, ~1e6 times faster than "
            "an AFM experiment. Absolute forces are not comparable to experiment.",
            "Severity is a count of removed side chains and is not a dose.",
            "The target carries measurable run-to-run noise; see label_sem_pp_median.",
        ],
        "rebuilt_locally": ("Refitted from stiffness_results_REAL_v1.csv under the "
                            "pinned scikit-learn 1.7.1; the Kaggle export referenced "
                            "a private class removed in that version."),
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }

    bundle = {
        "pipeline": pipeline,
        "metadata": metadata,
        "feature_columns": FEATURE_COLS + CAT_COLS,
        "target_column": "mechanical_degradation_pct",
        "model_version": metadata["model_version"],
        "scientific_status": metadata["scientific_status"],
    }

    args.out.mkdir(parents=True, exist_ok=True)
    bundle_path = args.out / "COSMORA_real_model_bundle.pkl"
    joblib.dump(bundle, bundle_path, compress=3)
    digest = hashlib.sha256(bundle_path.read_bytes()).hexdigest()
    (args.out / "real_model_metadata.json").write_text(
        json.dumps(metadata, indent=2, default=str), encoding="utf-8")
    (args.out / "real_release_manifest.json").write_text(json.dumps({
        "model_file": bundle_path.name,
        "model_sha256": digest,
        "metadata_file": "real_model_metadata.json",
        "scientific_status": metadata["scientific_status"],
        "created_at_utc": metadata["created_at_utc"],
    }, indent=2, default=str), encoding="utf-8")

    print(f"\nexported {bundle_path.name} ({bundle_path.stat().st_size:,} bytes)")
    print(f"  sha256                    {digest[:32]}...")
    print(f"  labels / proteins         {len(train)} / {n_groups}")
    print(f"  scientifically_validated: {not failed}")
    for reason in failed:
        print(f"    unmet: {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
