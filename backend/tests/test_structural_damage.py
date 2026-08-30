"""Tests for structural damage analysis module (issue #16)."""

from __future__ import annotations

from pathlib import Path
import pytest

from app.analysis.structural_damage import (
    NON_CAUSATION_CAVEAT,
    analyze_structural_damage,
    classify_secondary_structure,
    compare_contact_maps,
    compute_contact_map,
    compute_sasa,
    count_hydrogen_bonds,
    parse_pdb_atoms,
)


@pytest.fixture
def sample_pdbs(tmp_path: Path) -> tuple[Path, Path]:
    base_pdb = tmp_path / "baseline.pdb"
    base_content = """ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00  0.00           N
ATOM      2  CA  ALA A   1       1.450   0.000   0.000  1.00  0.00           C
ATOM      3  C   ALA A   1       2.000   1.400   0.000  1.00  0.00           C
ATOM      4  O   ALA A   1       1.200   2.350   0.000  1.00  0.00           O
ATOM      5  CB  ALA A   1       2.000  -0.700   1.200  1.00  0.00           C
ATOM      6  N   GLU A   2       3.300   1.500   0.000  1.00  0.00           N
ATOM      7  CA  GLU A   2       3.900   2.800   0.000  1.00  0.00           C
ATOM      8  C   GLU A   2       5.400   2.700   0.000  1.00  0.00           C
ATOM      9  O   GLU A   2       6.000   1.600   0.000  1.00  0.00           O
ATOM     10  N   VAL A   3       6.000   3.800   0.000  1.00  0.00           N
ATOM     11  CA  VAL A   3       7.450   3.900   0.000  1.00  0.00           C
ATOM     12  C   VAL A   3       8.000   5.300   0.000  1.00  0.00           C
ATOM     13  O   VAL A   3       7.200   6.250   0.000  1.00  0.00           O
END
"""
    base_pdb.write_text(base_content, encoding="utf-8")

    dmg_pdb = tmp_path / "damaged.pdb"
    dmg_content = """ATOM      1  N   ALA A   1       0.000   0.000   0.000  1.00  0.00           N
ATOM      2  CA  ALA A   1       1.450   0.000   0.000  1.00  0.00           C
ATOM      3  C   ALA A   1       2.000   1.400   0.000  1.00  0.00           C
ATOM      4  O   ALA A   1       1.200   2.350   0.000  1.00  0.00           O
ATOM      6  N   GLU A   2       3.300   1.500   0.000  1.00  0.00           N
ATOM      7  CA  GLU A   2       3.900   2.800   0.000  1.00  0.00           C
ATOM      8  C   GLU A   2       5.400   2.700   0.000  1.00  0.00           C
ATOM      9  O   GLU A   2       6.000   1.600   0.000  1.00  0.00           O
ATOM     10  N   VAL A   3       6.000   3.800   0.000  1.00  0.00           N
ATOM     11  CA  VAL A   3       7.800   4.200   0.100  1.00  0.00           C
ATOM     12  C   VAL A   3       8.500   5.500   0.100  1.00  0.00           C
ATOM     13  O   VAL A   3       7.700   6.450   0.100  1.00  0.00           O
END
"""
    dmg_pdb.write_text(dmg_content, encoding="utf-8")

    return base_pdb, dmg_pdb


def test_parse_pdb_atoms(sample_pdbs: tuple[Path, Path]):
    base_pdb, _ = sample_pdbs
    atoms = parse_pdb_atoms(base_pdb)
    assert len(atoms) == 13
    assert atoms[0].name == "N"
    assert atoms[0].res_name == "ALA"
    assert atoms[0].res_seq == 1


def test_compute_contact_map(sample_pdbs: tuple[Path, Path]):
    base_pdb, _ = sample_pdbs
    atoms = parse_pdb_atoms(base_pdb)
    cmap = compute_contact_map(atoms)
    assert "n_residues" in cmap
    assert cmap["n_residues"] == 3


def test_compare_contact_maps():
    c1 = [("A:1", "A:3", 0.6)]
    c2 = [("A:1", "A:3", 0.65), ("A:1", "A:4", 0.7)]
    diff = compare_contact_maps(c1, c2)
    assert diff["retained_contacts"] == 1
    assert diff["gained_contacts"] == 1
    assert diff["retention_pct"] == 100.0


def test_compute_sasa(sample_pdbs: tuple[Path, Path]):
    base_pdb, _ = sample_pdbs
    atoms = parse_pdb_atoms(base_pdb)
    sasa = compute_sasa(atoms, damage_res_seqs=[2])
    assert sasa["global_sasa_nm2"] > 0.0
    assert "A:2" in sasa["per_residue_sasa"]


def test_analyze_structural_damage(sample_pdbs: tuple[Path, Path]):
    base_pdb, dmg_pdb = sample_pdbs
    analysis = analyze_structural_damage(
        baseline_pdb=base_pdb,
        damaged_pdb=dmg_pdb,
        damage_residue_ids=["A:2"],
        baseline_rmsf=[{"residue_id": "A:2", "rmsf_nm": 0.12}],
        damaged_rmsf=[{"residue_id": "A:2", "rmsf_nm": 0.18}],
    )

    assert analysis["caveat"] == NON_CAUSATION_CAVEAT
    assert "contact_map" in analysis
    assert "hydrogen_bonds" in analysis
    assert "sasa" in analysis
    assert "secondary_structure" in analysis
    assert analysis["local_rmsf"]["baseline_rmsf"]["A:2"] == 0.12
    assert analysis["local_rmsf"]["damaged_rmsf"]["A:2"] == 0.18
