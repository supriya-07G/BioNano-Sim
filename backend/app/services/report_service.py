"""Report generation: JSON and CSV exports for a completed experiment."""

from __future__ import annotations

import csv
import io
from typing import Any

from app.analysis.degradation import PROXY_CAVEATS
from app.core.logging import get_logger
from app.services import prediction_service, simulation_service
from app.utils.serialization import to_jsonable, utc_now_iso

logger = get_logger("COSMORA.services.report")

SCIENTIFIC_NOTICE = {
    "status": "MVP_DEMONSTRATION",
    "headline": "COSMORA MVP — not experimentally validated",
    "what_this_is": [
        "An ML degradation estimate from a mock public-data bootstrap model whose "
        "labels are a synthetic proxy, not measured degradation.",
        "A real but very short OpenMM molecular-dynamics run in implicit solvent.",
        "A structural-drift score ('degradation proxy') computed by COSMORA "
        "from that trajectory.",
    ],
    "what_this_is_not": [
        "Not a validated prediction of protein degradation in space.",
        "Not a simulation of ionising radiation. Standard OpenMM models no particle "
        "tracks, energy deposition, radical chemistry or bond scission.",
        "Not production-timescale molecular dynamics. Simulated time is picoseconds.",
        "Not a claim that proteins replace silicon electronics. COSMORA examines "
        "proteins as candidate nanoscale mechanical components only.",
    ],
    "reproducibility": (
        "Every field needed to reproduce this run is recorded under "
        "'reproducibility': structure identity, chain, preset, force field, "
        "integrator seed, temperature and step counts."
    ),
}


def build_json_report(job_id: str) -> dict[str, Any]:
    results = simulation_service.job_results(job_id)
    metadata = results.get("metadata", {})
    scenario = metadata.get("scenario", {})
    status_doc = simulation_service.get_job_manager().read_status(job_id)

    protein_block: dict[str, Any] = {
        "pdb_id": metadata.get("pdb_id"),
        "upload_id": metadata.get("upload_id"),
        "chain_id": metadata.get("chain_id"),
    }
    if metadata.get("pdb_id"):
        try:
            detail = protein_detail_brief(metadata["pdb_id"])
            protein_block.update(detail)
        except Exception as exc:  # noqa: BLE001 - report must still generate
            logger.warning("Could not enrich protein block for report: %s", exc)

    ml_percent = status_doc.get("ml_degradation_percent")
    ml_block = None
    if ml_percent is not None:
        model = prediction_service.model_info()
        ml_block = {
            "label": "ML Prediction",
            "degradation_percent": ml_percent,
            "prediction_id": metadata.get("prediction_id"),
            "model_version": model.get("model_version"),
            "model_status": model.get("scientific_status"),
            "label_source": model.get("label_source"),
            "scientifically_validated": model.get("scientifically_validated"),
            "confidence": None,
            "confidence_note": model.get("uncertainty_note"),
            "held_out_metrics": {
                "validation": model.get("validation_metrics"),
                "test": model.get("test_metrics"),
            },
            "aggregation_note": (
                "The model's target is per-residue. This protein-level figure is the "
                "mean over ranked candidate residues, computed by COSMORA."
            ),
        }

    return {
        "report_version": "1.0",
        "generated_at_utc": utc_now_iso(),
        "job_id": job_id,
        "scientific_notice": SCIENTIFIC_NOTICE,
        "experiment": {
            "created_at": metadata.get("created_at"),
            "started_at": metadata.get("started_at"),
            "finished_at": metadata.get("finished_at"),
            "duration_seconds": metadata.get("duration_seconds"),
            "status": results.get("status"),
            "result_label": results.get("result_label"),
            "engine": results.get("engine"),
        },
        "protein": protein_block,
        "scenario": {
            **scenario,
            "provenance": prediction_service.scenario_provenance(),
        },
        "ml_prediction": ml_block,
        "simulation": {
            "preset": metadata.get("preset", {}),
            "metrics": results.get("metrics", {}),
            "stability_summary": results.get("stability_summary", {}),
            "topology": metadata.get("topology", {}),
        },
        "analysis": {
            "series": results.get("series", {}),
            "rmsf": results.get("rmsf", []),
            "highest_mobility_residues": results.get("highest_mobility_residues", []),
        },
        "comparison": results.get("comparison", {}),
        "reproducibility": results.get("reproducibility", {}),
        "warnings": results.get("warnings", []),
        "limitations": [*results.get("limitations", []), *PROXY_CAVEATS],
    }


def protein_detail_brief(pdb_id: str) -> dict[str, Any]:
    detail = prediction_service.protein_service.get_protein_detail(pdb_id)
    return {
        "name": detail.get("name"),
        "uniprot": detail.get("uniprot"),
        "proposed_role": detail.get("proposed_role"),
        "protein_length": detail.get("protein_length"),
        "molecular_weight": detail.get("molecular_weight"),
        "experiment_method": detail.get("experiment_method"),
        "resolution_angstrom": detail.get("resolution_angstrom"),
        "ml_dataset_split": detail.get("ml_dataset_split"),
        "source": detail.get("source"),
        "license_note": detail.get("license_note"),
    }


