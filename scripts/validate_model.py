#!/usr/bin/env python
"""Verify the ML bundle is loadable, faithful and self-consistent.

The decisive check is **reproduction**: the release ships
``data/ml/reports/{validation,test}_predictions.csv``, so we re-predict the
corresponding splits and confirm we match. If that passes, the pipeline in this
environment is numerically the same one that produced the published metrics.

    python scripts/validate_model.py

Exit code 0 = all checks passed, 1 = a check failed.
"""

from __future__ import annotations

import hashlib
import json
import sys
import warnings
from pathlib import Path

# scripts/ is not a package, so the shared console helper is imported by
# path. init_console() must run before any output is written.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _console import init_console

init_console()

warnings.filterwarnings("ignore")

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

# CSV reports are written at limited precision, so exact equality is impossible.
# 1e-4 is far tighter than the ~1e-6 round-trip error and far looser than any
# real numerical divergence.
REPRODUCTION_TOLERANCE = 1e-4

# A frozen input whose prediction must not move between environments.
SMOKE_INPUT = {
    "protein_length": 76.0,
    "molecular_weight": 8564.7357,
    "hydrophobic_fraction": 0.34210526315789475,
    "charged_fraction": 0.2894736842105263,
    "residue_index_norm": 0.5,
    "residue_sasa_norm": 0.75,
    "residue_contact_count": 6.0,
    "proxy_rank": 1.0,
    "residue_type": "LYS",
    "qualitative_susceptibility": "medium",
    "scenario_id": "GCR_DEEP_SPACE_REFERENCE",
    "radiation_class": "GCR",
    "environment": "free_space",
    "proxy_type": "SIDE_CHAIN_LOSS",
}

_results: list[tuple[bool, str, str]] = []


def check(passed: bool, name: str, detail: str = "") -> bool:
    _results.append((passed, name, detail))
    print(f"  [{'PASS' if passed else 'FAIL'}] {name}" + (f" - {detail}" if detail else ""))
    return passed


