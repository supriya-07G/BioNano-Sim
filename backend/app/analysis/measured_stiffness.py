"""Per-protein aggregates over the real 520-run steered-MD dataset.

Several surfaces used to carry their own hand-written tables of stiffness
values. Those tables disagreed with the measurements in
``data/ml/stiffness_results_REAL_v1.csv`` by a factor of three to five, and in
one case inverted the result: the protein ranked best was the one whose fit
slope is most strongly negative. This module is the single place any surface
reads measured mechanics from, so there is nothing left to drift against.

Two facts about the dataset shape everything here.

First, the seed spread is large -- roughly 15-25% of the mean for the domains
that resolve at all. A single number for a protein is therefore not a
measurement, and every aggregate below carries its standard deviation and its
sample count so callers can show the spread rather than imply precision that
40 runs do not support.

Second, the dataset already carries its own quality gate: 130 of the 520 runs
are ``COMPLETED`` and 390 are ``QC_FAILED``, each with a stated reason such as
``r2 0.02 below 0.5`` or ``negative stiffness -62 pN/nm is unphysical``. Only
four of the thirteen domains have any run that survives it. Statistics are
computed over passing runs alone, but every screened domain stays in the
mapping with its pass/fail accounting intact -- a fold the protocol could not
measure must never silently disappear, because "we screened thirteen and four
resolved" is the result, and dropping the nine would hide the denominator.
"""

from __future__ import annotations

import csv
import statistics
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

from app.config import settings

#: The measured dataset. 13 domains x 40 paired runs.
STIFFNESS_CSV = settings.data_dir / "ml" / "stiffness_results_REAL_v1.csv"

#: The producer's own verdict column. Runs it marks QC_FAILED carry a reason
#: (R^2 below 0.5, or a negative and therefore unphysical stiffness) and are
#: excluded from every statistic here.
PASSING_STATUS = "COMPLETED"

UNRESOLVED_NOTE = (
    "No run for this domain passed the dataset's quality gate: the "
    "force-extension fits are near zero, negative, or too poor to read an "
    "elastic constant from. This is a limit of the pulling protocol on this "
    "fold, not a measurement that the fold is weak."
)

#: Protein-level columns, constant within a pdb_id, used for neighbour distance.
SEQUENCE_FEATURES = (
    "protein_length",
    "molecular_weight",
    "hydrophobic_fraction",
    "charged_fraction",
)


@dataclass(frozen=True)
class Aggregate:
    """Mean, spread and sample count for one quantity."""

    mean: float
    sd: float
    n: int

    def as_dict(self) -> dict[str, Any]:
        return {"mean": round(self.mean, 2), "sd": round(self.sd, 2), "n": self.n}


@dataclass(frozen=True)
class MeasuredProtein:
    pdb_id: str
    uniprot_id: str
    n_runs: int
    """Runs that passed the dataset's quality gate; the basis of every statistic."""
    n_screened: int
    """Runs attempted, passing and failed. The denominator."""
    baseline: Aggregate
    damaged: Aggregate
    fit_quality: float
    resolved: bool
    unresolved_reason: str | None = None
    qc_failure_reasons: list[str] = field(default_factory=list)
    sequence_features: dict[str, float] = field(default_factory=dict)

    @property
    def retained_pct(self) -> float | None:
        """Damaged stiffness as a percentage of baseline.

        Undefined when the baseline is not a usable elastic constant: dividing
        by a slope fitted through noise produces a percentage that looks like a
        result and is not one.
        """
        if not self.resolved or self.baseline.mean <= 0:
            return None
        return round((self.damaged.mean / self.baseline.mean) * 100.0, 1)

    @property
    def relative_sd(self) -> float | None:
        """Seed spread as a fraction of the mean -- a real uncertainty term."""
        if not self.resolved or self.baseline.mean <= 0:
            return None
        return round(self.baseline.sd / self.baseline.mean, 4)

    def as_dict(self) -> dict[str, Any]:
        return {
            "pdb_id": self.pdb_id,
            "uniprot_id": self.uniprot_id,
            "runs_passing_qc": self.n_runs,
            "runs_screened": self.n_screened,
            "baseline_stiffness": self.baseline.as_dict(),
            "damaged_stiffness": self.damaged.as_dict(),
            "stiffness_unit": "pN/nm",
            "mean_fit_quality": round(self.fit_quality, 3),
            "resolved": self.resolved,
            "unresolved_reason": self.unresolved_reason,
            "qc_failure_reasons": self.qc_failure_reasons,
            "stiffness_retained_pct": self.retained_pct,
            "relative_sd": self.relative_sd,
        }


