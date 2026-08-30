"""Tests for the radiation-inspired damage proxy.

These are pure structure-file tests: no OpenMM, no dynamics. They pin down the
things that would silently corrupt a paired experiment -- damaging the wrong
residue, damaging a residue that cannot be damaged, or changing anything other
than the selected side chains.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.exceptions import InvalidSimulationInputError
from app.simulation.damage import (
    EXCLUDED_TYPES,
    NO_SIDE_CHAIN,
    PROXY_TYPE,
    SEVERITY_LEVELS,
    DamageTarget,
    apply_side_chain_loss,
    damage_rejection_reason,
    residue_types_in,
    sha256_file,
)

REPO = Path(__file__).resolve().parents[2]
UBIQUITIN = REPO / "data" / "proteins" / "pdb" / "1UBQ.pdb"


def _atom_lines(path: Path) -> list[str]:
    return [
        ln for ln in path.read_text(encoding="utf-8").splitlines()
        if ln.startswith(("ATOM", "HETATM"))
    ]


def _residue_atoms(path: Path, chain: str, seq: int) -> set[str]:
    return {
        ln[12:16].strip()
        for ln in _atom_lines(path)
        if ln[21:22].strip() == chain and ln[22:26].strip() == str(seq)
    }


# --------------------------------------------------------------------------- #
# Eligibility
# --------------------------------------------------------------------------- #
def test_glycine_and_alanine_have_no_side_chain_to_remove():
    assert damage_rejection_reason("GLY", 10) == NO_SIDE_CHAIN["GLY"]
    assert damage_rejection_reason("ALA", 10) == NO_SIDE_CHAIN["ALA"]


def test_proline_is_excluded_because_its_ring_touches_the_backbone():
    assert damage_rejection_reason("PRO", 10) == EXCLUDED_TYPES["PRO"]


def test_a_pull_attachment_residue_may_not_be_damaged():
    reason = damage_rejection_reason("ARG", 76, pull_atom_residue_seqs=(1, 76))
    assert reason and "reaction coordinate" in reason


def test_an_ordinary_residue_is_eligible():
    assert damage_rejection_reason("ARG", 45, pull_atom_residue_seqs=(1, 76)) is None


def test_severity_levels_are_ordered_and_positive():
    values = [SEVERITY_LEVELS[k] for k in ("MILD", "MODERATE", "SEVERE")]
    assert values == sorted(values)
    assert all(v >= 1 for v in values)


# --------------------------------------------------------------------------- #
# The perturbation itself
# --------------------------------------------------------------------------- #
def test_side_chain_removal_changes_only_the_target_residue(tmp_path):
    out = tmp_path / "damaged.pdb"
    manifest = apply_side_chain_loss(
        UBIQUITIN, out, chain_id="A",
        targets=[DamageTarget(residue_seq=74, residue_type="ARG")],
        severity_label="MILD", pull_atom_residue_seqs=(1, 76),
    )

    # Arginine keeps N, CA, C, O, CB and loses CG, CD, NE, CZ, NH1, NH2.
    assert _residue_atoms(out, "A", 74) == {"N", "CA", "C", "O", "CB"}
    assert set(manifest.atoms_removed) == {"CG", "CD", "NE", "CZ", "NH1", "NH2"}
    assert manifest.n_residues_damaged == 1

    # The residue is renamed so amber14 has a template that matches.
    renamed = [
        ln for ln in _atom_lines(out)
        if ln[21:22].strip() == "A" and ln[22:26].strip() == "74"
    ]
    assert all(ln[17:20].strip() == "ALA" for ln in renamed)

    # Every other atom line is byte-identical to the source.
    before = [ln for ln in _atom_lines(UBIQUITIN)
              if not (ln[21:22].strip() == "A" and ln[22:26].strip() == "74")]
    after = [ln for ln in _atom_lines(out)
             if not (ln[21:22].strip() == "A" and ln[22:26].strip() == "74")]
    assert before == after, "atoms outside the damaged residue were modified"


def test_the_proxy_is_deterministic(tmp_path):
    """The damage carries no randomness: same input, byte-identical output."""
    targets = [DamageTarget(residue_seq=74, residue_type="ARG")]
    a, b = tmp_path / "a.pdb", tmp_path / "b.pdb"
    m1 = apply_side_chain_loss(UBIQUITIN, a, chain_id="A", targets=targets)
    m2 = apply_side_chain_loss(UBIQUITIN, b, chain_id="A", targets=targets)
    assert sha256_file(a) == sha256_file(b)
    assert m1.damaged_structure_sha256 == m2.damaged_structure_sha256
    assert m1.is_stochastic is False


def test_severity_removes_more_side_chains_monotonically(tmp_path):
    """More severity must mean strictly more perturbation, or it is not a scale."""
    ladders = [
        ("MILD", [74]),
        ("MODERATE", [74, 9, 63]),
        ("SEVERE", [74, 9, 63, 72, 48, 54]),
    ]
    removed_counts = []
    for label, seqs in ladders:
        out = tmp_path / f"{label}.pdb"
        manifest = apply_side_chain_loss(
            UBIQUITIN, out, chain_id="A",
            targets=[DamageTarget(residue_seq=s) for s in seqs],
            severity_label=label, pull_atom_residue_seqs=(1, 76),
        )
        assert manifest.n_residues_damaged == len(seqs)
        assert manifest.severity_label == label
        assert len(manifest.damage_residue_ids) == len(seqs)
        removed_counts.append(manifest.n_atoms_removed)
    assert removed_counts == sorted(removed_counts)
    assert removed_counts[0] < removed_counts[-1]


def test_severity_is_never_recorded_as_a_dose(tmp_path):
    """The manifest must not let a reader mistake severity for an exposure."""
    out = tmp_path / "d.pdb"
    manifest = apply_side_chain_loss(
        UBIQUITIN, out, chain_id="A",
        targets=[DamageTarget(residue_seq=74)], severity_label="MODERATE",
    )
    body = manifest.as_dict()
    assert body["severity_is_a_dose"] is False
    assert any("NOT a dose" in n for n in body["notes"])
    # No dose-like field may appear anywhere in the manifest.
    assert not {"dose", "dose_gy", "let", "fluence", "damage_probability"} & set(body)


def test_the_manifest_records_every_target(tmp_path):
    out = tmp_path / "d.pdb"
    manifest = apply_side_chain_loss(
        UBIQUITIN, out, chain_id="A",
        targets=[
            DamageTarget(residue_seq=74, residue_type="ARG", proxy_rank=1),
            DamageTarget(residue_seq=9, residue_type="THR", proxy_rank=3),
        ],
        severity_label="MODERATE", pull_atom_residue_seqs=(1, 76),
    )
    assert manifest.damage_residue_ids == ["A:9", "A:74"]
    # The primary target is the best-ranked one, which is what the ML row keys on.
    assert manifest.damage_residue_id == "A:74"
    assert manifest.proxy_rank == 1
    assert {t["residue_type"] for t in manifest.targets} == {"ARG", "THR"}
    assert all(t["n_atoms_removed"] > 0 for t in manifest.targets)
    assert manifest.proxy_type == PROXY_TYPE


# --------------------------------------------------------------------------- #
# Refusals
# --------------------------------------------------------------------------- #
def test_damaging_a_glycine_is_refused(tmp_path):
    with pytest.raises(InvalidSimulationInputError) as exc:
        apply_side_chain_loss(
            UBIQUITIN, tmp_path / "d.pdb", chain_id="A",
            targets=[DamageTarget(residue_seq=76)],
        )
    assert exc.value.code == "DAMAGE_RESIDUE_NOT_ELIGIBLE"


def test_damaging_a_pull_anchor_is_refused(tmp_path):
    with pytest.raises(InvalidSimulationInputError) as exc:
        apply_side_chain_loss(
            UBIQUITIN, tmp_path / "d.pdb", chain_id="A",
            targets=[DamageTarget(residue_seq=1)], pull_atom_residue_seqs=(1, 76),
        )
    assert exc.value.code == "DAMAGE_RESIDUE_NOT_ELIGIBLE"


def test_a_residue_type_mismatch_is_refused(tmp_path):
    """Guards against the candidate table and the structure drifting apart."""
    with pytest.raises(InvalidSimulationInputError) as exc:
        apply_side_chain_loss(
            UBIQUITIN, tmp_path / "d.pdb", chain_id="A",
            targets=[DamageTarget(residue_seq=74, residue_type="LYS")],  # is ARG
        )
    assert exc.value.code == "DAMAGE_RESIDUE_TYPE_MISMATCH"


def test_a_missing_residue_is_refused(tmp_path):
    with pytest.raises(InvalidSimulationInputError) as exc:
        apply_side_chain_loss(
            UBIQUITIN, tmp_path / "d.pdb", chain_id="A",
            targets=[DamageTarget(residue_seq=9999)],
        )
    assert exc.value.code == "DAMAGE_RESIDUE_NOT_FOUND"


def test_duplicate_targets_are_refused(tmp_path):
    with pytest.raises(InvalidSimulationInputError) as exc:
        apply_side_chain_loss(
            UBIQUITIN, tmp_path / "d.pdb", chain_id="A",
            targets=[DamageTarget(residue_seq=74), DamageTarget(residue_seq=74)],
        )
    assert exc.value.code == "DAMAGE_DUPLICATE_TARGET"


def test_no_targets_is_refused(tmp_path):
    with pytest.raises(InvalidSimulationInputError) as exc:
        apply_side_chain_loss(UBIQUITIN, tmp_path / "d.pdb", chain_id="A", targets=[])
    assert exc.value.code == "DAMAGE_NO_TARGETS"


def test_residue_types_are_read_from_the_structure():
    types = residue_types_in(UBIQUITIN, "A")
    assert types[1] == "MET"
    assert types[74] == "ARG"
    assert types[76] == "GLY"
    assert len(types) == 76
