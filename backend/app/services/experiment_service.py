"""Service layer for paired mechanical experiments (issue #7).

Handles loading, validating, and serving paired experiment artifacts,
including stiffness results, force-extension series, structures, and reports.
"""

from __future__ import annotations

import csv
import json
import re
import shutil
from pathlib import Path
from typing import Any

from app.config import settings
from app.contracts.paired_experiment import (
    validate_result_payload,
)
from app.core.exceptions import (
    NotFoundError,
    UnsafePathError,
    ValidationFailedError,
)
from app.core.logging import get_logger
from app.core.security import resolve_within
from app.simulation.quality_gates import (
    check_fit,
    check_units,
    combine,
)

logger = get_logger("COSMORA.services.experiment")

_EXPERIMENT_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


def validate_experiment_id(experiment_id: str) -> str:
    """Validate experiment ID format to prevent directory traversal."""
    eid = (experiment_id or "").strip()
    if not eid or not _EXPERIMENT_ID_PATTERN.match(eid):
        raise UnsafePathError(
            f"'{experiment_id}' is not a valid experiment identifier.",
            code="INVALID_EXPERIMENT_ID",
        )
    return eid


def get_experiments_dir() -> Path:
    """Return root directory where paired experiments are stored."""
    exp_dir = settings.runtime_dir / "experiments"
    exp_dir.mkdir(parents=True, exist_ok=True)
    return exp_dir


def experiment_path(experiment_id: str) -> Path:
    """Safely resolve an experiment directory within the experiments root."""
    eid = validate_experiment_id(experiment_id)
    root = get_experiments_dir()
    return resolve_within(root, eid)


def _check_artifacts(exp_dir: Path) -> dict[str, bool]:
    """Map available standard experiment artifacts."""
    return {
        "result_json": (exp_dir / "result.json").is_file(),
        "manifest_json": (exp_dir / "manifest.json").is_file(),
        "damage_manifest_json": (exp_dir / "damage_manifest.json").is_file(),
        "baseline_force_extension": (exp_dir / "baseline_force_extension.csv").is_file() or (exp_dir / "baseline_job" / "analysis" / "force_extension.csv").is_file(),
        "damaged_force_extension": (exp_dir / "damaged_force_extension.csv").is_file() or (exp_dir / "damaged_job" / "analysis" / "force_extension.csv").is_file(),
        "baseline_features": (exp_dir / "baseline_features.json").is_file(),
        "damaged_features": (exp_dir / "damaged_features.json").is_file(),
        "baseline_prepared_pdb": (exp_dir / "baseline_job" / "prepared.pdb").is_file(),
        "damaged_prepared_pdb": (exp_dir / "damaged_job" / "prepared.pdb").is_file(),
        "baseline_topology_pdb": (exp_dir / "baseline_job" / "topology.pdb").is_file(),
        "damaged_topology_pdb": (exp_dir / "damaged_job" / "topology.pdb").is_file(),
        "baseline_final_pdb": (exp_dir / "baseline_job" / "final.pdb").is_file(),
        "damaged_final_pdb": (exp_dir / "damaged_job" / "final.pdb").is_file(),
        "structural_analysis_json": (exp_dir / "structural_analysis.json").is_file(),
        "structural_analysis_csv": (exp_dir / "structural_analysis.csv").is_file(),
    }


def _read_force_extension_csv(csv_path: Path) -> list[dict[str, float]]:
    """Parse a force_extension.csv into structured records."""
    if not csv_path.is_file():
        return []
    records: list[dict[str, float]] = []
    with csv_path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            try:
                records.append({
                    "time_ps": float(row.get("time_ps", 0.0)),
                    "restraint_center_nm": float(row.get("restraint_center_nm", 0.0)),
                    "end_to_end_nm": float(row.get("end_to_end_nm", 0.0)),
                    "extension_nm": float(row.get("extension_nm", 0.0)),
                    "force_pn": float(row.get("force_pn", 0.0)),
                    "work_kj_mol": float(row.get("work_kj_mol", 0.0)),
                    "potential_energy_kj_mol": float(row.get("potential_energy_kj_mol", 0.0)),
                })
            except (ValueError, TypeError):
                continue
    return records


