"""Multi-Objective Candidate Ranking Engine (#30).

Ranks candidate protein mechanical components on measured steered-MD results:
stiffness retention, pristine strength, fit quality, seed spread, and
Pareto-optimality across those objectives.

Every number served here is aggregated from the measured dataset by
``app.analysis.measured_stiffness``. This module previously carried its own
table of stiffness constants; they disagreed with the measurements by three to
five times and ranked first a domain whose fits are negative, which is the one
outcome the real data rules out. There is no local table any more, so there is
nothing left to diverge.

A domain that produced no run passing the dataset's quality gate is listed
without a rank rather than scored. Nine of the thirteen screened domains are in
that state, and saying so is the result -- a screen that resolves four of
thirteen is a finding, whereas thirteen confident scores would be a fiction.
"""

from typing import Any

from app.analysis import measured_stiffness
from app.schemas.ranking import (
    CandidateObjectiveScore,
    RankingResponse,
    RankingWeights,
)
from app.services import protein_service

#: Objectives maximised on the Pareto frontier. Retention is omitted where a
#: domain has no baseline to divide by; such domains never reach this stage.
_PARETO_OBJECTIVES = (
    "stiffness_retained_pct",
    "baseline_stiffness_pnnm",
    "mean_fit_quality",
)


def _pareto_frontier(rows: list[dict[str, Any]]) -> set[str]:
    """PDB ids not dominated by any other candidate.

    A candidate is dominated when another is at least equal on every objective
    and strictly better on one. Comparison is over measured quantities only.
    """
    frontier: set[str] = set()
    for row in rows:
        mine = tuple(row[key] for key in _PARETO_OBJECTIVES)
        dominated = any(
            other is not row
            and all(
                theirs >= ours
                for ours, theirs in zip(
                    mine,
                    tuple(other[key] for key in _PARETO_OBJECTIVES),
                    strict=True,
                )
            )
            and any(
                theirs > ours
                for ours, theirs in zip(
                    mine,
                    tuple(other[key] for key in _PARETO_OBJECTIVES),
                    strict=True,
                )
            )
            for other in rows
        )
        if not dominated:
            frontier.add(row["pdb_id"])
    return frontier


