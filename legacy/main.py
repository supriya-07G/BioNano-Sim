#main.py

import os
import shutil
import tempfile
import networkx as nx
import numpy as np
import pandas as pd
import xgboost as xgb
from Bio.PDB import PDBParser, PDBIO, Select
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="BioNano-Sim ML Engine",
    description="Fast surrogate prediction API for space radiation protein damage.",
    version="1.0.0",
)

# Enable CORS so the React/WebGL frontend can call the endpoint directly
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Helper Functions ---
def extract_graph_features(pdb_path, distance_threshold=8.0):
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
        }, []

    G = nx.Graph()
    res_details = []
    for idx, atom in enumerate(ca_atoms):
        res = atom.get_parent()
        G.add_node(idx, coord=atom.get_coord())
        res_details.append({
            "residue_id": res.get_id()[1],
            "res_name": res.get_resname(),
            "coord": atom.get_coord().tolist(),
        })

    for i in range(num_nodes):
        for j in range(i + 1, num_nodes):
            dist = np.linalg.norm(G.nodes[i]["coord"] - G.nodes[j]["coord"])
            if dist <= distance_threshold:
                G.add_edge(i, j)

    degrees = dict(G.degree())
    features = {
        "num_nodes": num_nodes,
        "num_edges": G.number_of_edges(),
        "avg_degree": np.mean(list(degrees.values())) if degrees else 0.0,
        "density": nx.density(G),
    }

    # Generate node-level vulnerability heatmap scores (0.0 to 1.0)
    max_deg = max(degrees.values()) if degrees else 1
    vulnerability_heatmap = []
    for idx, res in enumerate(res_details):
        # Higher connectedness/centrality = lower vulnerability score
        deg = degrees.get(idx, 0)
        vuln_score = round(float(1.0 - (deg / (max_deg + 1e-5))), 2)
        vulnerability_heatmap.append({
            "residue_id": res["residue_id"],
            "res_name": res["res_name"],
            "vulnerability_score": vuln_score,
        })

    return features, vulnerability_heatmap


# --- Routes ---
@app.get("/")
def health_check():
    return {
        "status": "online",
        "service": "BioNano-Sim Fast Surrogate API",
        "version": "1.0.0",
    }


@app.post("/predict-damage")
async def predict_damage(
    file: UploadFile = File(...), radiation_dose: str = Form("DEEP_SPACE")
):
    """Endpoint for frontend web team: accepts a PDB file and returns instant

    structural damage prediction & vulnerability scores.
    """
    if not file.filename.endswith(".pdb"):
        raise HTTPException(
            status_code=400, detail="Invalid file format. Please upload a .pdb file."
        )

    # Save uploaded file temporarily
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdb") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = tmp.name

    try:
        # Extract features & vulnerability map from uploaded PDB
        features, heatmap = extract_graph_features(tmp_path)

        if features["num_nodes"] == 0:
            raise HTTPException(
                status_code=400, detail="No valid C-alpha atoms found in PDB structure."
            )

        # Baseline assumption for demo (1L2Y baseline length = 20 residues, edge density baseline)
        base_nodes = 20
        base_edges = 45

        node_ratio = features["num_nodes"] / base_nodes
        edge_ratio = features["num_edges"] / base_edges

        # Fast heuristic surrogate calculation (<10ms latency)
        pred_force_pN = round(float(180.0 * (edge_ratio**1.2)), 2)
        pred_stress_score = round(
            float(min(100.0, (edge_ratio**1.5) * 100.0)), 2
        )

        return {
            "filename": file.filename,
            "radiation_dose": radiation_dose,
            "summary_metrics": {
                "intact_residues": features["num_nodes"],
                "intact_contacts": features["num_edges"],
                "predicted_breaking_force_pN": pred_force_pN,
                "predicted_stress_retention_pct": pred_stress_score,
            },
            "vulnerability_heatmap": heatmap,
        }

    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)