def list_experiments(limit: int = 100) -> list[dict[str, Any]]:
    """List paired experiments present in runtime/experiments."""
    root = get_experiments_dir()
    if not root.is_dir():
        return []

    summaries: list[dict[str, Any]] = []
    # Sort folders by mtime descending
    dirs = sorted(
        [d for d in root.iterdir() if d.is_dir() and not d.name.startswith(".")],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    for exp_dir in dirs[:limit]:
        res_file = exp_dir / "result.json"
        if not res_file.is_file():
            continue
        try:
            payload = json.loads(res_file.read_text(encoding="utf-8"))
            summary = {
                "experiment_id": payload.get("experiment_id", exp_dir.name),
                "protein_id": payload.get("protein_id") or payload.get("pdb_id", ""),
                "pdb_id": payload.get("pdb_id", ""),
                "chain_id": payload.get("chain_id", "A"),
                "scenario_id": payload.get("scenario_id", ""),
                "status": payload.get("status", "COMPLETED"),
                "severity_label": payload.get("severity_label", "MILD"),
                "damage_residue_id": payload.get("damage_residue_id", ""),
                "residue_type": payload.get("residue_type", ""),
                "baseline_stiffness": payload.get("baseline_stiffness"),
                "damaged_stiffness": payload.get("damaged_stiffness"),
                "stiffness_unit": payload.get("stiffness_unit", "pN/nm"),
                "mechanical_degradation_pct": payload.get("mechanical_degradation_pct"),
                "random_seed": payload.get("random_seed", 0),
                "is_synthetic": payload.get("is_synthetic", False),
                "qc_failures": payload.get("qc_failures", []),
            }
            summaries.append(summary)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to parse experiment summary in %s: %s", exp_dir.name, exc)

    return summaries


def get_experiment_detail(experiment_id: str) -> dict[str, Any]:
    """Retrieve full detail for a single paired experiment."""
    exp_dir = experiment_path(experiment_id)
    if not exp_dir.is_dir():
        raise NotFoundError(
            f"Experiment '{experiment_id}' was not found.",
            code="NOT_FOUND",
        )

    res_file = exp_dir / "result.json"
    if not res_file.is_file():
        raise NotFoundError(
            f"Experiment '{experiment_id}' has no result.json.",
            code="NOT_FOUND",
        )

    try:
        payload = json.loads(res_file.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValidationFailedError(
            f"Failed to read result.json for experiment '{experiment_id}': {exc}",
            code="INVALID_EXPERIMENT_RESULT",
        ) from exc

    # Quality gate judgment
    unit = payload.get("stiffness_unit", "pN/nm")
    fit_q = payload.get("fit_quality") or payload.get("baseline_fit_r_squared")
    findings = [
        check_units("pN", "nm") if unit == "pN/nm" else check_units(unit, "nm"),
        check_fit(fit_q, 5),
    ]
    gate_report = combine(findings)

    artifacts = _check_artifacts(exp_dir)

    detail = dict(payload)
    sa_file = exp_dir / "structural_analysis.json"
    if sa_file.is_file() and not detail.get("structural_analysis"):
        try:
            detail["structural_analysis"] = json.loads(sa_file.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass

    detail["quality_status"] = gate_report.status
    detail["artifacts"] = artifacts
    return detail


def get_force_extension(experiment_id: str) -> dict[str, Any]:
    """Retrieve paired force-extension curve series."""
    exp_dir = experiment_path(experiment_id)
    if not exp_dir.is_dir():
        raise NotFoundError(
            f"Experiment '{experiment_id}' was not found.",
            code="NOT_FOUND",
        )

    # Baseline curve
    base_csv = exp_dir / "baseline_force_extension.csv"
    if not base_csv.is_file():
        base_csv = exp_dir / "baseline_job" / "analysis" / "force_extension.csv"

    # Damaged curve
    dmg_csv = exp_dir / "damaged_force_extension.csv"
    if not dmg_csv.is_file():
        dmg_csv = exp_dir / "damaged_job" / "analysis" / "force_extension.csv"

    baseline_data = _read_force_extension_csv(base_csv)
    damaged_data = _read_force_extension_csv(dmg_csv)

    unit = "pN/nm"
    res_file = exp_dir / "result.json"
    if res_file.is_file():
        try:
            res_data = json.loads(res_file.read_text(encoding="utf-8"))
            unit = res_data.get("stiffness_unit", "pN/nm")
        except Exception:  # noqa: BLE001
            pass

    return {
        "experiment_id": experiment_id,
        "stiffness_unit": unit,
        "baseline": baseline_data,
        "damaged": damaged_data,
    }


def get_structure_file(experiment_id: str, condition: str) -> Path:
    """Resolve PDB structure file for a condition within an experiment."""
    exp_dir = experiment_path(experiment_id)
    if not exp_dir.is_dir():
        raise NotFoundError(
            f"Experiment '{experiment_id}' was not found.",
            code="NOT_FOUND",
        )

    cond = condition.lower().strip()
    mapping = {
        "baseline": [exp_dir / "baseline_job" / "final.pdb", exp_dir / "baseline_job" / "prepared.pdb"],
        "pristine": [exp_dir / "baseline_job" / "final.pdb", exp_dir / "baseline_job" / "prepared.pdb"],
        "damaged": [exp_dir / "damaged_job" / "final.pdb", exp_dir / "damaged_job" / "prepared.pdb", exp_dir / "damaged_source.pdb"],
        "baseline_prepared": [exp_dir / "baseline_job" / "prepared.pdb"],
        "damaged_prepared": [exp_dir / "damaged_job" / "prepared.pdb"],
        "baseline_topology": [exp_dir / "baseline_job" / "topology.pdb"],
        "damaged_topology": [exp_dir / "damaged_job" / "topology.pdb"],
        "baseline_final": [exp_dir / "baseline_job" / "final.pdb"],
        "damaged_final": [exp_dir / "damaged_job" / "final.pdb"],
    }

    candidates = mapping.get(cond)
    if not candidates:
        raise ValidationFailedError(
            f"Unknown condition '{condition}'. Expected one of: {list(mapping.keys())}",
            code="INVALID_CONDITION",
        )

    for p in candidates:
        if p.is_file():
            return resolve_within(exp_dir, str(p.relative_to(exp_dir)))

    raise NotFoundError(
        f"Structure for condition '{condition}' not found in experiment '{experiment_id}'.",
        code="NOT_FOUND",
    )


def get_report_payload(experiment_id: str) -> dict[str, Any]:
    """Assemble complete experiment report with manifest and features."""
    exp_dir = experiment_path(experiment_id)
    if not exp_dir.is_dir():
        raise NotFoundError(
            f"Experiment '{experiment_id}' was not found.",
            code="NOT_FOUND",
        )

    res_file = exp_dir / "result.json"
    if not res_file.is_file():
        raise NotFoundError(
            f"Experiment '{experiment_id}' has no result.json.",
            code="NOT_FOUND",
        )

    result_json = json.loads(res_file.read_text(encoding="utf-8"))

    manifest = {}
    m_file = exp_dir / "manifest.json"
    if m_file.is_file():
        try:
            manifest = json.loads(m_file.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass

    damage_manifest = {}
    dm_file = exp_dir / "damage_manifest.json"
    if dm_file.is_file():
        try:
            damage_manifest = json.loads(dm_file.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass

    baseline_features = {}
    bf_file = exp_dir / "baseline_features.json"
    if bf_file.is_file():
        try:
            baseline_features = json.loads(bf_file.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass

    damaged_features = {}
    df_file = exp_dir / "damaged_features.json"
    if df_file.is_file():
        try:
            damaged_features = json.loads(df_file.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass

    artifacts = _check_artifacts(exp_dir)

    return {
        "report_version": "1.0",
        "experiment_id": experiment_id,
        "result": result_json,
        "manifest": manifest,
        "damage_manifest": damage_manifest,
        "baseline_features": baseline_features,
        "damaged_features": damaged_features,
        "artifacts": artifacts,
    }


def import_experiment(source_path: str, override_id: str | None = None) -> dict[str, Any]:
    """Import an external experiment folder into runtime/experiments."""
    src = Path(source_path).resolve()
    if not src.is_dir():
        raise ValidationFailedError(
            f"Source path '{source_path}' is not a directory.",
            code="INVALID_IMPORT_PATH",
        )

    res_file = src / "result.json"
    if not res_file.is_file():
        raise ValidationFailedError(
            f"Source directory '{source_path}' does not contain result.json.",
            code="INVALID_IMPORT_ARTIFACT",
        )

    try:
        payload = json.loads(res_file.read_text(encoding="utf-8"))
        validate_result_payload(payload)
    except Exception as exc:
        raise ValidationFailedError(
            f"Experiment result in '{source_path}' violates experiment contract: {exc}",
            code="VALIDATION_FAILED",
        ) from exc

    exp_id = override_id or payload.get("experiment_id") or src.name
    validated_id = validate_experiment_id(exp_id)
    dest_dir = get_experiments_dir() / validated_id

    if dest_dir.exists() and dest_dir != src:
        shutil.rmtree(dest_dir)

    if src != dest_dir:
        shutil.copytree(src, dest_dir)

    detail = get_experiment_detail(validated_id)
    return {
        "experiment_id": validated_id,
        "status": "imported",
        "message": f"Successfully imported experiment '{validated_id}'",
        "detail": detail,
    }
