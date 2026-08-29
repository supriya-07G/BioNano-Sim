#!/usr/bin/env python
"""Simulate the remaining architecture blueprint items.

This script intentionally stays within the project's scientific guardrails:
- The "radiation-inspired damage proxy" is a controlled structural ablation and
  not a claim of real ionising-radiation physics.
- The OpenMM part is a short, real MD run with a light pulling restraint.
- The derived dataset captures before/after feature pairs and labels.
- The final XGBoost model plus SHAP summary is a surrogate demonstration.

Usage:
    .venv311\Scripts\python.exe scripts\simulate_blueprint_pipeline.py
"""

from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xgboost as xgb
from Bio.PDB import PDBIO, PDBParser, Select

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

REPO = Path(__file__).resolve().parents[1]
OUTDIR = REPO / "runtime" / "blueprint"
PDB_PATH = REPO / "data" / "proteins" / "pdb" / "1UBQ.pdb"


class IntactResidueSelect(Select):
    """Remove residues selected as severed by the proxy."""

    def __init__(self, severed_residue_ids: set[int]):
        self.severed_residue_ids = set(severed_residue_ids)

    def accept_residue(self, residue):
        if residue.id[0] != " ":
            return False
        return residue.get_id()[1] not in self.severed_residue_ids


def compute_graph_features(pdb_path: Path) -> dict[str, float]:
    """Compute a compact graph summary of the protein's Cα contact network."""
    parser = PDBParser(QUIET=True)
    structure = parser.get_structure("protein", str(pdb_path))
    model = structure[0]
    ca_atoms = [res["CA"] for res in model.get_residues() if res.has_id("CA") and res.id[0] == " "]
    num_nodes = len(ca_atoms)
    if num_nodes == 0:
        return {"num_nodes": 0.0, "num_edges": 0.0, "avg_degree": 0.0, "density": 0.0, "node_retention": 0.0}

    coords = np.asarray([atom.get_coord() for atom in ca_atoms], dtype=float)
    if num_nodes == 1:
        return {"num_nodes": 1.0, "num_edges": 0.0, "avg_degree": 0.0, "density": 0.0, "node_retention": 1.0}

    diff = coords[:, None, :] - coords[None, :, :]
    dist = np.linalg.norm(diff, axis=-1)
    edges = (dist <= 8.0).sum(axis=1) - 1
    num_edges = int(np.sum(edges > 0) / 2)
    const = 2 * num_edges / num_nodes if num_nodes > 0 else 0.0
    density = (2 * num_edges) / (num_nodes * (num_nodes - 1)) if num_nodes > 1 else 0.0
    return {
        "num_nodes": float(num_nodes),
        "num_edges": float(num_edges),
        "avg_degree": float(const),
        "density": float(density),
        "node_retention": 1.0,
    }


def build_damage_proxy(pdb_path: Path, dose_label: str = "DEEP_SPACE") -> tuple[Path, dict[str, float]]:
    """Create a radiation-inspired but clearly labelled damage proxy.

    This intentionally uses a probability-based residue omission as a proxy.
    """
    dose_map = {"LEO": 0.05, "DEEP_SPACE": 0.15, "SOLAR_FLARE": 0.30}
    damage_prob = dose_map[dose_label.upper()]
    parser = PDBParser(QUIET=True)
    structure = parser.get_structure("protein", str(pdb_path))
    residue_ids = [res.get_id()[1] for res in structure[0].get_residues() if res.id[0] == " "]
    random.seed(42)
    severed = {res_id for res_id in residue_ids if random.random() < damage_prob}

    damaged = OUTDIR / "damaged_proxy.pdb"
    io = PDBIO()
    io.set_structure(structure)
    io.save(str(damaged), IntactResidueSelect(severed))

    before = compute_graph_features(pdb_path)
    after = compute_graph_features(damaged)
    proxy = {
        "dose_label": dose_label,
        "damage_probability": float(damage_prob),
        "residue_count": len(residue_ids),
        "severed_residues": len(severed),
        "fraction_removed": len(severed) / len(residue_ids),
        "before_graph": before,
        "after_graph": after,
        "node_retention": after["num_nodes"] / before["num_nodes"] if before["num_nodes"] else 0.0,
        "edge_retention": after["num_edges"] / before["num_edges"] if before["num_edges"] else 0.0,
        "proxy_label": "radiation-inspired damage proxy",
        "scientific_note": "This is a controlled structural ablation used as a proxy label, not a physical radiation-transport simulation.",
    }
    return damaged, proxy


