"""Core engine for damage-severity and parameter sweep experiments (issue #33).

Provides grid expansion, cost estimation, bounds checks, deduplication against
existing runtime experiments, and severity-response curve aggregation.
"""

from __future__ import annotations

import numpy as np

from app.core.exceptions import ValidationFailedError
from app.schemas.sweep import (
    SeverityResponsePoint,
    SweepCombination,
    SweepConfig,
    SweepItem,
    SweepPreviewResponse,
)

MAX_SWEEP_EXPERIMENTS_LIMIT = 50
ESTIMATED_TIME_PER_RUN_SEC = 15.0  # 15 seconds per paired experiment
ESTIMATED_STORAGE_PER_RUN_MB = 5.0  # 5 MB per experiment artifact directory


def build_experiment_id(protein_id: str, severity: str, rank: int, seed: int) -> str:
    """Derive standard experiment identifier for a parameter combination."""
    if severity == "MILD":
        return f"{protein_id}_{severity}_rank{rank}_seed{seed}"
    return f"{protein_id}_{severity}_seed{seed}"


def expand_sweep_grid(config: SweepConfig, existing_experiment_ids: set[str] | None = None) -> list[SweepCombination]:
    """Expand sweep configuration into explicit unique experiment combinations."""
    existing = existing_experiment_ids or set()
    combinations: list[SweepCombination] = []

    for sev in config.severities:
        ranks = config.ranks if sev == "MILD" else [1]
        for r in ranks:
            for seed in config.seeds:
                exp_id = build_experiment_id(config.protein_id, sev, r, seed)
                is_dup = exp_id in existing
                combinations.append(
                    SweepCombination(
                        experiment_id=exp_id,
                        protein_id=config.protein_id,
                        severity_label=sev,
                        proxy_rank=r,
                        random_seed=seed,
                        is_duplicate=is_dup,
                    )
                )

    return combinations


def estimate_sweep_cost(config: SweepConfig, existing_experiment_ids: set[str] | None = None) -> SweepPreviewResponse:
    """Validate bounds and estimate compute time and storage for a proposed sweep."""
    combinations = expand_sweep_grid(config, existing_experiment_ids)
    total_runs = len(combinations)

    if total_runs > MAX_SWEEP_EXPERIMENTS_LIMIT:
        raise ValidationFailedError(
            f"Sweep configuration generates {total_runs} experiments, which exceeds "
            f"the safety limit of {MAX_SWEEP_EXPERIMENTS_LIMIT}.",
            code="SWEEP_LIMIT_EXCEEDED",
        )

    if total_runs == 0:
        raise ValidationFailedError(
            "Sweep configuration generated 0 experiments. Select at least one severity and seed.",
            code="INVALID_SWEEP_CONFIG",
        )

    duplicates = sum(1 for c in combinations if c.is_duplicate)
    new_runs = total_runs - duplicates

    est_time = round(new_runs * ESTIMATED_TIME_PER_RUN_SEC, 2)
    est_storage = round(new_runs * ESTIMATED_STORAGE_PER_RUN_MB, 2)

    return SweepPreviewResponse(
        protein_id=config.protein_id,
        total_experiments=total_runs,
        duplicates_skipped=duplicates,
        estimated_time_seconds=est_time,
        estimated_storage_mb=est_storage,
        max_experiments_limit=MAX_SWEEP_EXPERIMENTS_LIMIT,
        combinations=combinations,
    )


def aggregate_severity_response(items: list[SweepItem]) -> list[SeverityResponsePoint]:
    """Aggregate paired mechanical degradation into severity-response curves."""
    severity_map = {
        "MILD": 1,
        "MODERATE": 3,
        "SEVERE": 5,
    }

    grouped: dict[str, list[float]] = {}
    for item in items:
        if item.status == "COMPLETED" and item.mechanical_degradation_pct is not None:
            grouped.setdefault(item.severity_label, []).append(item.mechanical_degradation_pct)

    points: list[SeverityResponsePoint] = []
    for sev in ("MILD", "MODERATE", "SEVERE"):
        values = grouped.get(sev, [])
        if values:
            arr = np.array(values, dtype=float)
            mean_deg = round(float(np.mean(arr)), 4)
            std_deg = round(float(np.std(arr)), 4) if len(arr) > 1 else 0.0
        else:
            mean_deg = None
            std_deg = None

        points.append(
            SeverityResponsePoint(
                severity_label=sev,
                n_residues_damaged=severity_map.get(sev, 1),
                mean_degradation_pct=mean_deg,
                std_degradation_pct=std_deg,
                n_experiments=len(values),
            )
        )

    return points
