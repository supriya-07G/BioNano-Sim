"""Cross-experiment analysis: comparing two completed jobs.

Comparison is only meaningful when the two runs share a preset, because RMSD and
the drift proxy both scale with trajectory length. When they differ we still show
the numbers but flag the mismatch prominently rather than ranking silently.
"""

from __future__ import annotations

from typing import Any

from app.core.exceptions import ValidationFailedError
from app.core.logging import get_logger
from app.services import simulation_service

logger = get_logger("COSMORA.services.analysis")


def _brief(results: dict[str, Any]) -> dict[str, Any]:
    metrics = results.get("metrics", {})
    metadata = results.get("metadata", {})
    proxy = metrics.get("degradation_proxy") or {}
    comparison = results.get("comparison") or {}
    return {
        "job_id": results["job_id"],
        "result_label": results.get("result_label"),
        "engine": results.get("engine"),
        "pdb_id": metadata.get("pdb_id"),
        "upload_id": metadata.get("upload_id"),
        "chain_id": metadata.get("chain_id"),
        "scenario_id": (metadata.get("scenario") or {}).get("scenario_id"),
        "scenario_label": (metadata.get("scenario") or {}).get("label"),
        "preset_id": (metadata.get("preset") or {}).get("preset_id"),
        "preset_label": (metadata.get("preset") or {}).get("label"),
        "simulated_time_ps": metrics.get("simulated_time_ps"),
        "n_frames": metrics.get("n_frames"),
        "duration_seconds": metadata.get("duration_seconds"),
        "finished_at": metadata.get("finished_at"),
        "ml_degradation_percent": comparison.get("ml_degradation_percent"),
        "simulation_degradation_proxy_percent": proxy.get("percent"),
        "final_rmsd_nm": (metrics.get("rmsd_nm") or {}).get("final"),
        "max_rmsd_nm": (metrics.get("rmsd_nm") or {}).get("max"),
        "mean_rmsf_nm": (metrics.get("rmsf_nm") or {}).get("mean"),
        "rg_relative_change": (metrics.get("radius_of_gyration_nm") or {}).get(
            "relative_change"
        ),
        "stability_verdict": (results.get("stability_summary") or {}).get("verdict"),
        "series": results.get("series", {}),
        "rmsf": results.get("rmsf", []),
    }


def _delta(a: float | None, b: float | None) -> float | None:
    if a is None or b is None:
        return None
    return round(float(b) - float(a), 4)


def compare_jobs(job_id_a: str, job_id_b: str) -> dict[str, Any]:
    if job_id_a == job_id_b:
        raise ValidationFailedError(
            "Choose two different experiments to compare.", code="SAME_JOB"
        )

    a = _brief(simulation_service.job_results(job_id_a))
    b = _brief(simulation_service.job_results(job_id_b))

    notes: list[str] = []
    if a["preset_id"] != b["preset_id"]:
        notes.append(
            f"The two runs used different presets ({a['preset_label']} vs "
            f"{b['preset_label']}) and therefore different trajectory lengths. RMSD "
            "and the drift proxy both grow with simulated time, so this comparison "
            "is not like-for-like. Re-run with a shared preset for a fair ranking."
        )
    if a["pdb_id"] == b["pdb_id"] and a["scenario_id"] != b["scenario_id"]:
        notes.append(
            "Same protein under different scenarios: differences isolate the "
            "scenario effect."
        )
    elif a["pdb_id"] != b["pdb_id"] and a["scenario_id"] == b["scenario_id"]:
        notes.append(
            "Different proteins under the same scenario: differences isolate the "
            "protein effect. Note that absolute RMSD also depends on chain length."
        )
    if a["chain_id"] != b["chain_id"]:
        notes.append(f"Different chains compared ({a['chain_id']} vs {b['chain_id']}).")

    comparable = a["preset_id"] == b["preset_id"]
    metric_defs = [
        ("ml_degradation_percent", "ML degradation estimate", "%", "lower_is_better"),
        ("simulation_degradation_proxy_percent", "Simulation drift proxy", "%", "lower_is_better"),
        ("final_rmsd_nm", "Final Cα RMSD", "nm", "lower_is_better"),
        ("max_rmsd_nm", "Peak Cα RMSD", "nm", "lower_is_better"),
        ("mean_rmsf_nm", "Mean per-residue RMSF", "nm", "lower_is_better"),
        ("rg_relative_change", "Relative Rg change", "fraction", "lower_is_better"),
    ]

    differences = []
    for key, label, unit, direction in metric_defs:
        va, vb = a.get(key), b.get(key)
        winner = None
        if comparable and va is not None and vb is not None and va != vb:
            winner = job_id_a if (va < vb) == (direction == "lower_is_better") else job_id_b
        differences.append(
            {
                "metric": key,
                "label": label,
                "unit": unit,
                "a": va,
                "b": vb,
                "delta_b_minus_a": _delta(va, vb),
                "more_stable_job_id": winner,
            }
        )

    ranking: list[dict[str, Any]] = []
    if comparable:
        scored = [
            (job["job_id"], job["final_rmsd_nm"], job)
            for job in (a, b)
            if job["final_rmsd_nm"] is not None
        ]
        scored.sort(key=lambda t: t[1])
        ranking = [
            {
                "rank": i,
                "job_id": jid,
                "final_rmsd_nm": rmsd,
                "label": f"{job['pdb_id'] or job['upload_id']} / {job['scenario_id']}",
            }
            for i, (jid, rmsd, job) in enumerate(scored, start=1)
        ]

    return {
        "a": a,
        "b": b,
        "comparable": comparable,
        "differences": differences,
        "stability_ranking": ranking,
        "notes": notes,
        "interpretation_limits": [
            "Both degradation figures are proxies. Neither has been validated "
            "against experimental measurement, so a ranking says which run drifted "
            "more under these settings — not which protein is genuinely more "
            "radiation-tolerant.",
            "Absolute RMSD depends on chain length and trajectory length. Compare "
            "proteins only at equal preset, and treat cross-length comparisons as "
            "indicative.",
        ],
    }