def run_openmm_damaged_pull(damaged_pdb: Path, *, steps: int = 10) -> dict[str, float]:
    """Run a brief real OpenMM MD on the damaged structure with a light pulling restraint."""
    from openmm import CustomExternalForce, LangevinMiddleIntegrator, Platform
    from openmm.app import CutoffNonPeriodic, ForceField, HBonds, Modeller, PDBFile, Simulation, StateDataReporter
    from openmm.unit import femtoseconds, kilojoule_per_mole, kelvin, nanometer, picosecond

    pdb = PDBFile(str(damaged_pdb))
    forcefield = ForceField("amber14-all.xml", "implicit/gbn2.xml")
    modeller = Modeller(pdb.topology, pdb.positions)
    modeller.addHydrogens(forcefield)

    system = forcefield.createSystem(
        modeller.topology,
        constraints=HBonds,
        rigidWater=True,
        removeCMMotion=True,
        nonbondedMethod=CutoffNonPeriodic,
        nonbondedCutoff=1.2 * nanometer,
    )

    pull = CustomExternalForce("k * ((x - x0)^2 + (y - y0)^2 + (z - z0)^2)")
    pull.addGlobalParameter("k", 0.01)
    pull.addGlobalParameter("x0", 0.0)
    pull.addGlobalParameter("y0", 0.0)
    pull.addGlobalParameter("z0", 0.5)
    for atom in modeller.topology.atoms():
        if atom.name == "CA":
            pull.addParticle(atom.index, [])
    system.addForce(pull)

    integrator = LangevinMiddleIntegrator(300 * kelvin, 1.0 / picosecond, 2.0 * femtoseconds)
    integrator.setRandomNumberSeed(42)

    platform = Platform.getPlatformByName("CPU")
    sim = Simulation(modeller.topology, system, integrator, platform)
    sim.context.setPositions(modeller.positions)
    sim.minimizeEnergy(maxIterations=25)

    state_report = OUTDIR / "openmm_state.csv"
    sim.reporters.append(StateDataReporter(str(state_report), 10, step=True, potentialEnergy=True, temperature=True))
    sim.step(steps)

    final_state = sim.context.getState(getPositions=True, getEnergy=True)
    positions = final_state.getPositions(asNumpy=True)
    final_pdb = OUTDIR / "damaged_openmm_final.pdb"
    with final_pdb.open("w", encoding="utf-8") as fh:
        PDBFile.writeFile(sim.topology, positions, fh)

    energy = final_state.getPotentialEnergy().value_in_unit(kilojoule_per_mole)
    kinetic = final_state.getKineticEnergy().value_in_unit(kilojoule_per_mole)
    temperature = (2.0 * kinetic) / (3.0 * sim.topology.getNumAtoms() * 8.31446261815324e-3)
    return {
        "steps": int(steps),
        "potential_energy_kj_mol": float(energy),
        "temperature_kelvin_proxy": float(temperature),
        "final_pdb": str(final_pdb),
        "state_csv": str(state_report),
        "note": "Short OpenMM run on a damaged structure with a light harmonic pulling restraint.",
    }


def build_derived_dataset(before_pdb: Path, after_pdb: Path, damage_proxy: dict[str, float]) -> pd.DataFrame:
    """Create a derived dataset with before/after labels for the surrogate pipeline."""
    rows = []
    for name, path, label in (("before", before_pdb, 0), ("after", after_pdb, 1)):
        feat = compute_graph_features(path)
        rows.append(
            {
                "structure_state": name,
                "damage_label": int(label),
                "dose_label": damage_proxy["dose_label"],
                "damage_probability": damage_proxy["damage_probability"],
                "residue_count": damage_proxy["residue_count"],
                "severed_residues": damage_proxy["severed_residues"],
                "fraction_removed": damage_proxy["fraction_removed"],
                "num_nodes": feat["num_nodes"],
                "num_edges": feat["num_edges"],
                "avg_degree": feat["avg_degree"],
                "density": feat["density"],
                "node_retention": feat["num_nodes"] / damage_proxy["before_graph"]["num_nodes"] if damage_proxy["before_graph"]["num_nodes"] else 0.0,
                "edge_retention": feat["num_edges"] / damage_proxy["before_graph"]["num_edges"] if damage_proxy["before_graph"]["num_edges"] else 0.0,
            }
        )
    return pd.DataFrame(rows)