def main() -> int:
    import joblib
    import numpy as np
    import pandas as pd

    print("COSMORA model validation")
    print("=" * 74)

    # --- environment ----------------------------------------------------
    print("\n[1] Environment")
    import sklearn

    check(
        sys.version_info[:2] == (3, 11),
        "Python 3.11",
        f"running {sys.version.split()[0]}",
    )
    check(
        sklearn.__version__ == "1.7.1",
        "scikit-learn == 1.7.1 (version the bundle was fitted with)",
        f"found {sklearn.__version__}",
    )
    check(
        int(np.__version__.split(".")[0]) >= 2,
        "NumPy >= 2 (the pickle references numpy._core)",
        f"found {np.__version__}",
    )

    # --- integrity ------------------------------------------------------
    print("\n[2] Bundle integrity")
    bundle_path = REPO / "models" / "COSMORA_mock_model_bundle.pkl"
    if not check(bundle_path.exists(), "bundle file present", str(bundle_path)):
        return 1
    digest = hashlib.sha256(bundle_path.read_bytes()).hexdigest()
    manifest = json.loads(
        (REPO / "models" / "release_manifest.json").read_text(encoding="utf-8")
    )
    check(
        digest == manifest["model_sha256"],
        "SHA-256 matches release_manifest.json",
        digest[:16] + "...",
    )

    # --- load -----------------------------------------------------------
    print("\n[3] Load")
    bundle = joblib.load(bundle_path)
    check(isinstance(bundle, dict), "bundle is a dict")
    for key in ("pipeline", "feature_columns", "target_column", "model_version"):
        check(key in bundle, f"bundle has '{key}'")
    pipeline = bundle["pipeline"]
    check(hasattr(pipeline, "predict"), "pipeline exposes .predict()")
    steps = [n for n, _ in pipeline.steps]
    check(
        steps == ["preprocessor", "model"],
        "pipeline steps are ['preprocessor', 'model']",
        str(steps),
    )

    # --- schema agreement -----------------------------------------------
    print("\n[4] Feature schema agreement")
    from app.ml.feature_schema import load_feature_schema

    schema = load_feature_schema()
    pre = pipeline.named_steps["preprocessor"]
    encoder = pre.transformers_[1][1].named_steps["encoder"]
    live_vocab = {
        c: [str(v) for v in cats]
        for c, cats in zip(pre.transformers_[1][2], encoder.categories_, strict=False)
    }
    check(
        schema.feature_order == list(bundle["feature_columns"]),
        "schema feature order matches the bundle",
    )
    check(schema.vocabulary == live_vocab, "schema vocabularies match the encoder")
    check(
        encoder.handle_unknown == "ignore",
        "encoder handle_unknown is 'ignore' (unknown categories must be pre-detected)",
    )
    check(
        schema.bundle_sha256 == digest,
        "schema records the current bundle hash",
    )

    # --- reproduction (the decisive check) ------------------------------
    print("\n[5] Reproduction of shipped prediction reports")
    features = schema.feature_order
    all_ok = True
    for split, report_name in (
        ("validation", "validation_predictions.csv"),
        ("test", "test_predictions.csv"),
    ):
        split_path = REPO / "data" / "ml" / "splits" / f"{split}.csv"
        report_path = REPO / "data" / "ml" / "reports" / report_name
        if not (split_path.exists() and report_path.exists()):
            all_ok &= check(False, f"{split} split and report present")
            continue
        X = pd.read_csv(split_path)
        shipped = pd.read_csv(report_path)
        predicted = np.asarray(pipeline.predict(X[features]), dtype=float)
        reference = shipped["predicted_mechanical_degradation_pct"].to_numpy(dtype=float)
        max_diff = float(np.abs(predicted - reference).max())
        all_ok &= check(
            max_diff < REPRODUCTION_TOLERANCE,
            f"{split}: reproduces shipped predictions ({len(X)} rows)",
            f"max|diff| = {max_diff:.3e} (tolerance {REPRODUCTION_TOLERANCE:g})",
        )

        # Confirm the published held-out metrics too.
        truth = shipped["mechanical_degradation_pct"].to_numpy(dtype=float)
        mae = float(np.abs(predicted - truth).mean())
        published = json.loads(
            (REPO / "models" / "model_metadata.json").read_text(encoding="utf-8")
        )[f"{split}_metrics"]["mae"]
        all_ok &= check(
            abs(mae - published) < 1e-3,
            f"{split}: MAE matches model_metadata.json",
            f"computed {mae:.6f} vs published {published:.6f}",
        )

    # --- deterministic smoke test ---------------------------------------
    print("\n[6] Deterministic smoke test")
    frame = pd.DataFrame([SMOKE_INPUT], columns=features)
    a = float(pipeline.predict(frame)[0])
    b = float(pipeline.predict(frame)[0])
    check(a == b, "repeated prediction is identical", f"{a:.10f}")
    check(
        0.0 <= a <= 100.0,
        "smoke prediction is inside [0, 100] %",
        f"{a:.4f} %",
    )
    target_range = schema.target_train_range
    check(
        target_range.min <= a <= target_range.max,
        "smoke prediction is inside the training target range",
        f"{a:.4f} % in [{target_range.min:.2f}, {target_range.max:.2f}]",
    )

    # --- unknown-category behaviour -------------------------------------
    print("\n[7] Unknown-category behaviour (must be detectable, not silent)")
    from app.ml.inference import check_unknown_categories

    bad = dict(SMOKE_INPUT, residue_type="XXX")
    findings = check_unknown_categories(pd.DataFrame([bad], columns=features), schema)
    check(
        any(f["column"] == "residue_type" for f in findings),
        "an unseen residue_type is detected before predicting",
        f"{len(findings)} finding(s)",
    )
    # And confirm why detection is necessary: the model answers anyway.
    still_predicts = float(pipeline.predict(pd.DataFrame([bad], columns=features))[0])
    check(
        np.isfinite(still_predicts),
        "the model silently returns a number for unknown input (hence the guard)",
        f"{still_predicts:.4f} % with an all-zero residue_type block",
    )

    # --- summary --------------------------------------------------------
    failed = [name for ok, name, _ in _results if not ok]
    print("\n" + "=" * 74)
    print(f"{len(_results) - len(failed)}/{len(_results)} checks passed")
    if failed:
        print("\nFAILED:")
        for name in failed:
            print(f"  - {name}")
        return 1
    print("\nModel bundle is loadable, faithful to its published metrics, and "
          "consistent with models/feature_schema.json.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
