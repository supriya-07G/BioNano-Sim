#build_contact_graph.py

import os
import networkx as nx
import numpy as np
from Bio.PDB import PDBParser


def build_protein_graph(pdb_path, distance_threshold=8.0):
    """Parses a PDB file, extracts C-alpha backbone coordinates,

    and builds an 8 Angstrom contact graph network.
    """
    if not os.path.exists(pdb_path):
        raise FileNotFoundError(f"File {pdb_path} does not exist.")

    # 1. Parse structure using Biopython
    parser = PDBParser(QUIET=True)
    structure = parser.get_structure("protein", pdb_path)

    # Grab the first model and first chain
    model = structure[0]

    # Extract all C-alpha (CA) atoms representing residue positions
    ca_atoms = []
    for residue in model.get_residues():
        # Filter out hetero-atoms/water (only keep standard amino acids)
        if residue.has_id("CA") and residue.id[0] == " ":
            ca_atoms.append(residue["CA"])

    num_residues = len(ca_atoms)
    print(
        f"Parsed {pdb_path}: Found {num_residues} C-alpha nodes."
    )  #

    # 2. Build NetworkX Graph
    G = nx.Graph()

    # Add nodes with metadata (residue name, chain, 3D coordinates)
    for idx, atom in enumerate(ca_atoms):
        parent_res = atom.get_parent()
        coord = atom.get_coord()  # [x, y, z] numpy array

        G.add_node(
            idx,
            res_name=parent_res.get_resname(),
            res_id=parent_res.get_id()[1],
            coord=coord,
        )

    # 3. Add Edges based on the 8 Angstrom distance threshold
    for i in range(num_residues):
        for j in range(i + 1, num_residues):
            coord_i = G.nodes[i]["coord"]
            coord_j = G.nodes[j]["coord"]

            # Calculate Euclidean distance between C-alpha atoms
            distance = np.linalg.norm(coord_i - coord_j)

            if distance <= distance_threshold:
                # Add edge with distance attribute
                G.add_edge(i, j, weight=round(float(distance), 2))

    print(
        f"Graph construction complete: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges (threshold: {distance_threshold} Å)."
    )
    return G


if __name__ == "__main__":
    # Test on the Step 1 baseline file
    pdb_file = "data/raw/1l2y.pdb"

    # Build the graph
    protein_graph = build_protein_graph(pdb_file, distance_threshold=8.0)

    # Print sample node and edge properties
    first_node = protein_graph.nodes[0]
    print(
        f"\nSample Node 0: Residue {first_node['res_name']}-{first_node['res_id']} at {first_node['coord']}"
    )

    sample_edges = list(protein_graph.edges(data=True))[:3]
    print(f"Sample Edges (< 8 Å): {sample_edges}")