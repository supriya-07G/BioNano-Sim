#train_surrogate_model.py

import os
import random
import networkx as nx
import numpy as np
import pandas as pd
import xgboost as xgb
from Bio.PDB import PDBParser, PDBIO, Select
from sklearn.model_selection import train_test_split


# --- 1. Graph Feature Extractor ---
def extract_graph_features(pdb_path, distance_threshold=8.0):
    """Parses PDB and returns summary graph topology features."""
    parser = PDBParser(QUIET=True)
    structure = parser.get_structure("protein", pdb_path)

    ca_atoms = [
        res["CA"]
        for res in structure[0].get_residues()
        if res.has_id("CA") and res.id[0] == " "
    ]
    num_nodes = len(ca_atoms)

    if num_nodes == 0:
        return {
            "num_nodes": 0,
            "num_edges": 0,
            "avg_degree": 0.0,
            "density": 0.0,
        }

    G = nx.Graph()
    for idx, atom in enumerate(ca_atoms):
        G.add_node(idx, coord=atom.get_coord())

    for i in range(num_nodes):
        for j in range(i + 1, num_nodes):
            dist = np.linalg.norm(G.nodes[i]["coord"] - G.nodes[j]["coord"])
            if dist <= distance_threshold:
                G.add_edge(i, j)

    num_edges = G.number_of_edges()
    degrees = [d for _, d in G.degree()]
    avg_degree = np.mean(degrees) if degrees else 0.0
    density = nx.density(G)

    return {
        "num_nodes": num_nodes,
        "num_edges": num_edges,
        "avg_degree": avg_degree,
        "density": density,
    }


# --- 2. Synthetic Dataset Generator for Hackathon Demo ---
def generate_training_data(
    base_pdb="data/raw/1l2y.pdb", num_samples=50, output_dir="data/synthetic"
):
    """Generates synthetic dataset by simulating varied damage levels."""
    os.makedirs(output_dir, exist_ok=True)
    baseline_feats = extract_graph_features(base_pdb)

    dataset = []
    parser = PDBParser(QUIET=True)

    for i in range(num_samples):
        structure = parser.get_structure(f"sim_{i}", base_pdb)
        res_ids = [
            res.get_id()[1]
            for res in structure[0].get_residues()
            if res.id[0] == " "
        ]

        # Varying scission probabilities (1% to 35%)
        damage_rate = random.uniform(0.01, 0.35)
        severed_ids = set(
            [r for r in res_ids if random.random() < damage_rate]
        )

        # Save temporary damaged structure
        temp_out = os.path.join(output_dir, f"temp_{i}.pdb")

        class QuickSelect(Select):

            def accept_residue(self, residue):
                return (
                    residue.id[0] == " "
                    and residue.get_id()[1] not in severed_ids
                )

        io = PDBIO()
        io.set_structure(structure)
        io.save(temp_out, QuickSelect())

        # Extract damaged graph metrics
        dmg_feats = extract_graph_features(temp_out)
        os.remove(temp_out)

        # Compute ratio features (Damaged vs Baseline)
        node_retention = dmg_feats["num_nodes"] / baseline_feats["num_nodes"]
        edge_retention = (
            dmg_feats["num_edges"] / baseline_feats["num_edges"]
            if baseline_feats["num_edges"] > 0
            else 0
        )

        # Physics ground truth target simulation:
        # Retention score scales non-linearly with edge retention
        stress_retention_score = round(
            float((edge_retention**1.5) * 100), 2
        )
        breaking_force_pN = round(
            float(200.0 * (edge_retention**1.2) + random.uniform(-5, 5)), 2
        )

        dataset.append({
            "num_nodes_intact": dmg_feats["num_nodes"],
            "num_edges_intact": dmg_feats["num_edges"],
            "node_retention_ratio": node_retention,
            "edge_retention_ratio": edge_retention,
            "avg_degree": dmg_feats["avg_degree"],
            "density": dmg_feats["density"],
            "stress_retention_score": stress_retention_score,
            "breaking_force_pN": breaking_force_pN,
        })

    return pd.DataFrame(dataset)


# --- 3. Build & Train XGBoost Surrogate Model ---
if __name__ == "__main__":
    print("Generating synthetic dataset for fast surrogate training...")
    df = generate_training_data(num_samples=60)

    feature_cols = [
        "num_nodes_intact",
        "num_edges_intact",
        "node_retention_ratio",
        "edge_retention_ratio",
        "avg_degree",
        "density",
    ]

    X = df[feature_cols]
    y_force = df["breaking_force_pN"]
    y_score = df["stress_retention_score"]

    # Train XGBoost Regressor for Breaking Force
    model_force = xgb.XGBRegressor(n_estimators=50, max_depth=3, learning_rate=0.1)
    model_force.fit(X, y_force)

    # Train XGBoost Regressor for Stress Retention Score
    model_score = xgb.XGBRegressor(n_estimators=50, max_depth=3, learning_rate=0.1)
    model_score.fit(X, y_score)

    print("\nSurrogate ML Models Trained Successfully!")

    # Test sample inference on step 3 damaged structure
    test_dmg_feats = extract_graph_features("data/processed/damaged_1l2y.pdb")
    base_feats = extract_graph_features("data/raw/1l2y.pdb")

    sample_input = pd.DataFrame([{
        "num_nodes_intact": test_dmg_feats["num_nodes"],
        "num_edges_intact": test_dmg_feats["num_edges"],
        "node_retention_ratio": test_dmg_feats["num_nodes"]
        / base_feats["num_nodes"],
        "edge_retention_ratio": test_dmg_feats["num_edges"]
        / base_feats["num_edges"],
        "avg_degree": test_dmg_feats["avg_degree"],
        "density": test_dmg_feats["density"],
    }])

    pred_force = model_force.predict(sample_input)[0]
    pred_score = model_score.predict(sample_input)[0]

    print(f"\n--- FAST INFERENCE TEST RESULTS ---")
    print(f"Predicted Breaking Force: {pred_force:.2f} pN")
    print(f"Predicted Stress Retention Score: {pred_score:.2f}%")