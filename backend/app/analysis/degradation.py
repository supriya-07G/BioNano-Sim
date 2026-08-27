"""The simulation-derived degradation **proxy**.

This is the most easily misread number in the application, so the calculation is
written to be auditable and every response carries its formula.

What it is NOT:
  * not a measured degradation percentage,
  * not a radiation-damage yield,
  * not comparable to an experimental assay.

What it IS: a bounded, monotone score built from three structural observables of
the trajectory, each normalised against a reference scale, then combined with
fixed weights. It answers "how far did this structure drift from its starting
conformation, relative to a drift scale we chose" — nothing more. The reference
scales are engineering constants for an MVP, not physical constants.

The proxy exists so the dashboard can put the ML estimate and the physics run on
one axis. That comparison is a *consistency check between two different proxies*,
not a validation of either.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

# --- Reference scales (engineering constants, not physical constants) ------- #
# Chosen so that a well-behaved short implicit-solvent run of a small stable
# domain lands in the low tens of percent, and gross unfolding approaches 100 %.
# They are declared here, echoed in every API response, and documented in
# docs/simulation-methodology.md so a reader can recompute the score by hand.
RMSD_REFERENCE_NM = 0.60      # RMSD treated as "fully drifted"
RG_RELATIVE_REFERENCE = 0.25  # 25 % change in radius of gyration -> full score
RMSF_REFERENCE_NM = 0.35      # mean per-residue fluctuation treated as maximal

W_RMSD = 0.50
W_RG = 0.20
W_RMSF = 0.30

PROXY_FORMULA = (
    "degradation_proxy_percent = 100 * clip("
    f"{W_RMSD}*min(1, final_rmsd_nm/{RMSD_REFERENCE_NM}) + "
    f"{W_RG}*min(1, |rg_final - rg_initial|/rg_initial/{RG_RELATIVE_REFERENCE}) + "
    f"{W_RMSF}*min(1, mean_rmsf_nm/{RMSF_REFERENCE_NM})"
    ", 0, 1)"
)

PROXY_LABEL = "Simulation-derived degradation proxy"

PROXY_CAVEATS = [
    "This is a structural-drift score computed by BioNano-Sim from the "
    "trajectory. It is NOT experimentally measured degradation and NOT a "
    "radiation-damage yield.",
    "The reference scales (RMSD 0.60 nm, ΔRg 25 %, RMSF 0.35 nm) are engineering "
    "constants chosen for this MVP, not physical constants. Changing them changes "
    "the number without changing the underlying physics.",
    "A short run at 300 K produces non-zero drift from thermal motion alone. Use "
    "the BASELINE_NO_RADIATION preset as a control to see that floor.",
    "The ML estimate and this proxy are different quantities on different scales. "
    "Their difference measures disagreement between two proxies, and does not tell "
    "you which is closer to reality.",
]


@dataclass
class DegradationProxy:
    percent: float
    components: dict[str, Any] = field(default_factory=dict)
    formula: str = PROXY_FORMULA
    label: str = PROXY_LABEL
    caveats: list[str] = field(default_factory=lambda: list(PROXY_CAVEATS))

    def as_dict(self) -> dict[str, Any]:
        return {
            "percent": round(self.percent, 4),
            "label": self.label,
            "formula": self.formula,
            "components": self.components,
            "reference_scales": {
                "rmsd_reference_nm": RMSD_REFERENCE_NM,
                "rg_relative_reference": RG_RELATIVE_REFERENCE,
                "rmsf_reference_nm": RMSF_REFERENCE_NM,
                "weights": {"rmsd": W_RMSD, "radius_of_gyration": W_RG, "rmsf": W_RMSF},
                "note": "Engineering constants for this MVP, not physical constants.",
            },
            "caveats": self.caveats,
        }


def _safe(value: float | None, default: float = 0.0) -> float:
    if value is None:
        return default
    v = float(value)
    return v if np.isfinite(v) else default


def compute_degradation_proxy(
    *,
    final_rmsd_nm: float | None,
    rg_initial_nm: float | None,
    rg_final_nm: float | None,
    mean_rmsf_nm: float | None,
) -> DegradationProxy:
    """Combine three trajectory observables into a bounded [0, 100] score."""
    rmsd = _safe(final_rmsd_nm)
    rg0 = _safe(rg_initial_nm)
    rg1 = _safe(rg_final_nm)
    rmsf = _safe(mean_rmsf_nm)

    rmsd_term = min(1.0, rmsd / RMSD_REFERENCE_NM) if RMSD_REFERENCE_NM > 0 else 0.0
    rg_relative = abs(rg1 - rg0) / rg0 if rg0 > 0 else 0.0
    rg_term = min(1.0, rg_relative / RG_RELATIVE_REFERENCE) if RG_RELATIVE_REFERENCE > 0 else 0.0
    rmsf_term = min(1.0, rmsf / RMSF_REFERENCE_NM) if RMSF_REFERENCE_NM > 0 else 0.0

    score = W_RMSD * rmsd_term + W_RG * rg_term + W_RMSF * rmsf_term
    percent = float(np.clip(score, 0.0, 1.0) * 100.0)

    return DegradationProxy(
        percent=percent,
        components={
            "rmsd": {
                "value_nm": round(rmsd, 6),
                "normalised": round(rmsd_term, 6),
                "weight": W_RMSD,
                "contribution_percent": round(W_RMSD * rmsd_term * 100, 4),
            },
            "radius_of_gyration": {
                "initial_nm": round(rg0, 6),
                "final_nm": round(rg1, 6),
                "relative_change": round(rg_relative, 6),
                "normalised": round(rg_term, 6),
                "weight": W_RG,
                "contribution_percent": round(W_RG * rg_term * 100, 4),
            },
            "rmsf": {
                "mean_nm": round(rmsf, 6),
                "normalised": round(rmsf_term, 6),
                "weight": W_RMSF,
                "contribution_percent": round(W_RMSF * rmsf_term * 100, 4),
            },
        },
    )


def stability_summary(
    *,
    rmsd_series: np.ndarray,
    rg_series: np.ndarray,
    rmsf_values: np.ndarray,
    temperature_series: list[float],
) -> dict[str, Any]:
    """Plain-language structural stability assessment with its own thresholds."""

    def _stat(arr: np.ndarray) -> dict[str, float | None]:
        finite = arr[np.isfinite(arr)] if arr.size else arr
        if finite.size == 0:
            return {"min": None, "max": None, "mean": None, "final": None, "std": None}
        return {
            "min": round(float(finite.min()), 6),
            "max": round(float(finite.max()), 6),
            "mean": round(float(finite.mean()), 6),
            "final": round(float(finite[-1]), 6),
            "std": round(float(finite.std(ddof=0)), 6),
        }

    rmsd_stat = _stat(np.asarray(rmsd_series, dtype=float))
    rg_stat = _stat(np.asarray(rg_series, dtype=float))
    rmsf_stat = _stat(np.asarray(rmsf_values, dtype=float))
    temp = np.asarray(temperature_series, dtype=float)

    final_rmsd = rmsd_stat["final"]
    if final_rmsd is None:
        verdict, explanation = "unknown", "No RMSD series was produced."
    elif final_rmsd < 0.15:
        verdict = "stable"
        explanation = (
            f"Final backbone RMSD of {final_rmsd:.3f} nm is within the range expected "
            "from thermal motion for a folded domain over a short run. No evidence of "
            "unfolding in this trajectory."
        )
    elif final_rmsd < 0.30:
        verdict = "mildly_perturbed"
        explanation = (
            f"Final backbone RMSD of {final_rmsd:.3f} nm indicates measurable but "
            "modest rearrangement, typically loop and terminus motion rather than "
            "loss of the fold."
        )
    elif final_rmsd < 0.60:
        verdict = "perturbed"
        explanation = (
            f"Final backbone RMSD of {final_rmsd:.3f} nm is substantial for a small "
            "domain over a short run and suggests real structural rearrangement."
        )
    else:
        verdict = "strongly_perturbed"
        explanation = (
            f"Final backbone RMSD of {final_rmsd:.3f} nm is large enough to be "
            "consistent with partial loss of the native fold."
        )

    return {
        "verdict": verdict,
        "explanation": explanation,
        "threshold_note": (
            "Verdict bands (0.15 / 0.30 / 0.60 nm final Cα RMSD) are presentational "
            "heuristics for this MVP, not published stability criteria."
        ),
        "rmsd_nm": rmsd_stat,
        "radius_of_gyration_nm": rg_stat,
        "rmsf_nm": rmsf_stat,
        "temperature_kelvin": {
            "mean": round(float(temp.mean()), 3) if temp.size else None,
            "std": round(float(temp.std(ddof=0)), 3) if temp.size else None,
            "n_samples": int(temp.size),
        },
    }


def highest_mobility_residues(
    residue_ids: list[str],
    residue_types: list[str],
    rmsf_values: np.ndarray,
    top_n: int = 10,
) -> list[dict[str, Any]]:
    """The most mobile residues by RMSF, descending."""
    rmsf = np.asarray(rmsf_values, dtype=float)
    if rmsf.size == 0:
        return []
    n = min(len(residue_ids), len(residue_types), rmsf.size)
    order = np.argsort(rmsf[:n])[::-1][:top_n]
    return [
        {
            "rank": rank,
            "residue_id": residue_ids[i],
            "residue_type": residue_types[i],
            "rmsf_nm": round(float(rmsf[i]), 6),
        }
        for rank, i in enumerate(order, start=1)
    ]