def _aggregate(values: list[float]) -> Aggregate:
    if not values:
        return Aggregate(mean=0.0, sd=0.0, n=0)
    sd = statistics.pstdev(values) if len(values) > 1 else 0.0
    return Aggregate(mean=statistics.fmean(values), sd=sd, n=len(values))


@lru_cache(maxsize=1)
def load_measured() -> dict[str, MeasuredProtein]:
    """Aggregate the measured dataset per protein.

    Cached: the file is a build artefact that does not change while the server
    runs. Returns an empty mapping when the dataset is absent so a checkout
    without it degrades to "no measurement" rather than failing to import.
    """
    if not STIFFNESS_CSV.is_file():
        return {}

    screened: dict[str, list[dict[str, str]]] = {}
    with STIFFNESS_CSV.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            pdb_id = (row.get("pdb_id") or "").strip().upper()
            if pdb_id:
                screened.setdefault(pdb_id, []).append(row)

    measured: dict[str, MeasuredProtein] = {}
    for pdb_id, all_entries in screened.items():
        passing = [
            row
            for row in all_entries
            if (row.get("status") or "").upper() == PASSING_STATUS
        ]
        # Statistics come from passing runs only. A domain with none of them is
        # still reported, carrying the reasons its runs were rejected.
        stats_rows = passing or []
        baseline = _aggregate(_floats(stats_rows, "baseline_stiffness"))
        damaged = _aggregate(_floats(stats_rows, "damaged_stiffness"))
        fits = _floats(stats_rows, "fit_quality")

        measured[pdb_id] = MeasuredProtein(
            pdb_id=pdb_id,
            uniprot_id=(all_entries[0].get("uniprot_id") or "").strip(),
            n_runs=len(passing),
            n_screened=len(all_entries),
            baseline=baseline,
            damaged=damaged,
            fit_quality=statistics.fmean(fits) if fits else 0.0,
            resolved=bool(passing),
            unresolved_reason=None if passing else UNRESOLVED_NOTE,
            qc_failure_reasons=_qc_reasons(all_entries),
            sequence_features=_sequence_features(all_entries[0]),
        )
    return measured


def _qc_reasons(entries: list[dict[str, str]]) -> list[str]:
    """The distinct rejection reasons the producer recorded, most common first.

    Individual notes carry per-run numbers ("r2 0.02 below 0.5"), which would
    give hundreds of near-identical strings. They are reduced to their kind so
    a caller can say *why* a domain failed without reprinting 40 variations.
    """
    counts: dict[str, int] = {}
    for row in entries:
        if (row.get("status") or "").upper() == PASSING_STATUS:
            continue
        for note in (row.get("qc_note") or "").split("|"):
            kind = _reason_kind(note.strip())
            if kind:
                counts[kind] = counts.get(kind, 0) + 1
    return [kind for kind, _ in sorted(counts.items(), key=lambda kv: -kv[1])]


def _reason_kind(note: str) -> str | None:
    if not note:
        return None
    lowered = note.lower()
    if "negative stiffness" in lowered:
        return "negative stiffness (unphysical)"
    if "below" in lowered and "r2" in lowered:
        return "force-extension fit R^2 below 0.5"
    return note


