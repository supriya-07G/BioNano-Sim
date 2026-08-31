#!/usr/bin/env python
"""Run one paired pristine-vs-damaged mechanical experiment and emit the ML handoff.

The pair is the point. Baseline and damaged runs use the *same* structure, the
same preparation, the same force field, the same temperature, the same
minimisation and equilibration, the same production duration, the same pulling
direction, speed and spring constant, the same analysis and the same seed. The
only difference between them is one residue's side chain.

That is enforced structurally rather than by convention: both runs are handed the
identical frozen ``PROTOCOL`` object, and the damaged structure is derived from
the baseline run's own prepared.pdb, so the two runs start from the same
coordinates for every atom that still exists.

Usage:
    python scripts/run_paired_experiment.py --protein 1UBQ \\
        --scenario GCR_DEEP_SPACE_REFERENCE --rank 1 --seed 42
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import hashlib
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

import numpy as np
from app.analysis.structural_damage import analyze_structural_damage
from app.simulation.damage import (
    PROXY_TYPE,
    SEVERITY_LEVELS,
    DamageTarget,
    apply_side_chain_loss,
    damage_rejection_reason,
    sha256_file,
)
from app.simulation.engine import load_trajectory, run_simulation
from app.simulation.presets import MECHANICAL_PULL
from app.simulation.pulling import PullConfig

SCHEMA_VERSION = "1.0"
SCENARIO_VERSION = "1.0"
STIFFNESS_UNIT = "pN/nm"

# --------------------------------------------------------------------------- #
# The frozen production protocol.
#
# Changing any value here changes sim_config_hash, which is how the ML team can
# tell that two rows are not comparable. Do not edit it mid-batch.
# --------------------------------------------------------------------------- #
PROTOCOL = dataclasses.replace(
    MECHANICAL_PULL,
    preset_id="mechanical_pull_production_v1",
    label="Mechanical Pull (production v1)",
    platform="auto",
    minimisation_steps=1_000,
    equilibration_steps=5_000,     # 10 ps
    production_steps=20_000,       # 40 ps of pulling
    report_interval=100,
    pulling=PullConfig(
        spring_constant_kj_mol_nm2=1000.0,   # = 1660.539 pN/nm
        pull_velocity_nm_per_ps=0.03,        # 1.2 nm of restraint travel over 40 ps
        restraint_update_steps=10,
        sample_interval_steps=20,            # 1000 samples per curve
        fit_block_size=25,                   # -> 40 blocks fitted
    ),
)
TEMPERATURE_K = 300.0

SCENARIO_SHORT = {
    "GCR_DEEP_SPACE_REFERENCE": "GCR",
    "SPE_REFERENCE_EVENT": "SPE",
    "MARS_SURFACE_REFERENCE": "MARS",
}

UNIPROT = {
    "1TIT": "Q8WZ42", "1TEN": "P24821", "2SPC": "P13395",
    "1UBQ": "P0CG48", "1PGA": "P06654",
}

STIFFNESS_CSV_COLUMNS = [
    "experiment_id", "job_id", "protein_id", "pdb_id", "chain_id", "scenario_id",
    "damage_residue_id", "residue_type", "proxy_type", "proxy_rank", "random_seed",
    "baseline_stiffness", "damaged_stiffness", "stiffness_unit", "fit_quality",
    "sim_config_hash", "git_commit", "status", "is_synthetic",
]

# Appended after the columns the ML spec fixed, so a reader that selects by name
# is unaffected and a reader that selects by position still finds the spec block
# first. Severity is not optional context: two rows with different severity are
# different experiments.
STIFFNESS_CSV_EXTRA = [
    "severity_label", "n_residues_damaged", "damage_residue_ids",
    "mechanical_degradation_pct",
]


# --------------------------------------------------------------------------- #
# Provenance
# --------------------------------------------------------------------------- #
def protocol_config() -> dict[str, Any]:
    """The exact protocol, as the dict that gets hashed into sim_config_hash."""
    pull = PROTOCOL.pulling
    return {
        "protocol_version": "1.0",
        "engine": "openmm",
        "forcefield": list(PROTOCOL.forcefield),
        "solvent_model": PROTOCOL.solvent,
        "explicit_water": False,
        "water_model": None,
        "nonbonded_method": "CutoffNonPeriodic",
        "nonbonded_cutoff_nm": PROTOCOL.nonbonded_cutoff_nm,
        "constraints": PROTOCOL.constraints,
        "integrator": "LangevinMiddleIntegrator",
        "temperature_kelvin": TEMPERATURE_K,
        "friction_per_ps": PROTOCOL.friction_per_ps,
        "timestep_fs": PROTOCOL.timestep_fs,
        "pressure_bar": None,
        "barostat": None,
        "minimisation_steps": PROTOCOL.minimisation_steps,
        "equilibration_steps": PROTOCOL.equilibration_steps,
        "production_steps": PROTOCOL.production_steps,
        "equilibration_ps": PROTOCOL.equilibration_steps * PROTOCOL.timestep_fs / 1000.0,
        "production_ps": PROTOCOL.production_steps * PROTOCOL.timestep_fs / 1000.0,
        "pull_anchor": "first Ca of the chain (N-terminus)",
        "pull_attachment": "last Ca of the chain (C-terminus)",
        "pull_direction": "along the anchor-to-attachment interatomic distance",
        "pull_velocity_nm_per_ps": pull.pull_velocity_nm_per_ps,
        "spring_constant_kj_mol_nm2": pull.spring_constant_kj_mol_nm2,
        "spring_constant_pn_per_nm": round(pull.spring_constant_kj_mol_nm2 * 1.6605390671738467, 4),
        "restraint_update_steps": pull.restraint_update_steps,
        "sample_interval_steps": pull.sample_interval_steps,
        "stiffness_method": "linear least squares of force (pN) vs extension (nm)",
        "stiffness_unit": STIFFNESS_UNIT,
        "proxy_type": PROXY_TYPE,
    }


def sim_config_hash() -> str:
    canonical = json.dumps(protocol_config(), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def git_commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True, timeout=15, check=False
        )
        return out.stdout.strip() or "UNKNOWN"
    except Exception:  # noqa: BLE001
        return "UNKNOWN"


def now_utc() -> str:
    return datetime.now(UTC).isoformat()


# --------------------------------------------------------------------------- #
# Candidate selection
# --------------------------------------------------------------------------- #
def load_candidate(protein_id: str, rank: int) -> dict[str, Any]:
    """The ranked candidate table the ML features were built from."""
    path = REPO / "data" / "ml" / "data" / "ranked_candidate_residues.csv"
    with path.open(encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh) if r["protein_id"] == protein_id]
    if not rows:
        raise SystemExit(f"No ranked candidates for {protein_id} in {path.name}.")
    for row in rows:
        if int(float(row["proxy_rank"])) == rank:
            return row
    raise SystemExit(
        f"{protein_id} has no candidate with proxy_rank {rank}. "
        f"Available: {sorted(int(float(r['proxy_rank'])) for r in rows)}"
    )


def load_candidates(protein_id: str) -> list[dict[str, Any]]:
    path = REPO / "data" / "ml" / "data" / "ranked_candidate_residues.csv"
    with path.open(encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh) if r["protein_id"] == protein_id]
    if not rows:
        raise SystemExit(f"No ranked candidates for {protein_id} in {path.name}.")
    return sorted(rows, key=lambda r: int(float(r["proxy_rank"])))


def ca_residue_seqs(pdb: Path, chain_id: str) -> list[int]:
    """Residue numbers carrying a CA atom, in file order."""
    seqs: list[int] = []
    for line in pdb.read_text(encoding="utf-8").splitlines():
        if not line.startswith("ATOM"):
            continue
        if line[12:16].strip() != "CA" or line[21:22].strip() != chain_id:
            continue
        raw = line[22:26].strip()
        if raw.isdigit():
            seqs.append(int(raw))
    return seqs


def select_targets(
    protein_id: str, n_wanted: int, pull_seqs: tuple[int, ...], structure_types: dict[int, str]
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """The top-N eligible candidates by proxy_rank, plus why any were skipped.

    Not every ranked candidate can be damaged: the ranking scores side-chain-loss
    susceptibility, which is a different question from whether a side chain exists
    (glycine) or whether the residue is a pulling attachment point. Rejections are
    returned rather than silently dropped, so the handoff records them.
    """
    chosen: list[dict[str, Any]] = []
    rejected: list[dict[str, str]] = []
    for row in load_candidates(protein_id):
        seq = int(row["residue_id"].split(":")[1])
        actual = structure_types.get(seq, row["residue_type"])
        reason = damage_rejection_reason(actual, seq, pull_seqs)
        if reason:
            rejected.append({
                "residue_id": row["residue_id"],
                "residue_type": actual,
                "proxy_rank": row["proxy_rank"],
                "reason": reason,
            })
            continue
        chosen.append(row)
        if len(chosen) == n_wanted:
            break
    if len(chosen) < n_wanted:
        raise SystemExit(
            f"{protein_id} has only {len(chosen)} eligible candidate residues but "
            f"{n_wanted} were required for this severity. Rejected: "
            + "; ".join(f"{r['residue_id']} ({r['residue_type']})" for r in rejected)
        )
    return chosen, rejected


# --------------------------------------------------------------------------- #
# Analysis helpers
# --------------------------------------------------------------------------- #
def _series_stats(series: list[dict[str, float]], key: str = "y") -> tuple[float | None, float | None]:
    """Mean and std of an engine series. The engine emits {"x": time, "y": value}."""
    values = [s[key] for s in series if s.get(key) is not None]
    if not values:
        return None, None
    arr = np.asarray(values, dtype=float)
    return round(float(arr.mean()), 6), round(float(arr.std()), 6)


def mean_contact_count(job_dir: Path, topology: dict[str, Any]) -> float | None:
    """Mean number of Ca-Ca neighbours within 0.8 nm, averaged over residues and frames.

    0.8 nm is the same threshold the project's residue_contact_count feature and
    legacy contact-graph code use, so this number is on the same scale.
    """
    dcd = job_dir / "trajectory.dcd"
    top = job_dir / "topology.pdb"
    if not dcd.exists() or not top.exists():
        return None
    try:
        frames, _reader = load_trajectory(dcd, top)
    except Exception:  # noqa: BLE001
        return None
    ca = np.array(
        [i for i in topology.get("ca_indices", []) if i < frames.shape[1]], dtype=int
    )
    if ca.size < 2:
        return None
    per_frame = []
    for frame in frames[:, ca, :]:
        d = np.linalg.norm(frame[:, None, :] - frame[None, :, :], axis=-1)
        np.fill_diagonal(d, np.inf)
        per_frame.append(float((d < 0.8).sum(axis=1).mean()))
    return round(float(np.mean(per_frame)), 6)


def residue_rmsf(result: Any, residue_id: str) -> float | None:
    for row in result.rmsf:
        if row.get("residue_id") == residue_id:
            return row.get("rmsf_nm")
    return None


def features_block(result: Any, job_dir: Path, label: str) -> dict[str, Any]:
    rmsd_mean, rmsd_std = _series_stats(result.series.get("rmsd", []))
    rg_mean, rg_std = _series_stats(result.series.get("radius_of_gyration", []))
    metrics = result.metrics
    return {
        "run": label,
        "rmsd_mean_nm": rmsd_mean,
        "rmsd_std_nm": rmsd_std,
        "rg_mean_nm": rg_mean,
        "rg_std_nm": rg_std,
        "contact_mean": mean_contact_count(job_dir, result.topology),
        "hbond_mean": None,
        "hbond_unavailable_reason": (
            "No hydrogen-bond detector is implemented in this pipeline. Reporting a "
            "number would mean inventing one, so the field is left null."
        ),
        "secondary_structure": None,
        "secondary_structure_unavailable_reason": (
            "Secondary-structure assignment needs DSSP, which is not a dependency of "
            "this project. Left null rather than guessed."
        ),
        "temperature_mean_kelvin": metrics.get("temperature_kelvin", {}).get("mean"),
        "temperature_std_kelvin": metrics.get("temperature_kelvin", {}).get("std"),
        "potential_energy_mean_kj_mol": metrics.get("potential_energy_kj_mol", {}).get("mean"),
        "n_atoms": result.topology.get("n_atoms"),
        "n_residues": result.topology.get("n_residues"),
        "platform": result.topology.get("platform"),
        "bit_reproducible": result.topology.get("bit_reproducible", False),
        "simulated_time_ps": metrics.get("simulated_time_ps"),
        "degradation_proxy": metrics.get("degradation_proxy"),
    }


# --------------------------------------------------------------------------- #
# Running one half of the pair
# --------------------------------------------------------------------------- #
def run_half(source_pdb: Path, job_dir: Path, chain_id: str, seed: int, label: str) -> Any:
    job_dir.mkdir(parents=True, exist_ok=True)
    log_path = job_dir / "simulation.log"
    lines: list[str] = []
    started = time.time()
    last = [0.0]

    def report(stage, message, payload):
        now = time.time()
        if now - last[0] > 5.0:
            last[0] = now
            print(f"    [{label}] {stage.value}: {message}")

    result = run_simulation(
        source_pdb=source_pdb,
        job_dir=job_dir,
        chain_id=chain_id,
        preset=PROTOCOL,
        temperature_kelvin=TEMPERATURE_K,
        seed=seed,
        report=report,
        should_cancel=lambda: False,
        log=lines.append,
    )
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"    [{label}] done in {time.time() - started:.1f} s")
    return result


def stiffness_of(result: Any) -> tuple[float | None, float | None, dict[str, Any]]:
    fit = result.metrics.get("pulling", {}).get("stiffness_fit", {})
    if not fit.get("available"):
        return None, None, fit
    return fit.get("apparent_stiffness_pn_per_nm"), fit.get("r_squared"), fit


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--protein", default="1UBQ")
    ap.add_argument("--chain", default="A")
    ap.add_argument("--scenario", default="GCR_DEEP_SPACE_REFERENCE",
                    choices=sorted(SCENARIO_SHORT))
    ap.add_argument("--rank", type=int, default=1,
                    help="proxy_rank of the primary candidate (MILD severity only)")
    ap.add_argument("--severity", default="MILD", choices=sorted(SEVERITY_LEVELS),
                    help="how many side chains to remove: "
                         + ", ".join(f"{k}={v}" for k, v in SEVERITY_LEVELS.items()))
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--outroot", default=str(REPO / "runtime" / "experiments"))
    args = ap.parse_args()

    source_early = REPO / "data" / "proteins" / "pdb" / f"{args.protein}.pdb"
    if not source_early.exists():
        raise SystemExit(f"Structure not found: {source_early}")

    # The pull attaches to the first and last Ca of the chain. Predict them here
    # so ineligible candidates are excluded before a baseline run is spent; the
    # damage step re-checks against the real anchors and hard-fails on a mismatch.
    ca_seqs = ca_residue_seqs(source_early, args.chain)
    predicted_pull = (ca_seqs[0], ca_seqs[-1]) if len(ca_seqs) >= 2 else ()
    from app.simulation.damage import residue_types_in
    structure_types = residue_types_in(source_early, args.chain)

    n_damage = SEVERITY_LEVELS[args.severity]
    if args.severity == "MILD":
        primary = load_candidate(args.protein, args.rank)
        reason = damage_rejection_reason(
            structure_types.get(int(primary["residue_id"].split(":")[1]), primary["residue_type"]),
            int(primary["residue_id"].split(":")[1]),
            predicted_pull,
        )
        if reason:
            raise SystemExit(
                f"{args.protein} rank {args.rank} ({primary['residue_id']} "
                f"{primary['residue_type']}) cannot be damaged: {reason}."
            )
        selected, rejected = [primary], []
    else:
        selected, rejected = select_targets(
            args.protein, n_damage, predicted_pull, structure_types
        )

    candidate = selected[0]
    residue_id = candidate["residue_id"]                 # e.g. "A:74"
    residue_type = candidate["residue_type"]
    short = SCENARIO_SHORT[args.scenario]
    experiment_id = (
        f"{args.protein}_{short}_{args.severity}_{residue_id.replace(':', '')}"
        f"_seed{args.seed}"
    )
    out = Path(args.outroot) / experiment_id
    out.mkdir(parents=True, exist_ok=True)

    print(f"\n=== {experiment_id} ===")
    print(f"  severity : {args.severity} -> {n_damage} side chain(s) removed")
    print("  residues : " + ", ".join(
        f"{c['residue_type']} {c['residue_id']} (rank {int(float(c['proxy_rank']))})"
        for c in selected
    ))
    for r in rejected:
        print(f"    skipped {r['residue_type']} {r['residue_id']}: {r['reason']}")
    print(f"  protocol : {PROTOCOL.production_steps} pull steps, "
          f"v={PROTOCOL.pulling.pull_velocity_nm_per_ps} nm/ps, "
          f"k={PROTOCOL.pulling.spring_constant_kj_mol_nm2} kJ/mol/nm^2")
    print(f"  config   : {sim_config_hash()[:16]}...")

    source = source_early

    # --- 1. baseline --------------------------------------------------------
    print("\n  [1/4] baseline pull")
    baseline_dir = out / "baseline_job"
    baseline = run_half(source, baseline_dir, args.chain, args.seed, "baseline")

    # --- 2. damage ----------------------------------------------------------
    # Derived from the baseline's own prepared.pdb, so every surviving atom
    # starts from identical coordinates.
    print("\n  [2/4] applying damage proxy")
    pull_sel = baseline.metrics["pulling"]["selection"]
    anchor_seq = int(pull_sel["anchor_residue"].split(":")[1])
    pulled_seq = int(pull_sel["pulled_residue"].split(":")[1])
    damaged_source = out / "damaged_source.pdb"
    manifest = apply_side_chain_loss(
        baseline_dir / "prepared.pdb",
        damaged_source,
        chain_id=args.chain,
        targets=[
            DamageTarget(
                residue_seq=int(c["residue_id"].split(":")[1]),
                residue_type=c["residue_type"],
                residue_index_norm=float(c["residue_index_norm"]),
                proxy_rank=int(float(c["proxy_rank"])),
            )
            for c in selected
        ],
        severity_label=args.severity,
        pull_atom_residue_seqs=(anchor_seq, pulled_seq),
    )
    print(f"    {manifest.n_residues_damaged} residue(s), "
          f"{manifest.n_atoms_removed} atoms removed")

    # --- 3. damaged ---------------------------------------------------------
    print("\n  [3/4] damaged pull (identical protocol)")
    damaged_dir = out / "damaged_job"
    damaged = run_half(damaged_source, damaged_dir, args.chain, args.seed, "damaged")

    # --- 4. handoff ---------------------------------------------------------
    print("\n  [4/4] writing handoff files")
    base_k, base_r2, base_fit = stiffness_of(baseline)
    dmg_k, dmg_r2, dmg_fit = stiffness_of(damaged)

    degradation = None
    if base_k not in (None, 0) and dmg_k is not None:
        # Preserved with its sign: a stiffer damaged protein is a real result.
        degradation = round((base_k - dmg_k) / base_k * 100.0, 6)

    qc_failures: list[str] = []
    if base_k is None or not np.isfinite(base_k):
        qc_failures.append("baseline stiffness is missing or non-finite")
    if dmg_k is None or not np.isfinite(dmg_k):
        qc_failures.append("damaged stiffness is missing or non-finite")
    if base_k is not None and base_k <= 0:
        qc_failures.append(
            f"baseline stiffness is {base_k} pN/nm; a non-positive elastic stiffness "
            "is unphysical and the run must not be trained on"
        )
    if not base_fit.get("reliable", False):
        qc_failures.append(
            "baseline stiffness fit is flagged unreliable: "
            + "; ".join(base_fit.get("unreliable_reasons", []))
        )
    if not dmg_fit.get("reliable", False):
        qc_failures.append(
            "damaged stiffness fit is flagged unreliable: "
            + "; ".join(dmg_fit.get("unreliable_reasons", []))
        )
    for name, res in (("baseline", baseline), ("damaged", damaged)):
        if not res.metrics.get("pulling", {}).get("completed", False):
            qc_failures.append(f"{name} pull did not run to completion")

    status = "COMPLETED" if not qc_failures else "QC_FAILED"

    for label, res, job_dir in (
        ("baseline", baseline, baseline_dir), ("damaged", damaged, damaged_dir)
    ):
        (out / f"{label}_features.json").write_text(
            json.dumps(features_block(res, job_dir, label), indent=2) + "\n", encoding="utf-8"
        )
        src = job_dir / "analysis" / "force_extension.csv"
        if src.exists():
            (out / f"{label}_force_extension.csv").write_text(
                src.read_text(encoding="utf-8"), encoding="utf-8"
            )

    (out / "damage_manifest.json").write_text(
        json.dumps(manifest.as_dict(), indent=2) + "\n", encoding="utf-8"
    )

    base_pdb = baseline_dir / "prepared.pdb"
    if not base_pdb.exists():
        base_pdb = baseline_dir / "final.pdb"
    dmg_pdb = damaged_dir / "prepared.pdb"
    if not dmg_pdb.exists():
        dmg_pdb = damaged_dir / "final.pdb"

    struct_analysis = analyze_structural_damage(
        baseline_pdb=base_pdb,
        damaged_pdb=dmg_pdb,
        damage_residue_ids=manifest.damage_residue_ids,
        baseline_rmsf=baseline.rmsf,
        damaged_rmsf=damaged.rmsf,
    )

    (out / "structural_analysis.json").write_text(
        json.dumps(struct_analysis, indent=2) + "\n", encoding="utf-8"
    )

    csv_rows = [
        ("metric", "value", "unit_or_info"),
        ("retention_pct", struct_analysis["contact_map"]["retention_pct"], "%"),
        ("retained_contacts", struct_analysis["contact_map"]["retained_contacts"], "count"),
        ("lost_contacts", struct_analysis["contact_map"]["lost_contacts"], "count"),
        ("gained_contacts", struct_analysis["contact_map"]["gained_contacts"], "count"),
        ("baseline_hbond_count", struct_analysis["hydrogen_bonds"]["baseline_hbond_count"], "count"),
        ("damaged_hbond_count", struct_analysis["hydrogen_bonds"]["damaged_hbond_count"], "count"),
        ("hbond_count_change", struct_analysis["hydrogen_bonds"]["hbond_count_change"], "count"),
        ("global_sasa_change_nm2", struct_analysis["sasa"]["global_sasa_change_nm2"], "nm^2"),
        ("local_sasa_change_nm2", struct_analysis["sasa"]["local_sasa_change_nm2"], "nm^2"),
        ("helix_change_pct", struct_analysis["secondary_structure"]["helix_change_pct"], "%"),
        ("sheet_change_pct", struct_analysis["secondary_structure"]["sheet_change_pct"], "%"),
        ("coil_change_pct", struct_analysis["secondary_structure"]["coil_change_pct"], "%"),
        ("caveat", struct_analysis["caveat"], "scientific_disclaimer"),
    ]
    with (out / "structural_analysis.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerows(csv_rows)

    result_json: dict[str, Any] = {
        "experiment_id": experiment_id,
        "structural_analysis": struct_analysis,
        "job_id": f"{experiment_id}",
        "baseline_job_id": baseline_dir.name,
        "damaged_job_id": damaged_dir.name,
        "schema_version": SCHEMA_VERSION,
        "status": status,

        "protein_id": args.protein,
        "pdb_id": args.protein,
        "chain_id": args.chain,
        "uniprot_id": UNIPROT.get(args.protein),

        "scenario_id": args.scenario,
        "scenario_version": SCENARIO_VERSION,
        "scenario_dose": None,
        "scenario_let": None,
        "scenario_damage_probability": None,
        "scenario_context_note": (
            "No verified NASA/OLTARIS dose, LET or fluence value was available, so "
            "these fields are null rather than invented. The scenario ID is "
            "provenance only: it does not enter the damage proxy or the simulation."
        ),

        "damage_residue_id": residue_id,
        "residue_type": residue_type,
        "residue_index_norm": float(candidate["residue_index_norm"]),

        "proxy_type": PROXY_TYPE,
        "proxy_rank": int(float(candidate["proxy_rank"])),
        "random_seed": args.seed,

        "severity_label": args.severity,
        "n_residues_damaged": manifest.n_residues_damaged,
        "damage_residue_ids": manifest.damage_residue_ids,
        "n_side_chain_atoms_removed": manifest.n_atoms_removed,
        "severity_is_a_dose": False,
        "severity_note": (
            "Severity counts removed side chains. It is a structural axis only and "
            "does not correspond to any Gy, LET or fluence value."
        ),
        "ineligible_candidates": rejected,

        "baseline_rmsd_mean": None, "baseline_rmsd_std": None,
        "baseline_rg_mean": None, "baseline_rg_std": None,
        "baseline_hbond_mean": None, "baseline_contact_mean": None,
        "baseline_stiffness": base_k,

        "residue_sasa_norm": float(candidate["residue_sasa_norm"]),
        "residue_rmsf": residue_rmsf(baseline, residue_id),
        "residue_contact_count": float(candidate["residue_contact_count"]),
        "secondary_structure": None,
        "qualitative_susceptibility": candidate["qualitative_susceptibility"],

        "damaged_stiffness": dmg_k,
        "damaged_rmsd_mean": None,

        "stiffness_unit": STIFFNESS_UNIT,
        "fit_quality": base_r2,
        "baseline_fit_r_squared": base_r2,
        "damaged_fit_r_squared": dmg_r2,
        "baseline_fit": base_fit,
        "damaged_fit": dmg_fit,

        "mechanical_degradation_pct": degradation,
        "degradation_definition": (
            "(baseline_stiffness - damaged_stiffness) / baseline_stiffness * 100. "
            "Sign preserved: a negative value means the damaged construct was "
            "stiffer, and is reported as measured."
        ),

        "sim_config_hash": sim_config_hash(),
        "git_commit": git_commit(),
        "structure_sha256": manifest.source_structure_sha256,
        "damaged_structure_sha256": manifest.damaged_structure_sha256,
        "is_synthetic": False,
        "created_at_utc": now_utc(),
        "qc_failures": qc_failures,
    }

    base_feat = json.loads((out / "baseline_features.json").read_text(encoding="utf-8"))
    dmg_feat = json.loads((out / "damaged_features.json").read_text(encoding="utf-8"))
    result_json.update({
        "baseline_rmsd_mean": base_feat["rmsd_mean_nm"],
        "baseline_rmsd_std": base_feat["rmsd_std_nm"],
        "baseline_rg_mean": base_feat["rg_mean_nm"],
        "baseline_rg_std": base_feat["rg_std_nm"],
        "baseline_contact_mean": base_feat["contact_mean"],
        "baseline_hbond_mean": base_feat["hbond_mean"],
        "damaged_rmsd_mean": dmg_feat["rmsd_mean_nm"],
    })

    (out / "result.json").write_text(json.dumps(result_json, indent=2) + "\n", encoding="utf-8")

    manifest_json = {
        "experiment_id": experiment_id,
        "schema_version": SCHEMA_VERSION,
        "created_at_utc": now_utc(),
        "protocol": protocol_config(),
        "sim_config_hash": sim_config_hash(),
        "git_commit": git_commit(),
        "paired_runs": {
            "baseline": {
                "job_dir": str(baseline_dir.relative_to(out)),
                "source_structure": str(source),
                "structure_sha256": sha256_file(source),
                "prepared_sha256": sha256_file(baseline_dir / "prepared.pdb"),
                "trajectory": str((baseline_dir / "trajectory.dcd").relative_to(out)),
                "force_extension_csv": "baseline_force_extension.csv",
                "platform": baseline.topology.get("platform"),
                "seed": args.seed,
            },
            "damaged": {
                "job_dir": str(damaged_dir.relative_to(out)),
                "source_structure": "damaged_source.pdb",
                "structure_sha256": manifest.damaged_structure_sha256,
                "prepared_sha256": sha256_file(damaged_dir / "prepared.pdb"),
                "trajectory": str((damaged_dir / "trajectory.dcd").relative_to(out)),
                "force_extension_csv": "damaged_force_extension.csv",
                "platform": damaged.topology.get("platform"),
                "seed": args.seed,
            },
        },
        "comparability": {
            "identical_protocol": True,
            "identical_seed": True,
            "only_difference": (
                f"{manifest.n_residues_damaged} side chain(s) removed "
                f"({manifest.n_atoms_removed} atoms) and renamed ALA: "
                + ", ".join(manifest.damage_residue_ids)
            ),
            "severity_label": args.severity,
            "damaged_derived_from": "the baseline run's own prepared.pdb",
        },
        "limitations": [
            *baseline.notes[:0],
            ("Implicit solvent (GBn2): there is no water model, no box, no barostat "
             "and therefore no density. Pressure is not defined for these runs."),
            ("50 ps of pulling at 0.02 nm/ps is a non-equilibrium loading rate around "
             "a million times faster than an AFM experiment. Absolute forces are far "
             "above experimental values; only baseline-vs-damaged comparisons under "
             "this identical protocol are meaningful."),
            ("The damage proxy is a controlled side-chain truncation, not radiation "
             "chemistry. No dose or LET value was used."),
            ("Runs on the auto-selected platform are not bit-reproducible. Repeat "
             "seeds are the intended way to capture run-to-run variation."),
        ],
        "status": status,
        "qc_failures": qc_failures,
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest_json, indent=2) + "\n", encoding="utf-8"
    )

    # --- combined stiffness table ------------------------------------------
    csv_path = REPO / "data" / "ml" / "stiffness" / "stiffness_results_REAL_v1.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "experiment_id": experiment_id,
        "job_id": experiment_id,
        "protein_id": args.protein,
        "pdb_id": args.protein,
        "chain_id": args.chain,
        "scenario_id": args.scenario,
        "damage_residue_id": residue_id,
        "residue_type": residue_type,
        "proxy_type": PROXY_TYPE,
        "proxy_rank": int(float(candidate["proxy_rank"])),
        "random_seed": args.seed,
        "baseline_stiffness": base_k,
        "damaged_stiffness": dmg_k,
        "stiffness_unit": STIFFNESS_UNIT,
        "fit_quality": base_r2,
        "sim_config_hash": sim_config_hash(),
        "git_commit": git_commit(),
        "status": status,
        "is_synthetic": False,
        "severity_label": args.severity,
        "n_residues_damaged": manifest.n_residues_damaged,
        "damage_residue_ids": " ".join(manifest.damage_residue_ids),
        "mechanical_degradation_pct": degradation,
    }
    existing: list[dict[str, str]] = []
    if csv_path.exists():
        with csv_path.open(encoding="utf-8", newline="") as fh:
            existing = [r for r in csv.DictReader(fh) if r["experiment_id"] != experiment_id]
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=STIFFNESS_CSV_COLUMNS + STIFFNESS_CSV_EXTRA,
            lineterminator="\n", restval="",
        )
        writer.writeheader()
        for r in existing:
            writer.writerow(r)
        writer.writerow(row)
    all_cols = STIFFNESS_CSV_COLUMNS + STIFFNESS_CSV_EXTRA
    (out / "stiffness_row.csv").write_text(
        ",".join(all_cols) + "\n"
        + ",".join("" if row.get(c) is None else str(row[c]) for c in all_cols) + "\n",
        encoding="utf-8",
    )

    # --- report -------------------------------------------------------------
    print(f"\n  baseline stiffness : {base_k} {STIFFNESS_UNIT}  (r2 {base_r2})")
    print(f"  damaged stiffness  : {dmg_k} {STIFFNESS_UNIT}  (r2 {dmg_r2})")
    print(f"  degradation        : {degradation} %")
    print(f"  status             : {status}")
    for failure in qc_failures:
        print(f"    QC: {failure}")
    print(f"\n  files -> {out}")
    for f in sorted(out.iterdir()):
        if f.is_file():
            print(f"    {f.name}")
    print(f"  stiffness table -> {csv_path.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