def build_csv_report(job_id: str) -> str:
    """A flat, spreadsheet-friendly export.

    Long-format ``section,key,value`` rather than wide columns, because the
    payload mixes scalars, time series and per-residue rows. One shape holds all
    three without a ragged header.
    """
    report = build_json_report(job_id)
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(["section", "key", "value", "unit", "note"])

    def emit(section: str, key: str, value: Any, unit: str = "", note: str = "") -> None:
        writer.writerow([section, key, "" if value is None else value, unit, note])

    emit("notice", "status", report["scientific_notice"]["status"])
    emit("notice", "headline", report["scientific_notice"]["headline"])
    for i, item in enumerate(report["scientific_notice"]["what_this_is_not"], 1):
        emit("notice", f"not_claimed_{i}", item)

    emit("experiment", "job_id", report["job_id"])
    emit("experiment", "generated_at_utc", report["generated_at_utc"])
    for key in ("created_at", "started_at", "finished_at", "status", "result_label", "engine"):
        emit("experiment", key, report["experiment"].get(key))
    emit("experiment", "duration_seconds", report["experiment"].get("duration_seconds"), "s")

    for key, value in (report.get("protein") or {}).items():
        emit("protein", key, value)

    scenario = report.get("scenario") or {}
    for key in ("scenario_id", "label", "radiation_class", "environment", "particle_group", "ml_supported"):
        emit("scenario", key, scenario.get(key))
    emit("scenario", "preset_status", (scenario.get("provenance") or {}).get("status"))

    ml = report.get("ml_prediction")
    if ml:
        emit("ml_prediction", "label", ml["label"])
        emit("ml_prediction", "degradation_percent", ml["degradation_percent"], "%",
             "Mean over ranked candidate residues; model target is per-residue.")
        for key in ("prediction_id", "model_version", "model_status", "label_source",
                    "scientifically_validated"):
            emit("ml_prediction", key, ml.get(key))
        emit("ml_prediction", "confidence", None, "",
             "Null: the bundle exposes no calibrated uncertainty.")
        for split in ("validation", "test"):
            m = (ml.get("held_out_metrics") or {}).get(split) or {}
            for stat in ("mae", "rmse", "r2"):
                if stat in m:
                    emit("ml_prediction", f"{split}_{stat}", round(float(m[stat]), 6), "",
                         f"Held-out {split} metric from model_metadata.json.")
    else:
        emit("ml_prediction", "available", "false", "",
             "Scenario is outside the model's trained vocabulary.")

    metrics = report["simulation"].get("metrics", {})
    preset = report["simulation"].get("preset", {})
    for key in ("preset_id", "label", "platform", "solvent", "production_steps",
                "equilibration_steps", "minimisation_steps", "timestep_fs",
                "report_interval", "scientific_label"):
        emit("simulation_preset", key, preset.get(key))
    for key in ("n_frames", "n_atoms", "n_ca_atoms", "steps_total",
                "simulated_time_ps", "requested_temperature_kelvin",
                "trajectory_reader", "dynamics_run"):
        emit("simulation", key, metrics.get(key))
    for group in ("rmsd_nm", "radius_of_gyration_nm", "rmsf_nm",
                  "potential_energy_kj_mol", "temperature_kelvin", "minimisation"):
        for stat, value in (metrics.get(group) or {}).items():
            emit("simulation", f"{group}.{stat}", value)

    proxy = metrics.get("degradation_proxy") or {}
    emit("degradation_proxy", "percent", proxy.get("percent"), "%",
         "Structural-drift score computed by COSMORA, NOT measured degradation.")
    emit("degradation_proxy", "formula", proxy.get("formula"))
    for name, comp in (proxy.get("components") or {}).items():
        for stat, value in comp.items():
            emit("degradation_proxy", f"{name}.{stat}", value)

    comparison = report.get("comparison") or {}
    for key in ("ml_degradation_percent", "simulation_degradation_proxy_percent",
                "difference_percentage_points", "agreement", "agreement_note"):
        emit("comparison", key, comparison.get(key))
    emit("comparison", "interpretation", comparison.get("interpretation"))

    stability = report["simulation"].get("stability_summary", {})
    emit("stability", "verdict", stability.get("verdict"))
    emit("stability", "explanation", stability.get("explanation"))
    emit("stability", "threshold_note", stability.get("threshold_note"))

    for key, value in (report.get("reproducibility") or {}).items():
        emit("reproducibility", key, value)

    for row in report["analysis"].get("highest_mobility_residues", []):
        emit("highest_mobility_residues",
             f"rank_{row['rank']}",
             f"{row['residue_id']} {row['residue_type']}",
             "nm", f"rmsf={row['rmsf_nm']}")

    for name, series in (report["analysis"].get("series") or {}).items():
        for point in series:
            emit(f"series.{name}", point["x"], point["y"])

    for row in report["analysis"].get("rmsf", []):
        emit("rmsf", row["residue_id"], row["rmsf_nm"], "nm", row["residue_type"])

    for i, item in enumerate(report.get("warnings", []), 1):
        emit("warnings", str(i), item)
    for i, item in enumerate(report.get("limitations", []), 1):
        emit("limitations", str(i), item)

    return buf.getvalue()


def report_json_payload(job_id: str) -> dict[str, Any]:
    return to_jsonable(build_json_report(job_id))