def rank_candidates(weights: RankingWeights | None = None) -> RankingResponse:
    """Score and rank approved proteins against the measured dataset."""
    if weights is None:
        weights = RankingWeights()

    summary = measured_stiffness.dataset_summary()
    approved = protein_service.list_proteins()

    resolved_rows: list[dict[str, Any]] = []
    unresolved: list[CandidateObjectiveScore] = []

    for protein in approved:
        pdb_id = protein["pdb_id"]
        measured = measured_stiffness.get(pdb_id)
        common = {
            "pdb_id": pdb_id,
            "name": protein.get("name", pdb_id),
            "uniprot": protein.get("uniprot") or (measured.uniprot_id if measured else "") or "N/A",
        }

        if measured is None:
            unresolved.append(
                _unmeasured(common, screened=0, reason=(
                    "This protein does not appear in the measured dataset, so no "
                    "mechanical result exists for it yet."
                ))
            )
            continue

        if not measured.resolved:
            unresolved.append(
                CandidateObjectiveScore(
                    rank=None,
                    **common,
                    baseline_stiffness_pnnm=None,
                    baseline_stiffness_sd=None,
                    damaged_stiffness_pnnm=None,
                    stiffness_retained_pct=None,
                    relative_sd=None,
                    mean_fit_quality=None,
                    runs_passing_qc=0,
                    runs_screened=measured.n_screened,
                    resolved=False,
                    unresolved_reason=measured.unresolved_reason,
                    qc_failure_reasons=measured.qc_failure_reasons,
                    composite_score=None,
                    explanation=(
                        f"Not ranked. All {measured.n_screened} runs were rejected by "
                        f"the dataset's quality gate ("
                        f"{'; '.join(measured.qc_failure_reasons) or 'no reason recorded'}"
                        "). No elastic constant can be read from these fits."
                    ),
                    provenance=_provenance(measured),
                )
            )
            continue

        resolved_rows.append(
            {
                **common,
                "baseline_stiffness_pnnm": round(measured.baseline.mean, 1),
                "baseline_stiffness_sd": round(measured.baseline.sd, 1),
                "damaged_stiffness_pnnm": round(measured.damaged.mean, 1),
                "stiffness_retained_pct": measured.retained_pct,
                "relative_sd": measured.relative_sd,
                "mean_fit_quality": round(measured.fit_quality, 3),
                "runs_passing_qc": measured.n_runs,
                "runs_screened": measured.n_screened,
                "measured": measured,
            }
        )

    if not resolved_rows:
        return RankingResponse(
            mode="NO_MEASUREMENTS_AVAILABLE" if not summary["available"] else "MEASURED_STEERED_MD",
            total_candidates=len(approved),
            ranked_candidates=0,
            pareto_frontier_ids=[],
            weights_used=weights,
            dataset=summary,
            candidates=unresolved,
        )

    frontier = _pareto_frontier(resolved_rows)
    max_baseline = max(row["baseline_stiffness_pnnm"] for row in resolved_rows) or 1.0
    total_positive = max(
        1e-6,
        weights.stiffness_retention
        + weights.baseline_strength
        + weights.measurement_confidence,
    )

    scored: list[CandidateObjectiveScore] = []
    for row in resolved_rows:
        measured = row["measured"]

        # Retention can exceed 100% -- damage sometimes leaves a domain
        # marginally stiffer, which is itself a result. It is clamped for
        # scoring only, so a null result cannot outscore a real improvement,
        # while the raw percentage is still reported untouched.
        s_retention = min(100.0, max(0.0, row["stiffness_retained_pct"]))
        s_strength = round((row["baseline_stiffness_pnnm"] / max_baseline) * 100.0, 1)
        s_confidence = round(row["mean_fit_quality"] * 100.0, 1)

        weighted = (
            weights.stiffness_retention * s_retention
            + weights.baseline_strength * s_strength
            + weights.measurement_confidence * s_confidence
        ) / total_positive

        # The spread across seeds is the honest uncertainty here, and it is
        # large: 15-25% of the mean even for domains that resolve cleanly.
        penalty = round(weights.uncertainty_penalty * (row["relative_sd"] or 0.0) * 100.0, 1)
        composite = round(max(0.0, weighted - penalty), 1)

        scored.append(
            CandidateObjectiveScore(
                rank=0,  # assigned after sorting
                pdb_id=row["pdb_id"],
                name=row["name"],
                uniprot=row["uniprot"],
                baseline_stiffness_pnnm=row["baseline_stiffness_pnnm"],
                baseline_stiffness_sd=row["baseline_stiffness_sd"],
                damaged_stiffness_pnnm=row["damaged_stiffness_pnnm"],
                stiffness_retained_pct=row["stiffness_retained_pct"],
                relative_sd=row["relative_sd"],
                mean_fit_quality=row["mean_fit_quality"],
                runs_passing_qc=row["runs_passing_qc"],
                runs_screened=row["runs_screened"],
                resolved=True,
                qc_failure_reasons=measured.qc_failure_reasons,
                subscores={
                    "stiffness_retention": round(s_retention, 1),
                    "baseline_strength": s_strength,
                    "measurement_confidence": s_confidence,
                },
                penalties={"seed_spread": penalty},
                composite_score=composite,
                is_pareto_optimal=row["pdb_id"] in frontier,
                explanation=_explain(row, s_strength, penalty, row["pdb_id"] in frontier),
                provenance=_provenance(measured),
            )
        )

    scored.sort(key=lambda c: c.composite_score or 0.0, reverse=True)
    for position, candidate in enumerate(scored, start=1):
        candidate.rank = position

    return RankingResponse(
        mode="MEASURED_STEERED_MD",
        total_candidates=len(approved),
        ranked_candidates=len(scored),
        pareto_frontier_ids=sorted(frontier),
        weights_used=weights,
        dataset=summary,
        candidates=scored + unresolved,
    )


def _unmeasured(
    common: dict[str, Any], *, screened: int, reason: str
) -> CandidateObjectiveScore:
    return CandidateObjectiveScore(
        rank=None,
        **common,
        baseline_stiffness_pnnm=None,
        baseline_stiffness_sd=None,
        damaged_stiffness_pnnm=None,
        stiffness_retained_pct=None,
        relative_sd=None,
        mean_fit_quality=None,
        runs_passing_qc=0,
        runs_screened=screened,
        resolved=False,
        unresolved_reason=reason,
        composite_score=None,
        explanation=f"Not ranked. {reason}",
        provenance={"dataset": measured_stiffness.STIFFNESS_CSV.name},
    )


def _explain(
    row: dict[str, Any], strength_score: float, penalty: float, on_frontier: bool
) -> str:
    retained = row["stiffness_retained_pct"]
    parts = [
        f"Baseline stiffness {row['baseline_stiffness_pnnm']} "
        f"+/- {row['baseline_stiffness_sd']} pN/nm over {row['runs_passing_qc']} of "
        f"{row['runs_screened']} runs that passed QC ({strength_score:.1f} pts).",
        f"Retains {retained}% of baseline after damage.",
        f"Mean force-extension fit R^2 {row['mean_fit_quality']}.",
    ]
    if retained is not None and retained >= 100.0:
        parts.append(
            "Retention at or above 100% means damage produced no measurable loss "
            "of stiffness in this domain; the seed spread is wider than the effect."
        )
    if penalty:
        parts.append(f"Seed spread costs {penalty} pts.")
    if on_frontier:
        parts.append("Pareto-optimal: not dominated on any measured objective.")
    return " ".join(parts)


def _provenance(measured: measured_stiffness.MeasuredProtein) -> dict[str, Any]:
    return {
        "dataset": measured_stiffness.STIFFNESS_CSV.name,
        "runs_passing_qc": measured.n_runs,
        "runs_screened": measured.n_screened,
        "measurement": "steered molecular dynamics, force-extension slope",
        "stiffness_unit": "pN/nm",
    }