def _floats(entries: list[dict[str, str]], column: str) -> list[float]:
    out: list[float] = []
    for entry in entries:
        raw = entry.get(column)
        if raw in (None, ""):
            continue
        try:
            out.append(float(raw))
        except (TypeError, ValueError):
            continue
    return out


def _sequence_features(entry: dict[str, str]) -> dict[str, float]:
    out: dict[str, float] = {}
    for name in SEQUENCE_FEATURES:
        raw = entry.get(name)
        if raw in (None, ""):
            continue
        try:
            out[name] = float(raw)
        except (TypeError, ValueError):
            continue
    return out


def get(pdb_id: str) -> MeasuredProtein | None:
    return load_measured().get((pdb_id or "").strip().upper())


def nearest_measured(pdb_id: str, limit: int = 3) -> list[dict[str, Any]]:
    """Proteins in the measured set closest to ``pdb_id`` in sequence features.

    Distance is Euclidean over the four protein-level descriptors, each scaled
    by the population standard deviation so molecular weight does not dominate
    length by three orders of magnitude.

    This describes proximity in the descriptor space the model consumes. It is
    not structural or evolutionary similarity, and it is deliberately not
    reported as a percentage: the query protein is excluded from its own
    neighbour list, which a similarity score would otherwise rank first at 100%
    and make the whole list look meaningless.
    """
    measured = load_measured()
    target = measured.get((pdb_id or "").strip().upper())
    if target is None or not target.sequence_features:
        return []

    scales = _feature_scales(measured)
    scored: list[tuple[float, MeasuredProtein]] = []
    for other in measured.values():
        if other.pdb_id == target.pdb_id or not other.sequence_features:
            continue
        distance = _scaled_distance(
            target.sequence_features, other.sequence_features, scales
        )
        if distance is not None:
            scored.append((distance, other))

    scored.sort(key=lambda pair: pair[0])
    return [
        {
            "pdb_id": other.pdb_id,
            "distance": round(distance, 4),
            "baseline_stiffness_pnnm": round(other.baseline.mean, 1),
            "resolved": other.resolved,
        }
        for distance, other in scored[:limit]
    ]


def _feature_scales(measured: dict[str, MeasuredProtein]) -> dict[str, float]:
    scales: dict[str, float] = {}
    for name in SEQUENCE_FEATURES:
        values = [
            protein.sequence_features[name]
            for protein in measured.values()
            if name in protein.sequence_features
        ]
        spread = statistics.pstdev(values) if len(values) > 1 else 0.0
        # A descriptor with no spread carries no information; scaling by 1.0
        # leaves its (zero) differences harmlessly in the sum.
        scales[name] = spread or 1.0
    return scales


def _scaled_distance(
    left: dict[str, float], right: dict[str, float], scales: dict[str, float]
) -> float | None:
    total = 0.0
    used = 0
    for name in SEQUENCE_FEATURES:
        if name not in left or name not in right:
            continue
        delta = (left[name] - right[name]) / scales[name]
        total += delta * delta
        used += 1
    if used == 0:
        return None
    return (total / used) ** 0.5


def dataset_summary() -> dict[str, Any]:
    """Provenance for any surface that reports these numbers."""
    measured = load_measured()
    return {
        "source_file": STIFFNESS_CSV.name,
        "available": bool(measured),
        "proteins_screened": len(measured),
        "runs_screened": sum(p.n_screened for p in measured.values()),
        "runs_passing_qc": sum(p.n_runs for p in measured.values()),
        "resolved_proteins": sorted(
            p.pdb_id for p in measured.values() if p.resolved
        ),
        "unresolved_proteins": sorted(
            p.pdb_id for p in measured.values() if not p.resolved
        ),
        "quality_gate": (
            "Runs are accepted only where the producer marked them COMPLETED. "
            "Rejections are recorded with a reason: a force-extension fit with "
            "R^2 below 0.5, or a negative stiffness, which is unphysical."
        ),
    }
