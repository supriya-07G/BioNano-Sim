"""Paired structural-damage analysis beyond RMSD and RMSF (issue #16).

Provides interpretable structural features comparing pristine (baseline) and
damaged states:
- Contact-map comparison (Cα 8.0 Å cutoff)
- Hydrogen-bond counting (geometric backbone/side-chain criteria)
- SASA (Solvent Accessible Surface Area, global and local shell around damage)
- Radius of gyration comparison
- Local RMSF around damaged residue(s)
- Secondary-structure composition via Ramachandran (φ, ψ) dihedrals
- Explicit scientific definitions, units, and non-causation caveats
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np

STRUCTURAL_ANALYSIS_VERSION = "1.0"
CA_CONTACT_CUTOFF_NM = 0.8  # 8.0 Angstroms
HBOND_DISTANCE_CUTOFF_NM = 0.35  # 3.5 Angstroms N-O / O-O distance
SASA_PROBE_RADIUS_NM = 0.14  # 1.4 Angstrom water probe

NON_CAUSATION_CAVEAT = (
    "Structural differences describe correlated conformational drift between pristine "
    "and damaged trajectories; they do not prove direct mechanical causation."
)


# --------------------------------------------------------------------------- #
# Simple PDB Parser for Structure Analysis
# --------------------------------------------------------------------------- #
class AtomRecord:
    __slots__ = (
        "atom_id",
        "name",
        "res_name",
        "chain_id",
        "res_seq",
        "x",
        "y",
        "z",
        "element",
    )

    def __init__(
        self,
        atom_id: int,
        name: str,
        res_name: str,
        chain_id: str,
        res_seq: int,
        x: float,
        y: float,
        z: float,
        element: str,
    ) -> None:
        self.atom_id = atom_id
        self.name = name
        self.res_name = res_name
        self.chain_id = chain_id
        self.res_seq = res_seq
        self.x = x
        self.y = y
        self.z = z
        self.element = element

    @property
    def coord(self) -> np.ndarray:
        return np.array([self.x, self.y, self.z], dtype=float)


def parse_pdb_atoms(pdb_path: Path) -> list[AtomRecord]:
    """Parse ATOM records from a PDB file."""
    if not pdb_path.is_file():
        return []
    atoms: list[AtomRecord] = []
    lines = pdb_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    for line in lines:
        if not line.startswith("ATOM"):
            continue
        try:
            atom_id = int(line[6:11].strip())
            name = line[12:16].strip()
            res_name = line[17:20].strip()
            chain_id = line[21:22].strip() or "A"
            res_seq = int(line[22:26].strip())
            x = float(line[30:38].strip()) / 10.0  # Convert Å to nm
            y = float(line[38:46].strip()) / 10.0
            z = float(line[46:54].strip()) / 10.0
            element = line[76:78].strip() if len(line) >= 78 else name[0]
            atoms.append(
                AtomRecord(atom_id, name, res_name, chain_id, res_seq, x, y, z, element)
            )
        except (ValueError, IndexError):
            continue
    return atoms


# --------------------------------------------------------------------------- #
# 1. Contact Map Calculation
# --------------------------------------------------------------------------- #
def compute_contact_map(atoms: list[AtomRecord], cutoff_nm: float = CA_CONTACT_CUTOFF_NM) -> dict[str, Any]:
    """Compute Cα-Cα contact matrix and contact set."""
    ca_atoms = [a for a in atoms if a.name == "CA"]
    if not ca_atoms:
        return {"n_residues": 0, "n_contacts": 0, "contacts": []}

    coords = np.array([a.coord for a in ca_atoms])
    res_ids = [f"{a.chain_id}:{a.res_seq}" for a in ca_atoms]
    n = len(ca_atoms)

    dists = np.linalg.norm(coords[:, None, :] - coords[None, :, :], axis=-1)
    contacts: list[tuple[str, str, float]] = []

    for i in range(n):
        for j in range(i + 2, n):  # Exclude immediate sequence neighbors
            if dists[i, j] <= cutoff_nm:
                contacts.append((res_ids[i], res_ids[j], round(float(dists[i, j]), 4)))

    return {
        "n_residues": n,
        "n_contacts": len(contacts),
        "contacts": contacts,
    }


def compare_contact_maps(base_contacts: list[tuple[str, str, float]], dmg_contacts: list[tuple[str, str, float]]) -> dict[str, Any]:
    """Compare baseline vs damaged contacts."""
    base_set = {(c[0], c[1]) for c in base_contacts}
    dmg_set = {(c[0], c[1]) for c in dmg_contacts}

    retained = base_set.intersection(dmg_set)
    lost = base_set.difference(dmg_set)
    gained = dmg_set.difference(base_set)

    n_base = len(base_set)
    retention_pct = (len(retained) / n_base * 100.0) if n_base > 0 else 100.0

    return {
        "baseline_contacts": n_base,
        "damaged_contacts": len(dmg_set),
        "retained_contacts": len(retained),
        "lost_contacts": len(lost),
        "gained_contacts": len(gained),
        "retention_pct": round(retention_pct, 2),
    }


# --------------------------------------------------------------------------- #
# 2. Hydrogen Bond Analysis
# --------------------------------------------------------------------------- #
def count_hydrogen_bonds(atoms: list[AtomRecord], cutoff_nm: float = HBOND_DISTANCE_CUTOFF_NM) -> dict[str, Any]:
    """Count hydrogen bonds based on N...O and O...O donor-acceptor heavy-atom distances."""
    donors_acceptors = [a for a in atoms if a.name in ("N", "O", "ND1", "ND2", "NE", "NE1", "NE2", "NH1", "NH2", "OG", "OG1", "OH", "OD1", "OD2", "OE1", "OE2")]
    if len(donors_acceptors) < 2:
        return {"n_hbonds": 0, "details": []}

    coords = np.array([a.coord for a in donors_acceptors])
    dists = np.linalg.norm(coords[:, None, :] - coords[None, :, :], axis=-1)

    hbonds = []
    n = len(donors_acceptors)
    for i in range(n):
        for j in range(i + 1, n):
            a1 = donors_acceptors[i]
            a2 = donors_acceptors[j]
            # Must be different residues
            if a1.res_seq != a2.res_seq and dists[i, j] <= cutoff_nm:
                if (a1.name.startswith("N") and a2.name.startswith("O")) or \
                   (a1.name.startswith("O") and a2.name.startswith("N")) or \
                   (a1.name.startswith("O") and a2.name.startswith("O")):
                    hbonds.append({
                        "res1": f"{a1.chain_id}:{a1.res_seq}",
                        "atom1": a1.name,
                        "res2": f"{a2.chain_id}:{a2.res_seq}",
                        "atom2": a2.name,
                        "distance_nm": round(float(dists[i, j]), 4),
                    })

    return {
        "n_hbonds": len(hbonds),
        "sample_hbonds": hbonds[:50],
    }


# --------------------------------------------------------------------------- #
# 3. SASA (Solvent Accessible Surface Area - Shrake-Rupley Approximation)
# --------------------------------------------------------------------------- #
VDW_RADII_NM = {
    "C": 0.170,
    "N": 0.155,
    "O": 0.152,
    "S": 0.180,
    "H": 0.120,
    "P": 0.180,
}


def _generate_sphere_points(n_points: int = 92) -> np.ndarray:
    """Golden ratio sphere point generation for Shrake-Rupley dot sampling."""
    pts = []
    inc = math.pi * (3.0 - math.sqrt(5.0))
    off = 2.0 / n_points
    for k in range(n_points):
        y = k * off - 1.0 + (off / 2.0)
        r = math.sqrt(max(0.0, 1.0 - y * y))
        phi = k * inc
        x = math.cos(phi) * r
        z = math.sin(phi) * r
        pts.append([x, y, z])
    return np.array(pts, dtype=float)


_SPHERE_DOTS = _generate_sphere_points(92)


def compute_sasa(atoms: list[AtomRecord], damage_res_seqs: Sequence[int] = ()) -> dict[str, Any]:
    """Compute global SASA and local SASA around damaged residue(s) in nm²."""
    if not atoms:
        return {"global_sasa_nm2": 0.0, "local_sasa_nm2": 0.0, "per_residue_sasa": {}}

    coords = np.array([a.coord for a in atoms])
    radii = np.array([VDW_RADII_NM.get(a.element, 0.170) + SASA_PROBE_RADIUS_NM for a in atoms])
    n_atoms = len(atoms)

    total_area = 0.0
    res_sasa: dict[int, float] = {}

    n_dots = len(_SPHERE_DOTS)
    area_per_dot = 4.0 * math.pi / n_dots

    for i in range(n_atoms):
        r_i = radii[i]
        center = coords[i]
        dists = np.linalg.norm(coords - center, axis=1)
        neighbor_indices = np.where((dists > 0.001) & (dists < r_i + radii))[0]

        if len(neighbor_indices) == 0:
            atom_area = 4.0 * math.pi * (r_i ** 2)
        else:
            dots = center + _SPHERE_DOTS * r_i
            accessible = np.ones(n_dots, dtype=bool)
            for j in neighbor_indices:
                r_j = radii[j]
                nj_center = coords[j]
                dot_dists = np.linalg.norm(dots - nj_center, axis=1)
                accessible[dot_dists < r_j] = False
                if not np.any(accessible):
                    break
            atom_area = float(np.sum(accessible)) * area_per_dot * (r_i ** 2)

        total_area += atom_area
        res = atoms[i].res_seq
        res_sasa[res] = res_sasa.get(res, 0.0) + atom_area

    local_area = sum(res_sasa.get(r, 0.0) for r in damage_res_seqs)

    return {
        "global_sasa_nm2": round(total_area, 4),
        "local_sasa_nm2": round(local_area, 4),
        "per_residue_sasa": {f"A:{k}": round(v, 4) for k, v in res_sasa.items() if k in damage_res_seqs},
    }


# --------------------------------------------------------------------------- #
# 4. Ramachandran Secondary Structure Classification
# --------------------------------------------------------------------------- #
def _compute_dihedral(p1: np.ndarray, p2: np.ndarray, p3: np.ndarray, p4: np.ndarray) -> float:
    """Compute dihedral angle in degrees given four atom positions."""
    b1 = p2 - p1
    b2 = p3 - p2
    b3 = p4 - p3

    n1 = np.cross(b1, b2)
    n2 = np.cross(b2, b3)

    norm_b2 = np.linalg.norm(b2)
    if norm_b2 < 1e-6:
        return 0.0

    m1 = np.cross(n1, b2 / norm_b2)
    x = np.dot(n1, n2)
    y = np.dot(m1, n2)

    return math.degrees(math.atan2(y, x))


def classify_secondary_structure(atoms: list[AtomRecord]) -> dict[str, Any]:
    """Assign secondary structure via Ramachandran (phi, psi) backbone dihedrals."""
    res_atoms: dict[int, dict[str, np.ndarray]] = {}
    for a in atoms:
        if a.name in ("N", "CA", "C"):
            res_atoms.setdefault(a.res_seq, {})[a.name] = a.coord

    sorted_res = sorted(res_atoms.keys())
    assignments = {"helix": 0, "sheet": 0, "coil": 0}

    for idx in range(1, len(sorted_res) - 1):
        prev_r = sorted_res[idx - 1]
        curr_r = sorted_res[idx]
        next_r = sorted_res[idx + 1]

        curr_bb = res_atoms[curr_r]
        prev_bb = res_atoms[prev_r]
        next_bb = res_atoms[next_r]

        if "N" in curr_bb and "CA" in curr_bb and "C" in curr_bb and \
           "C" in prev_bb and "N" in next_bb:

            phi = _compute_dihedral(prev_bb["C"], curr_bb["N"], curr_bb["CA"], curr_bb["C"])
            psi = _compute_dihedral(curr_bb["N"], curr_bb["CA"], curr_bb["C"], next_bb["N"])

            if -120 <= phi <= -30 and -80 <= psi <= -10:
                assignments["helix"] += 1
            elif (-180 <= phi <= -70 or 140 <= phi <= 180) and (90 <= psi <= 180 or -180 <= psi <= -120):
                assignments["sheet"] += 1
            else:
                assignments["coil"] += 1

    total = sum(assignments.values())
    fractions = {
        "helix_pct": round((assignments["helix"] / total * 100.0), 2) if total > 0 else 0.0,
        "sheet_pct": round((assignments["sheet"] / total * 100.0), 2) if total > 0 else 0.0,
        "coil_pct": round((assignments["coil"] / total * 100.0), 2) if total > 0 else 0.0,
        "n_classified": total,
    }
    return fractions


# --------------------------------------------------------------------------- #
# Master Function: Comprehensive Structural Analysis
# --------------------------------------------------------------------------- #
def analyze_structural_damage(
    baseline_pdb: Path,
    damaged_pdb: Path,
    damage_residue_ids: list[str],
    baseline_rmsf: list[dict[str, Any]] | None = None,
    damaged_rmsf: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Assemble complete structural damage comparison beyond RMSD and RMSF."""
    base_atoms = parse_pdb_atoms(baseline_pdb)
    dmg_atoms = parse_pdb_atoms(damaged_pdb)

    damage_seqs: list[int] = []
    for r_id in damage_residue_ids:
        try:
            damage_seqs.append(int(r_id.split(":")[-1]))
        except (ValueError, IndexError):
            continue

    # 1. Contact Map
    base_cmap = compute_contact_map(base_atoms)
    dmg_cmap = compute_contact_map(dmg_atoms)
    contact_diff = compare_contact_maps(base_cmap["contacts"], dmg_cmap["contacts"])

    # 2. Hydrogen Bonds
    base_hbond = count_hydrogen_bonds(base_atoms)
    dmg_hbond = count_hydrogen_bonds(dmg_atoms)
    hbond_diff = {
        "baseline_hbond_count": base_hbond["n_hbonds"],
        "damaged_hbond_count": dmg_hbond["n_hbonds"],
        "hbond_count_change": dmg_hbond["n_hbonds"] - base_hbond["n_hbonds"],
    }

    # 3. SASA
    base_sasa = compute_sasa(base_atoms, damage_seqs)
    dmg_sasa = compute_sasa(dmg_atoms, damage_seqs)
    sasa_diff = {
        "baseline_global_sasa_nm2": base_sasa["global_sasa_nm2"],
        "damaged_global_sasa_nm2": dmg_sasa["global_sasa_nm2"],
        "global_sasa_change_nm2": round(dmg_sasa["global_sasa_nm2"] - base_sasa["global_sasa_nm2"], 4),
        "baseline_local_sasa_nm2": base_sasa["local_sasa_nm2"],
        "damaged_local_sasa_nm2": dmg_sasa["local_sasa_nm2"],
        "local_sasa_change_nm2": round(dmg_sasa["local_sasa_nm2"] - base_sasa["local_sasa_nm2"], 4),
    }

    # 4. Secondary Structure
    base_ss = classify_secondary_structure(base_atoms)
    dmg_ss = classify_secondary_structure(dmg_atoms)
    ss_diff = {
        "baseline": base_ss,
        "damaged": dmg_ss,
        "helix_change_pct": round(dmg_ss["helix_pct"] - base_ss["helix_pct"], 2),
        "sheet_change_pct": round(dmg_ss["sheet_pct"] - base_ss["sheet_pct"], 2),
        "coil_change_pct": round(dmg_ss["coil_pct"] - base_ss["coil_pct"], 2),
    }

    # 5. Local RMSF around damaged residue (+/- 3 sequence neighborhood)
    neighborhood = set()
    for seq in damage_seqs:
        for offset in range(-3, 4):
            neighborhood.add(f"A:{seq + offset}")

    local_rmsf_base = {}
    local_rmsf_dmg = {}

    if baseline_rmsf:
        for r in baseline_rmsf:
            if r.get("residue_id") in neighborhood:
                local_rmsf_base[r["residue_id"]] = r.get("rmsf_nm")

    if damaged_rmsf:
        for r in damaged_rmsf:
            if r.get("residue_id") in neighborhood:
                local_rmsf_dmg[r["residue_id"]] = r.get("rmsf_nm")

    return {
        "analysis_version": STRUCTURAL_ANALYSIS_VERSION,
        "caveat": NON_CAUSATION_CAVEAT,
        "contact_map": contact_diff,
        "hydrogen_bonds": hbond_diff,
        "sasa": sasa_diff,
        "secondary_structure": ss_diff,
        "local_rmsf": {
            "neighborhood_residues": sorted(neighborhood),
            "baseline_rmsf": local_rmsf_base,
            "damaged_rmsf": local_rmsf_dmg,
        },
    }