def train_xgboost_surrogate(df: pd.DataFrame) -> tuple[xgb.XGBRegressor, pd.DataFrame, dict[str, float]]:
    """Train an XGBoost surrogate from the derived before/after dataset and summarise SHAP."""
    feature_cols = ["num_nodes", "num_edges", "avg_degree", "density", "node_retention", "edge_retention"]
    target_col = "damage_label"
    X = df[feature_cols].astype(float)
    y = df[target_col].astype(float)

    model = xgb.XGBRegressor(n_estimators=60, max_depth=3, learning_rate=0.12, random_state=42)
    model.fit(X, y)

    import shap

    explainer = shap.Explainer(model, X)
    shap_values = explainer(X)
    mean_abs = np.abs(shap_values.values).mean(axis=0)
    importance = pd.DataFrame({"feature": feature_cols, "mean_abs_shap": mean_abs})
    importance = importance.sort_values("mean_abs_shap", ascending=False).reset_index(drop=True)
    prediction = model.predict(X)
    summary = {
        "model_type": "XGBoostRegressor",
        "training_rows": int(len(df)),
        "predicted_before": float(prediction[0]),
        "predicted_after": float(prediction[1]),
        "shap_top_feature": importance.iloc[0]["feature"],
        "shap_top_value": float(importance.iloc[0]["mean_abs_shap"]),
    }
    return model, importance, summary


def main() -> int:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    if not PDB_PATH.exists():
        raise FileNotFoundError(f"Missing input PDB: {PDB_PATH}")

    print("BioNano-Sim blueprint simulation")
    print("=" * 72)
    print("Stage 1: radiation-inspired damage proxy")
    damaged_pdb, proxy = build_damage_proxy(PDB_PATH, dose_label="DEEP_SPACE")
    print(f"  dose_label       : {proxy['dose_label']}")
    print(f"  severed residues : {proxy['severed_residues']} / {proxy['residue_count']} ({proxy['fraction_removed']:.3f})")
    print(f"  node retention   : {proxy['node_retention']:.3f}")
    print(f"  edge retention   : {proxy['edge_retention']:.3f}")
    print(f"  output pdb       : {damaged_pdb.relative_to(REPO)}")

    print("\nStage 2: damaged MD + pulling OpenMM")
    md_summary = run_openmm_damaged_pull(damaged_pdb, steps=10)
    print(f"  steps            : {md_summary['steps']}")
    print(f"  potential energy : {md_summary['potential_energy_kj_mol']:.3f} kJ/mol")
    print(f"  temperature      : {md_summary['temperature_kelvin_proxy']:.3f} K")
    print(f"  output path      : {Path(md_summary['final_pdb']).relative_to(REPO)}")

    print("\nStage 3: derived dataset before/after labels")
    df = build_derived_dataset(PDB_PATH, damaged_pdb, proxy)
    dataset_path = OUTDIR / "derived_before_after_labels.csv"
    df.to_csv(dataset_path, index=False)
    print(f"  rows             : {len(df)}")
    print(f"  dataset file     : {dataset_path.relative_to(REPO)}")
    print(df.to_string(index=False))

    print("\nStage 4: XGBoost surrogate + SHAP")
    model, importance, summary = train_xgboost_surrogate(df)
    shap_path = OUTDIR / "xgboost_shap_importance.csv"
    importance.to_csv(shap_path, index=False)
    json_path = OUTDIR / "blueprint_summary.json"
    payload = {
        "proxy": proxy,
        "md_summary": md_summary,
        "dataset_rows": len(df),
        "xgboost_summary": summary,
        "shap_importance": importance.to_dict(orient="records"),
    }
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"  model file       : {model.model_file if hasattr(model, 'model_file') else 'in-memory'}")
    print(f"  shap file        : {shap_path.relative_to(REPO)}")
    print(f"  summary file     : {json_path.relative_to(REPO)}")
    print(importance.to_string(index=False))

    print("\nSummary")
    print("- The project now includes a real OpenMM-based damaged-structure demo and a clear radiation-inspired proxy workflow.")
    print("- The surrogate is intentionally a demonstration model; it is not presented as validated radiation-damage physics.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
