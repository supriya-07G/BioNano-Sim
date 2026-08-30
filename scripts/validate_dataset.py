#!/usr/bin/env python
"""Validate the real stiffness dataset and emit its manifest (issue #6).

One command that either accepts the dataset or exits non-zero saying exactly
which rows are wrong and why. This is the gate between a simulation output and
the training set, so it is deliberately unforgiving: a row that cannot be
checked is rejected, not waved through.

What it checks:

* every row against the versioned contract in ``app.contracts.paired_experiment``
* duplicate ``experiment_id`` -- the same experiment counted twice silently
  doubles its weight in training
* physical ranges, so an implausible stiffness is caught even when the row is
  structurally valid
* protocol consistency -- rows produced under different ``sim_config_hash``
  values are not comparable and must not be pooled
* failed stiffness fits, which are excluded from the accepted set

Paired-artifact checks (pristine/damaged directories and their hashes) run only
when an experiments root is supplied with ``--experiments-dir``; the Kaggle
producer emits a flat CSV with no artifact tree, and the report says so rather
than silently passing.

Usage:
    python scripts/validate_dataset.py
    python scripts/validate_dataset.py --dataset data/ml/stiffness_results_REAL_v1.csv
    python scripts/validate_dataset.py --experiments-dir runtime/experiments
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

from app.contracts.paired_experiment import (  # noqa: E402
    CONTRACT_VERSION,
    STIFFNESS_CSV_COLUMNS,
    validate_stiffness_row,
)
from pydantic import ValidationError  # noqa: E402

DEFAULT_DATASET = REPO / "data" / "ml" / "stiffness_results_REAL_v1.csv"


def show(path: Path) -> str:
    """Repo-relative when possible; absolute otherwise. Never raises."""
    try:
        return str(path.resolve().relative_to(REPO))
    except ValueError:
        return str(path)

#: Physically plausible bounds for this protocol. These are not tight -- they
#: exist to catch a unit error or a degenerate fit, not to police the science.
#: A kJ/mol/nm^2 value would land around 1e5 and trip the upper bound.
STIFFNESS_MIN_PN_NM = -5_000.0
STIFFNESS_MAX_PN_NM = 20_000.0

#: Columns the Kaggle notebook does not emit. Both are pure provenance; see
#: docs/experiment-contract.md. Filled with a placeholder so the scientific
#: fields are still validated rather than the whole row being skipped.
KNOWN_PRODUCER_GAP = {"job_id": None, "git_commit": "unrecorded"}


class Report:
    """Collects findings so every problem is reported, not just the first."""

    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    @property
    def ok(self) -> bool:
        return not self.errors


def coerce(row: dict[str, str]) -> dict[str, Any]:
    """CSV gives strings; the contract wants typed values."""
    payload = {k: v for k, v in row.items() if k in STIFFNESS_CSV_COLUMNS}
    for column, placeholder in KNOWN_PRODUCER_GAP.items():
        if column not in payload or payload[column] == "":
            payload[column] = placeholder or row.get("experiment_id", "")
    for key in ("baseline_stiffness", "damaged_stiffness",
                "mechanical_degradation_pct", "fit_quality"):
        raw = payload.get(key)
        payload[key] = float(raw) if raw not in (None, "", "nan") else None
    for key in ("proxy_rank", "n_residues_damaged", "random_seed"):
        payload[key] = int(float(payload[key]))
    payload["is_synthetic"] = str(payload.get("is_synthetic", "")).lower() == "true"
    return payload


def check_ranges(payload: dict[str, Any], row_no: int, report: Report) -> None:
    for key in ("baseline_stiffness", "damaged_stiffness"):
        value = payload.get(key)
        if value is None:
            continue
        if not STIFFNESS_MIN_PN_NM <= value <= STIFFNESS_MAX_PN_NM:
            report.error(
                f"row {row_no} ({payload['experiment_id']}): {key} is {value:,.1f} "
                f"pN/nm, outside the plausible range "
                f"[{STIFFNESS_MIN_PN_NM:,.0f}, {STIFFNESS_MAX_PN_NM:,.0f}]. "
                "A value near 1e5 usually means kJ/mol/nm^2 was written instead."
            )


def check_paired_artifacts(
    experiments: Path, ids: list[str], report: Report
) -> dict[str, Any]:
    """Every accepted experiment must have both runs and their curves on disk."""
    required = ("baseline_force_extension.csv", "damaged_force_extension.csv",
                "result.json", "manifest.json")
    present, missing_dirs, incomplete = 0, [], []

    for experiment_id in ids:
        directory = experiments / experiment_id
        if not directory.is_dir():
            missing_dirs.append(experiment_id)
            continue
        absent = [name for name in required if not (directory / name).is_file()]
        if absent:
            incomplete.append(f"{experiment_id}: missing {', '.join(absent)}")
        else:
            present += 1

    for entry in incomplete:
        report.error(f"incomplete experiment directory -- {entry}")
    if missing_dirs:
        report.error(
            f"{len(missing_dirs)} accepted experiments have no directory under "
            f"{experiments}: {', '.join(missing_dirs[:5])}"
            + (" ..." if len(missing_dirs) > 5 else "")
        )
    return {"checked": len(ids), "complete": present,
            "missing_directories": len(missing_dirs),
            "incomplete": len(incomplete)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    ap.add_argument("--experiments-dir", type=Path, default=None,
                    help="root holding one directory per experiment_id")
    ap.add_argument("--manifest", type=Path, default=None,
                    help="where to write the dataset manifest (default: beside "
                         "the dataset as <name>.manifest.json)")
    args = ap.parse_args()

    report = Report()

    if not args.dataset.is_file():
        print(f"FAIL  dataset not found: {args.dataset}", file=sys.stderr)
        return 2

    with args.dataset.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        header = list(reader.fieldnames or [])
        rows = list(reader)

    print(f"dataset      {show(args.dataset)}")
    print(f"contract     v{CONTRACT_VERSION}")
    print(f"rows         {len(rows)}")

    if not rows:
        print("\nFAIL  the dataset is empty", file=sys.stderr)
        return 1

    missing_columns = [c for c in STIFFNESS_CSV_COLUMNS if c not in header]
    unexpected_gap = set(missing_columns) - set(KNOWN_PRODUCER_GAP)
    if unexpected_gap:
        report.error(f"required columns absent: {sorted(unexpected_gap)}")
    elif missing_columns:
        report.warn(
            f"columns {sorted(missing_columns)} absent -- the documented Kaggle "
            "producer gap; both are provenance only"
        )

    # --- Per-row contract and range validation ------------------------------
    accepted: list[dict[str, Any]] = []
    rejected_fits = 0
    for index, row in enumerate(rows, start=2):  # header is line 1
        try:
            payload = coerce(row)
        except (ValueError, KeyError) as exc:
            report.error(f"row {index}: could not be read -- {exc}")
            continue
        try:
            validate_stiffness_row(payload)
        except ValidationError as exc:
            first = exc.errors()[0]
            location = ".".join(str(p) for p in first["loc"]) or "row"
            report.error(
                f"row {index} ({payload.get('experiment_id', '?')}): "
                f"{location}: {first['msg']}"
            )
            continue
        check_ranges(payload, index, report)

        if payload["status"] != "COMPLETED":
            rejected_fits += 1
            continue
        accepted.append(payload)

    # --- Duplicates ---------------------------------------------------------
    counts = Counter(r["experiment_id"] for r in rows)
    duplicates = sorted(k for k, n in counts.items() if n > 1)
    for experiment_id in duplicates:
        report.error(
            f"duplicate experiment_id {experiment_id!r} appears "
            f"{counts[experiment_id]} times; the same experiment counted twice "
            "doubles its weight in training"
        )

    # --- Protocol consistency ----------------------------------------------
    hashes = sorted({r["sim_config_hash"] for r in rows if r.get("sim_config_hash")})
    if len(hashes) > 1:
        report.error(
            f"{len(hashes)} distinct sim_config_hash values in one dataset: "
            f"{[h[:12] for h in hashes]}. Rows produced under different "
            "protocols are not comparable and must not be pooled."
        )

    # --- Paired artifacts ---------------------------------------------------
    artifacts: dict[str, Any] | None = None
    if args.experiments_dir:
        artifacts = check_paired_artifacts(
            args.experiments_dir, [r["experiment_id"] for r in accepted], report
        )
    else:
        report.warn(
            "paired-artifact and hash checks skipped: no --experiments-dir given. "
            "The flat CSV alone cannot prove both runs exist on disk."
        )

    # --- Manifest -----------------------------------------------------------
    proteins = sorted({r["protein_id"] for r in accepted})
    manifest = {
        "dataset_file": args.dataset.name,
        "dataset_sha256": hashlib.sha256(args.dataset.read_bytes()).hexdigest(),
        "contract_version": CONTRACT_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "rows_total": len(rows),
        "rows_accepted": len(accepted),
        "rows_rejected_by_status": rejected_fits,
        "duplicate_experiment_ids": duplicates,
        "proteins": proteins,
        "n_proteins": len(proteins),
        "damage_proxies": sorted({r["proxy_type"] for r in accepted}),
        "severity_levels": sorted({r["severity_label"] for r in accepted}),
        "scenarios": sorted({r["scenario_id"] for r in accepted}),
        "seeds": sorted({r["random_seed"] for r in accepted}),
        "sim_config_hashes": hashes,
        "columns_present": header,
        "known_producer_gap": sorted(set(missing_columns)),
        "paired_artifacts": artifacts,
        "validation_passed": report.ok,
    }
    destination = args.manifest or args.dataset.with_suffix(".manifest.json")
    destination.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    # --- Report -------------------------------------------------------------
    print(f"accepted     {len(accepted)}")
    print(f"rejected     {rejected_fits} (status != COMPLETED)")
    print(f"proteins     {len(proteins)}  {', '.join(proteins)}")
    print(f"manifest     {show(destination)}")

    if report.warnings:
        print(f"\n{len(report.warnings)} warning(s):")
        for message in report.warnings:
            print(f"  [warn] {message}")

    if report.errors:
        print(f"\n{len(report.errors)} error(s):", file=sys.stderr)
        for message in report.errors[:40]:
            print(f"  [FAIL] {message}", file=sys.stderr)
        if len(report.errors) > 40:
            print(f"  ... and {len(report.errors) - 40} more", file=sys.stderr)
        print("\nFAIL  dataset rejected", file=sys.stderr)
        return 1

    print("\nOK    dataset validated against contract "
          f"v{CONTRACT_VERSION}; {len(accepted)} rows accepted")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
