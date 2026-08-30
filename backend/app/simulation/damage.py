"""The radiation-inspired damage proxy.

What this is
------------
A chosen set of residues has each side chain removed beyond CB, and each is
renamed to ALA so the force field has a template that matches. Everything else
about the structure -- every other residue, every backbone atom, the coordinates
of every atom that remains -- is untouched. The damaged structure is therefore
the baseline structure minus some side chains, and nothing else.

Severity is the number of side chains removed. It is a *structural* axis, not a
dose axis: ``MODERATE`` does not mean 15 Gy or any other physical quantity, and
nothing in this module converts between the two. Inventing that mapping is
exactly the thing the ML handoff spec forbids.

What this is NOT
----------------
This is **not** atomistic radiation chemistry. There is no particle track, no
energy deposition, no radical formation, no bond-scission kinetics and no dose
dependence. Nothing here computes what a cosmic ray would actually do.

It is a *controlled structural perturbation* chosen to be:

  * well defined -- an explicit residue list and one rule, no randomness,
  * reproducible -- the same residues and rule always give the same structure,
  * mechanically meaningful -- removing a side chain removes the contacts that
    side chain made, which is a load-bearing change a pulling experiment can see,
  * gradeable -- removing more side chains is monotonically more perturbation,
    which gives the ML target a range to learn instead of a near-binary flip.

The scenario ID attached to an experiment (GCR_DEEP_SPACE_REFERENCE and friends)
is *provenance metadata*. It records which mission environment the experiment is
labelled for. It does not enter this calculation, and no dose, LET or fluence
value is used or invented anywhere in this module.

Why side-chain loss specifically
--------------------------------
It matches the target the existing ML feature schema was built around
(``proxy_type = SIDE_CHAIN_LOSS``), and it is the mildest perturbation that
still changes a residue's interactions. Deleting whole residues would sever the
backbone and turn a mechanical experiment into a chain-scission experiment,
which is a different question and produces a damaged construct that is not
comparable to its own baseline.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.core.exceptions import InvalidSimulationInputError
from app.core.logging import get_logger

logger = get_logger("bionano.simulation.damage")

PROXY_TYPE = "SIDE_CHAIN_LOSS"
PROXY_VERSION = "2.0"

# Atoms kept when a side chain is removed: the backbone, plus CB, plus the
# C-terminal oxygen if this is the last residue. This is a truncation to alanine.
_BACKBONE_KEEP = {"N", "CA", "C", "O", "OXT", "CB"}

# How many side chains each severity level removes. Structural severity only:
# these numbers are NOT doses and do not map to any physical exposure.
SEVERITY_LEVELS: dict[str, int] = {
    "MILD": 1,
    "MODERATE": 3,
    "SEVERE": 6,
}

# Residues the proxy cannot be applied to, and why.
NO_SIDE_CHAIN = {
    "GLY": "glycine has no side chain beyond CB, so there is nothing to remove",
    "ALA": "alanine's side chain is already only CB, so removal would be a no-op",
}
EXCLUDED_TYPES = {
    "PRO": (
        "proline's side chain closes a ring onto the backbone nitrogen; truncating "
        "it changes backbone chemistry rather than only the side chain"
    ),
}


@dataclass(frozen=True)
class DamageTarget:
    """One residue selected for side-chain removal."""

    residue_seq: int
    residue_type: str | None = None
    residue_index_norm: float | None = None
    proxy_rank: int | None = None


@dataclass
class DamageManifest:
    """Everything needed to regenerate this exact damaged structure."""

    proxy_type: str = PROXY_TYPE
    proxy_version: str = PROXY_VERSION
    severity_label: str = "MILD"
    n_residues_damaged: int = 0
    damage_residue_id: str = ""          # primary (highest-ranked) target
    damage_residue_ids: list[str] = field(default_factory=list)
    chain_id: str = ""
    residue_type: str = ""               # primary target's type
    residue_type_after: str = "ALA"
    residue_index_norm: float | None = None
    proxy_rank: int | None = None
    targets: list[dict[str, Any]] = field(default_factory=list)
    atoms_removed: list[str] = field(default_factory=list)
    n_atoms_removed: int = 0
    n_atoms_before: int = 0
    n_atoms_after: int = 0
    source_structure_sha256: str = ""
    damaged_structure_sha256: str = ""
    rule: str = (
        "For each selected residue, delete every atom except N, CA, C, O, OXT and "
        "CB, then rename the residue to ALA. All other residues are byte-identical."
    )
    is_stochastic: bool = False
    severity_is_a_dose: bool = False
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _parse_atom_line(line: str) -> tuple[str, str, str, str]:
    """(atom_name, res_name, chain_id, res_seq) from a PDB ATOM/HETATM line."""
    return (
        line[12:16].strip(),
        line[17:20].strip(),
        line[21:22].strip(),
        line[22:26].strip(),
    )


def residue_types_in(source_pdb: Path, chain_id: str) -> dict[int, str]:
    """Map residue sequence number -> residue type for one chain.

    ATOM records only. HETATM covers waters, ions and ligands, which are not
    polymer residues and are never damage targets -- and in a deposited file they
    frequently reuse the same chain ID with their own numbering.
    """
    found: dict[int, str] = {}
    for line in source_pdb.read_text(encoding="utf-8").splitlines():
        if not line.startswith("ATOM"):
            continue
        _atom, res_name, chain, seq = _parse_atom_line(line)
        if chain == chain_id and seq.isdigit():
            found.setdefault(int(seq), res_name)
    return found


def damage_rejection_reason(
    residue_type: str,
    residue_seq: int,
    pull_atom_residue_seqs: tuple[int, ...] = (),
) -> str | None:
    """Why this residue cannot be damaged, or None if it can be."""
    if residue_type in NO_SIDE_CHAIN:
        return NO_SIDE_CHAIN[residue_type]
    if residue_type in EXCLUDED_TYPES:
        return EXCLUDED_TYPES[residue_type]
    if residue_seq in pull_atom_residue_seqs:
        return (
            "the residue carries a pulling attachment point, so damaging it would "
            "change the reaction coordinate itself rather than the molecule under load"
        )
    return None


def apply_side_chain_loss(
    source_pdb: Path,
    output_pdb: Path,
    *,
    chain_id: str,
    targets: list[DamageTarget],
    severity_label: str = "MILD",
    pull_atom_residue_seqs: tuple[int, ...] = (),
) -> DamageManifest:
    """Remove the side chains of every target residue. Returns the manifest.

    ``pull_atom_residue_seqs`` are residues the pulling protocol attaches to. A
    damaged residue must not be one of them: the anchor and pulled atoms define
    the reaction coordinate, so perturbing them would change what is being
    measured rather than what is being loaded.
    """
    if not targets:
        raise InvalidSimulationInputError(
            "No damage targets were supplied.", code="DAMAGE_NO_TARGETS"
        )

    present = residue_types_in(source_pdb, chain_id)
    resolved: list[DamageTarget] = []
    for target in targets:
        actual = present.get(target.residue_seq)
        if actual is None:
            raise InvalidSimulationInputError(
                f"Residue {chain_id}:{target.residue_seq} was not found in "
                f"{source_pdb.name}.",
                code="DAMAGE_RESIDUE_NOT_FOUND",
            )
        if target.residue_type and actual != target.residue_type:
            raise InvalidSimulationInputError(
                f"Residue {chain_id}:{target.residue_seq} is {actual}, but "
                f"{target.residue_type} was expected. Refusing to damage the wrong "
                "residue: the candidate table and the structure disagree.",
                code="DAMAGE_RESIDUE_TYPE_MISMATCH",
            )
        reason = damage_rejection_reason(actual, target.residue_seq, pull_atom_residue_seqs)
        if reason:
            raise InvalidSimulationInputError(
                f"{PROXY_TYPE} cannot be applied to {chain_id}:{target.residue_seq} "
                f"({actual}): {reason}.",
                code="DAMAGE_RESIDUE_NOT_ELIGIBLE",
            )
        resolved.append(
            DamageTarget(
                residue_seq=target.residue_seq,
                residue_type=actual,
                residue_index_norm=target.residue_index_norm,
                proxy_rank=target.proxy_rank,
            )
        )

    seqs = {t.residue_seq for t in resolved}
    if len(seqs) != len(resolved):
        raise InvalidSimulationInputError(
            "The same residue was listed twice as a damage target.",
            code="DAMAGE_DUPLICATE_TARGET",
        )

    lines = source_pdb.read_text(encoding="utf-8").splitlines(keepends=True)
    kept: list[str] = []
    removed_by_residue: dict[int, list[str]] = {s: [] for s in seqs}
    n_before = 0
    for line in lines:
        if not line.startswith(("ATOM", "HETATM")):
            kept.append(line)
            continue
        n_before += 1
        atom, _res_name, chain, seq = _parse_atom_line(line)
        # HETATM is never a target: a water numbered 74 in chain A must not be
        # truncated because residue 74 of the polymer was selected.
        is_target = (
            line.startswith("ATOM")
            and chain == chain_id
            and seq.isdigit()
            and int(seq) in seqs
        )
        if not is_target:
            kept.append(line)
            continue
        if atom not in _BACKBONE_KEEP:
            removed_by_residue[int(seq)].append(atom)
            continue
        # Rename the residue in place so the force field builds an alanine.
        kept.append(line[:17] + "ALA" + line[20:])

    empty = [s for s, atoms in removed_by_residue.items() if not atoms]
    if empty:
        raise InvalidSimulationInputError(
            f"No side-chain atoms were found on {chain_id}:{empty[0]}; the structure "
            "may already be truncated.",
            code="DAMAGE_NO_ATOMS_REMOVED",
        )

    output_pdb.parent.mkdir(parents=True, exist_ok=True)
    output_pdb.write_text("".join(kept), encoding="utf-8")

    all_removed = sorted(a for atoms in removed_by_residue.values() for a in atoms)
    primary = min(
        resolved,
        key=lambda t: (t.proxy_rank if t.proxy_rank is not None else 10**6, t.residue_seq),
    )
    target_rows = [
        {
            "residue_id": f"{chain_id}:{t.residue_seq}",
            "residue_seq": t.residue_seq,
            "residue_type": t.residue_type,
            "residue_index_norm": t.residue_index_norm,
            "proxy_rank": t.proxy_rank,
            "atoms_removed": sorted(removed_by_residue[t.residue_seq]),
            "n_atoms_removed": len(removed_by_residue[t.residue_seq]),
        }
        for t in sorted(resolved, key=lambda t: t.residue_seq)
    ]

    manifest = DamageManifest(
        severity_label=severity_label,
        n_residues_damaged=len(resolved),
        damage_residue_id=f"{chain_id}:{primary.residue_seq}",
        damage_residue_ids=[r["residue_id"] for r in target_rows],
        chain_id=chain_id,
        residue_type=primary.residue_type or "",
        residue_index_norm=primary.residue_index_norm,
        proxy_rank=primary.proxy_rank,
        targets=target_rows,
        atoms_removed=all_removed,
        n_atoms_removed=len(all_removed),
        n_atoms_before=n_before,
        n_atoms_after=n_before - len(all_removed),
        source_structure_sha256=sha256_file(source_pdb),
        damaged_structure_sha256=sha256_file(output_pdb),
        notes=[
            f"Severity {severity_label}: {len(resolved)} residue(s) truncated to ALA, "
            f"removing {len(all_removed)} side-chain atoms in total.",
            "Severity is a count of removed side chains. It is NOT a dose, and it "
            "does not correspond to any Gy, LET or fluence value.",
            "This is a controlled structural perturbation, not radiation chemistry.",
            "The perturbation itself is deterministic. The random seed recorded for "
            "an experiment governs the molecular dynamics, not the damage.",
        ],
    )
    logger.info(
        "damage: %s, %d residues -> ALA, removed %d atoms",
        severity_label, len(resolved), len(all_removed),
    )
    return manifest
