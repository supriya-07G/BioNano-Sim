#!/usr/bin/env python
"""Collapse per-seed simulation rows into ML training labels with uncertainty.

Why this exists
---------------
A single steered-MD pull is one draw from a stochastic process. The measured
run-to-run spread of ``mechanical_degradation_pct`` on 1UBQ is comparable to,
and can exceed, the effect being measured. Training on individual runs therefore
means training on labels whose noise dominates their signal, and no amount of
model tuning recovers from that: the achievable R2 is capped by the label noise,
not by the model.

Averaging n independent seeds of the same perturbation shrinks the standard
error of the label by sqrt(n). This script does that, and -- just as importantly
-- reports the standard error so a row whose label is still too noisy can be
excluded rather than silently trained on.

Two estimators are reported because they fail differently:

  paired_mean : mean over seeds of the per-seed degradation. Each seed's
                baseline and damaged run share a seed and a starting structure,
                so the pairing cancels part of the noise before averaging.
  ratio_of_means : degradation computed from the mean baseline and the mean
                damaged stiffness. More stable when individual baselines are
                noisy, but it discards the pairing.

They should agree. A large disagreement means the pairing is not doing what it
is supposed to, and the batch needs investigating rather than training on.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
DEFAULT_IN = REPO / "data" / "ml" / "stiffness" / "stiffness_results_REAL_v1.csv"
DEFAULT_OUT = REPO / "data" / "ml" / "stiffness" / "ml_training_labels_v1.csv"

# A perturbation is identified by everything except the seed.
GROUP_KEYS = [
    "protein_id", "pdb_id", "chain_id", "scenario_id",
    "damage_residue_ids", "proxy_type", "severity_label", "sim_config_hash",
]

OUT_COLUMNS = [
    *GROUP_KEYS,
    "damage_residue_id", "residue_type", "proxy_rank",
    "n_seeds", "seeds",
    "baseline_stiffness_mean", "baseline_stiffness_std", "baseline_stiffness_sem",
    "baseline_stiffness_cv",
    "damaged_stiffness_mean", "damaged_stiffness_std", "damaged_stiffness_sem",
    "mechanical_degradation_pct",          # the ML target (paired mean)
    "mechanical_degradation_pct_std",
    "mechanical_degradation_pct_sem",
    "mechanical_degradation_pct_ratio_of_means",
    "estimator_disagreement_pct",
    "fit_quality_min", "stiffness_unit",
    "label_usable", "label_reject_reasons",
    "git_commit", "is_synthetic",
]


def _f(value: str | None) -> float | None:
    if value is None or value == "":
        return None
    try:
        out = float(value)
    except ValueError:
        return None
    return out if math.isfinite(out) else None


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs)


def std(xs: list[float]) -> float:
    """Sample standard deviation (n-1). Zero for a single observation."""
    if len(xs) < 2:
        return 0.0
    m = mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def sem(xs: list[float]) -> float:
    return std(xs) / math.sqrt(len(xs)) if len(xs) >= 2 else float("inf")


def seeds_needed(observed_std: float, target_sem: float) -> int | None:
    """How many seeds would bring the standard error under target_sem."""
    if observed_std <= 0 or target_sem <= 0:
        return None
    return max(1, math.ceil((observed_std / target_sem) ** 2))


def aggregate(
    rows: list[dict[str, str]], *, min_seeds: int, max_sem: float
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    groups: dict[tuple, list[dict[str, str]]] = defaultdict(list)
    skipped_incomplete = 0
    for row in rows:
        if row.get("status") != "COMPLETED":
            skipped_incomplete += 1
            continue
        if str(row.get("is_synthetic", "")).strip().lower() in ("true", "1"):
            skipped_incomplete += 1
            continue
        groups[tuple(row.get(k, "") for k in GROUP_KEYS)].append(row)

    out: list[dict[str, Any]] = []
    for key, members in sorted(groups.items()):
        base = [v for v in (_f(m["baseline_stiffness"]) for m in members) if v is not None]
        dmg = [v for v in (_f(m["damaged_stiffness"]) for m in members) if v is not None]
        if not base or not dmg or len(base) != len(dmg):
            continue

        per_seed = [
            (b - d) / b * 100.0
            for b, d in zip(base, dmg, strict=True)
            if b not in (0.0, None)
        ]
        base_m, dmg_m = mean(base), mean(dmg)
        ratio_of_means = (base_m - dmg_m) / base_m * 100.0 if base_m else None
        paired = mean(per_seed) if per_seed else None
        disagreement = (
            abs(paired - ratio_of_means)
            if paired is not None and ratio_of_means is not None else None
        )

        fits = [v for v in (_f(m.get("fit_quality")) for m in members) if v is not None]
        reasons: list[str] = []
        if len(members) < min_seeds:
            reasons.append(
                f"only {len(members)} seed(s); at least {min_seeds} are required to "
                "estimate the label's uncertainty"
            )
        label_sem = sem(per_seed) if per_seed else float("inf")
        if math.isfinite(label_sem) and label_sem > max_sem:
            reasons.append(
                f"label standard error is {label_sem:.2f} pct, above the {max_sem:.2f} "
                "pct ceiling; more seeds are needed before this row is trainable"
            )
        elif not math.isfinite(label_sem):
            reasons.append("standard error is undefined with a single seed")
        if fits and min(fits) < 0.5:
            reasons.append(f"weakest stiffness fit has r2 {min(fits):.3f}, below 0.5")

        first = members[0]
        out.append({
            **dict(zip(GROUP_KEYS, key, strict=True)),
            "damage_residue_id": first.get("damage_residue_id", ""),
            "residue_type": first.get("residue_type", ""),
            "proxy_rank": first.get("proxy_rank", ""),
            "n_seeds": len(members),
            "seeds": " ".join(sorted(m.get("random_seed", "") for m in members)),
            "baseline_stiffness_mean": round(base_m, 4),
            "baseline_stiffness_std": round(std(base), 4),
            "baseline_stiffness_sem": round(sem(base), 4) if len(base) > 1 else "",
            "baseline_stiffness_cv": round(std(base) / base_m, 4) if base_m else "",
            "damaged_stiffness_mean": round(dmg_m, 4),
            "damaged_stiffness_std": round(std(dmg), 4),
            "damaged_stiffness_sem": round(sem(dmg), 4) if len(dmg) > 1 else "",
            "mechanical_degradation_pct": round(paired, 4) if paired is not None else "",
            "mechanical_degradation_pct_std": round(std(per_seed), 4) if per_seed else "",
            "mechanical_degradation_pct_sem": (
                round(label_sem, 4) if math.isfinite(label_sem) else ""
            ),
            "mechanical_degradation_pct_ratio_of_means": (
                round(ratio_of_means, 4) if ratio_of_means is not None else ""
            ),
            "estimator_disagreement_pct": (
                round(disagreement, 4) if disagreement is not None else ""
            ),
            "fit_quality_min": round(min(fits), 5) if fits else "",
            "stiffness_unit": first.get("stiffness_unit", "pN/nm"),
            "label_usable": not reasons,
            "label_reject_reasons": " | ".join(reasons),
            "git_commit": first.get("git_commit", ""),
            "is_synthetic": False,
        })

    usable = [r for r in out if r["label_usable"]]
    all_stds = [
        r["mechanical_degradation_pct_std"] for r in out
        if isinstance(r["mechanical_degradation_pct_std"], float)
        and r["n_seeds"] > 1
    ]
    typical_std = mean(all_stds) if all_stds else None
    summary = {
        "input_rows": len(rows),
        "rows_skipped_not_completed_or_synthetic": skipped_incomplete,
        "perturbations": len(out),
        "usable_labels": len(usable),
        "typical_label_std_pct": round(typical_std, 4) if typical_std else None,
        "seeds_needed_for_sem": (
            {
                f"sem_{t}pct": seeds_needed(typical_std, t)
                for t in (10.0, 5.0, 2.0)
            } if typical_std else None
        ),
        "min_seeds_required": min_seeds,
        "max_label_sem_pct": max_sem,
    }
    return out, summary


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--infile", default=str(DEFAULT_IN))
    ap.add_argument("--outfile", default=str(DEFAULT_OUT))
    ap.add_argument("--min-seeds", type=int, default=3)
    ap.add_argument("--max-sem", type=float, default=10.0,
                    help="reject a label whose standard error exceeds this many "
                         "percentage points")
    args = ap.parse_args()

    infile = Path(args.infile)
    if not infile.exists():
        raise SystemExit(f"No stiffness table at {infile}. Run experiments first.")
    with infile.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))

    out, summary = aggregate(rows, min_seeds=args.min_seeds, max_sem=args.max_sem)

    outfile = Path(args.outfile)
    outfile.parent.mkdir(parents=True, exist_ok=True)
    with outfile.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=OUT_COLUMNS, lineterminator="\n", restval="")
        writer.writeheader()
        for row in out:
            writer.writerow(row)

    (outfile.parent / "label_quality_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )

    print(f"read  {summary['input_rows']} experiment rows from {infile.name}")
    print(f"wrote {len(out)} perturbation labels to {outfile.name}")
    print(f"  usable for training : {summary['usable_labels']} / {len(out)}")
    if summary["typical_label_std_pct"] is not None:
        print(f"  typical label std   : {summary['typical_label_std_pct']:.2f} pct")
        for name, n in (summary["seeds_needed_for_sem"] or {}).items():
            print(f"  seeds needed for {name.replace('sem_', '+/-').replace('pct', ' pct')}: {n}")
    print()
    for row in out:
        flag = "OK " if row["label_usable"] else "REJ"
        print(
            f"  [{flag}] {row['protein_id']} {row['severity_label']:8} "
            f"{row['damage_residue_ids']:24} n={row['n_seeds']} "
            f"target={row['mechanical_degradation_pct']} "
            f"+/- {row['mechanical_degradation_pct_sem']}"
        )
        if not row["label_usable"]:
            print(f"         {row['label_reject_reasons']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
