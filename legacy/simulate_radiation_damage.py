#simulate_radiation_damage.py

import os
import random
from Bio.PDB import PDBParser, PDBIO, Select


class IntactResidueSelect(Select):
    """Filter class for Biopython PDBIO.

    Omits residues that have been marked as severed/damaged by radiation.
    """

    def __init__(self, severed_residue_ids):
        self.severed_residue_ids = set(severed_residue_ids)

    def accept_residue(self, residue):
        # Filter out hetero-atoms/water
        if residue.id[0] != " ":
            return False
        # Drop residue if its sequence ID was severed
        res_id = residue.get_id()[1]
        if res_id in self.severed_residue_ids:
            return False
        return True


def simulate_radiation_damage(
    input_pdb_path, output_pdb_path, radiation_dose="LEO"
):
    """Simulates cosmic radiation damage by probabilistically severing backbone

    residues and saving a damaged.pdb file.

    radiation_dose options: 'LEO' (Low Earth Orbit), 'DEEP_SPACE', 'SOLAR_FLARE'
    """
    if not os.path.exists(input_pdb_path):
        raise FileNotFoundError(f"File {input_pdb_path} does not exist.")

    # 1. Map radiation dose to a bond-cleavage probability threshold
    dose_probs = {
        "LEO": 0.05,  # 5% chance of scission per residue
        "DEEP_SPACE": 0.15,  # 15% chance
        "SOLAR_FLARE": 0.30,  # 30% chance
    }

    damage_prob = dose_probs.get(radiation_dose.upper(), 0.10)

    # 2. Parse PDB file
    parser = PDBParser(QUIET=True)
    structure = parser.get_structure("protein", input_pdb_path)

    # Collect all valid amino acid residue IDs
    residue_ids = []
    for residue in structure.get_residues():
        if residue.id[0] == " ":
            residue_ids.append(residue.get_id()[1])

    # 3. Probabilistically select residues to sever
    random.seed(42)  # Fixed seed for reproducible hackathon testing
    severed_ids = [
        res_id for res_id in residue_ids if random.random() < damage_prob
    ]

    print(f"Radiation Dose Profile: {radiation_dose} (Prob: {damage_prob})")
    print(f"Total residues: {len(residue_ids)}")
    print(
        f"Severed backbone bonds/residues ({len(severed_ids)}): {severed_ids}"
    )

    # 4. Save modified structure to damaged.pdb using Biopython PDBIO
    io = PDBIO()
    io.set_structure(structure)

    os.makedirs(os.path.dirname(output_pdb_path), exist_ok=True)
    io.save(output_pdb_path, IntactResidueSelect(severed_ids))

    print(f"Damaged PDB structure saved to: {output_pdb_path}")
    return severed_ids, output_pdb_path


if __name__ == "__main__":
    input_file = "data/raw/1l2y.pdb"
    output_file = "data/processed/damaged_1l2y.pdb"

    # Run simulation under Deep Space cosmic ray conditions
    severed_res, damaged_pdb = simulate_radiation_damage(
        input_file, output_file, radiation_dose="DEEP_SPACE"
    )