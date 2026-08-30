"""Structure preparation for OpenMM.

Turns an arbitrary deposited PDB into something ``ForceField.createSystem`` will
accept: one chain, one model, standard residues only, no waters or ligands, and
hydrogens added by OpenMM's own ``Modeller`` so they match the force field's
expectations rather than whatever the depositor used.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from app.core.exceptions import InvalidSimulationInputError
from app.core.logging import get_logger

logger = get_logger("bionano.simulation.preparation")

# Residues OpenMM's amber14 templates will not match, dropped before system build.
_DROP_RESIDUES = {"HOH", "WAT", "SO4", "PO4", "GOL", "EDO", "DOD", "MOH", "PEG"}

_STANDARD_AA = {
    "ALA", "ARG", "ASN", "ASP", "CYS", "GLN", "GLU", "GLY", "HIS", "ILE",
    "LEU", "LYS", "MET", "PHE", "PRO", "SER", "THR", "TRP", "TYR", "VAL",
}


@dataclass
class PreparedStructure:
    path: Path
    chain_id: str
    n_residues: int
    n_atoms_heavy: int
    residue_ids: list[str] = field(default_factory=list)
    residue_types: list[str] = field(default_factory=list)
    ca_indices: list[int] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def extract_chain(
    source: Path, destination: Path, chain_id: str
) -> PreparedStructure:
    """Write a single-chain, single-model, protein-only PDB.

    Also records the residue ids/types in file order so downstream RMSF values
    can be attributed to the right residues.
    """
    from Bio.PDB import PDBIO, PDBParser, Select

    structure = PDBParser(QUIET=True).get_structure("input", str(source))
    models = list(structure)
    if not models:
        raise InvalidSimulationInputError(
            "Structure contains no models.", code="STRUCTURE_EMPTY"
        )
    model = models[0]

    if chain_id not in [c.id for c in model]:
        raise InvalidSimulationInputError(
            f"Chain '{chain_id}' not found in the structure.", code="CHAIN_NOT_FOUND"
        )

    notes: list[str] = []
    if len(models) > 1:
        notes.append(f"Used model 1 of {len(models)}.")

    dropped: set[str] = set()
    kept_residues = []
    for res in model[chain_id]:
        name = res.get_resname().strip().upper()
        if res.id[0] != " ":
            if name not in _DROP_RESIDUES:
                dropped.add(name)
            continue
        if name not in _STANDARD_AA:
            dropped.add(name)
            continue
        if not res.has_id("CA"):
            # Incomplete residues break force-field templates. This is the same
            # rule that reconciles 1TEN's 90 parsed residues with the reference
            # table's 89 (A:802 carries only C and O).
            notes.append(f"Dropped {name} {res.id[1]}: no Cα atom.")
            continue
        kept_residues.append(res)

    if dropped:
        notes.append(
            "Dropped non-standard residues/heteroatoms: "
            f"{', '.join(sorted(dropped)[:10])}."
        )
    if not kept_residues:
        raise InvalidSimulationInputError(
            f"Chain '{chain_id}' has no standard amino-acid residues to simulate.",
            code="NO_SIMULATABLE_RESIDUES",
        )

    keep = {(chain_id, r.id) for r in kept_residues}

    class _ChainSelect(Select):
        def accept_model(self, m: Any) -> bool:  # noqa: N803
            return m.id == model.id

        def accept_chain(self, c: Any) -> bool:
            return c.id == chain_id

        def accept_residue(self, r: Any) -> bool:
            return (chain_id, r.id) in keep

        def accept_atom(self, atom: Any) -> bool:
            # Drop altloc duplicates and hydrogens; OpenMM re-adds H itself.
            if atom.element == "H" or atom.get_name().startswith("H"):
                return False
            return atom.get_altloc() in (" ", "A")

    destination.parent.mkdir(parents=True, exist_ok=True)
    io = PDBIO()
    io.set_structure(structure)
    io.save(str(destination), _ChainSelect())

    n_heavy = sum(
        1
        for r in kept_residues
        for a in r
        if not (a.element == "H" or a.get_name().startswith("H"))
        and a.get_altloc() in (" ", "A")
    )

    return PreparedStructure(
        path=destination,
        chain_id=chain_id,
        n_residues=len(kept_residues),
        n_atoms_heavy=n_heavy,
        residue_ids=[f"{chain_id}:{r.id[1]}" for r in kept_residues],
        residue_types=[r.get_resname().strip().upper() for r in kept_residues],
        notes=notes,
    )


def select_platform(
    preferred: str, *, deterministic: bool = False
) -> tuple[Any, dict[str, str], str]:
    """Pick an OpenMM platform. Returns (platform, properties, note).

    ``preferred='auto'`` walks a speed-ordered preference list. On this class of
    machine GBn2 implicit solvent runs ~350 steps/s on OpenCL versus ~70 steps/s
    on a 16-thread CPU, so auto-selection is the difference between a 17 s and an
    85 s demo. An explicit platform name is always honoured.

    Trade-off worth knowing: the CPU platform is bit-reproducible for a fixed
    seed *only when it runs on a single thread*. With more than one thread the
    force reductions are summed in a nondeterministic order, and two runs of an
    identical configuration diverge measurably — around 0.03 nm of atomic
    displacement after a few hundred steps on a 16-thread machine. GPU platforms
    are likewise not bit-reproducible.

    ``deterministic=True`` therefore pins the run to a single-threaded CPU, which
    is the only configuration that repeats exactly. It is much slower, so it is
    opt-in rather than the default. The platform and thread count actually used
    are recorded in the job's reproducibility block either way.
    """
    import os

    from openmm import Platform

    available = {
        Platform.getPlatform(i).getName() for i in range(Platform.getNumPlatforms())
    }

    def _props(name: str) -> dict[str, str]:
        if name == "CPU":
            # Be explicit so the value lands in the reproducibility record. One
            # thread is the only bit-reproducible setting; the default is one
            # thread per physical core, for speed.
            threads = 1 if deterministic else (os.cpu_count() or 1)
            return {"Threads": str(threads)}
        return {}

    if deterministic:
        if "CPU" not in available:
            raise InvalidSimulationInputError(
                "Deterministic runs require the CPU platform, which is not "
                f"available. Available: {', '.join(sorted(available))}.",
                code="PLATFORM_UNAVAILABLE",
            )
        if preferred not in ("auto", "CPU"):
            raise InvalidSimulationInputError(
                f"Deterministic runs require the CPU platform, but '{preferred}' "
                "was requested. Use platform 'CPU' or 'auto'.",
                code="PLATFORM_NOT_DETERMINISTIC",
            )
        return (
            Platform.getPlatformByName("CPU"),
            _props("CPU"),
            "Deterministic mode: CPU platform pinned to a single thread. This is "
            "the only configuration that reproduces a trajectory exactly for a "
            "fixed seed, and it is several times slower than the default.",
        )

    if preferred != "auto":
        if preferred not in available:
            raise InvalidSimulationInputError(
                f"Requested platform '{preferred}' is not available. Available: "
                f"{', '.join(sorted(available))}.",
                code="PLATFORM_UNAVAILABLE",
            )
        return (
            Platform.getPlatformByName(preferred),
            _props(preferred),
            f"Using explicitly requested platform '{preferred}'.",
        )

    for candidate in ("CUDA", "HIP", "OpenCL", "CPU", "Reference"):
        if candidate not in available:
            continue
        try:
            platform = Platform.getPlatformByName(candidate)
        except Exception:  # noqa: BLE001
            continue
        note = (
            f"Auto-selected platform '{candidate}' from available: "
            f"{', '.join(sorted(available))}."
        )
        if candidate not in ("CPU", "Reference"):
            note += (
                " GPU platforms are faster but not bit-reproducible. Neither is a "
                "multi-threaded CPU run: use a preset with deterministic=True for "
                "an exactly repeatable trajectory."
            )
        return platform, _props(candidate), note

    raise InvalidSimulationInputError(
        "No usable OpenMM platform was found.", code="PLATFORM_UNAVAILABLE"
    )


def build_openmm_system(
    prepared: PreparedStructure, preset: Any, temperature_kelvin: float, seed: int
) -> tuple[Any, Any, list[str]]:
    """Build (simulation, topology_info, notes) for a prepared structure.

    Uses amber14 with GBn2 implicit solvent and a 1.2 nm nonbonded cutoff — no
    periodic box, no explicit water, which is what makes a laptop-scale run
    possible at all. The cutoff is standard practice for implicit solvent and is
    an ~8x speedup over the uncut O(N²) Born-radius calculation; it is declared
    in the preset and echoed in every result payload.
    """
    from openmm import LangevinMiddleIntegrator, Platform
    from openmm.app import (
        CutoffNonPeriodic,
        ForceField,
        HBonds,
        Modeller,
        PDBFile,
        Simulation,
    )
    from openmm.unit import femtoseconds, kelvin, nanometer, picosecond

    notes: list[str] = []
    pdb = PDBFile(str(prepared.path))
    forcefield = ForceField(*preset.forcefield)

    modeller = Modeller(pdb.topology, pdb.positions)

    # addHydrogens is not deterministic by default, and the difference is not
    # small: where a hydrogen's position is ambiguous (rotatable OH, SH, NH3+)
    # Modeller chooses using the global RNG, then refines the choice with a short
    # minimisation on a platform of its own choosing. Two preparations of the
    # same PDB were measured 0.18 nm apart before a single dynamics step -- far
    # larger than anything the trajectory subsequently does, so it dominates any
    # attempt at reproducibility. Seeding the RNG and pinning that refinement to
    # the single-threaded Reference platform makes preparation bit-identical.
    deterministic = bool(getattr(preset, "deterministic", False))
    hydrogen_kwargs: dict[str, Any] = {}
    rng_state = random.getstate()
    numpy_state = np.random.get_state()
    if deterministic:
        random.seed(seed)
        np.random.seed(int(seed) % (2**32))
        hydrogen_kwargs["platform"] = Platform.getPlatformByName("Reference")

    try:
        added = modeller.addHydrogens(forcefield, **hydrogen_kwargs)
        if added:
            notes.append(f"Added {len(added)} hydrogen atoms using the force field.")
        if deterministic:
            notes.append(
                "Deterministic mode: hydrogen placement was seeded and pinned to the "
                "Reference platform, so preparation repeats exactly."
            )
    except Exception as exc:  # noqa: BLE001
        raise InvalidSimulationInputError(
            "OpenMM could not add hydrogens to this structure, which usually means a "
            f"residue does not match an amber14 template: {type(exc).__name__}: {exc}",
            code="HYDROGEN_ADDITION_FAILED",
        ) from exc
    finally:
        # Never leave the process-wide RNGs reseeded behind us.
        random.setstate(rng_state)
        np.random.set_state(numpy_state)

    try:
        system = forcefield.createSystem(
            modeller.topology,
            constraints=HBonds if preset.constraints == "HBonds" else None,
            rigidWater=True,
            removeCMMotion=True,
            nonbondedMethod=CutoffNonPeriodic,
            nonbondedCutoff=preset.nonbonded_cutoff_nm * nanometer,
        )
    except Exception as exc:  # noqa: BLE001
        raise InvalidSimulationInputError(
            "OpenMM could not build a system from this structure: "
            f"{type(exc).__name__}: {exc}. This normally indicates a missing atom or "
            "an unsupported residue. Try the Minimisation-only preset, or a different "
            "chain.",
            code="SYSTEM_CONSTRUCTION_FAILED",
        ) from exc

    integrator = LangevinMiddleIntegrator(
        temperature_kelvin * kelvin,
        preset.friction_per_ps / picosecond,
        preset.timestep_fs * femtoseconds,
    )
    # Fixed seed: on the CPU platform, two runs with the same seed and preset
    # produce the same trajectory.
    integrator.setRandomNumberSeed(int(seed))

    platform, properties, platform_note = select_platform(
        preset.platform, deterministic=getattr(preset, "deterministic", False)
    )
    notes.append(platform_note)
    try:
        simulation = Simulation(
            modeller.topology, system, integrator, platform, properties
        )
    except Exception as exc:  # noqa: BLE001
        notes.append(
            f"Could not initialise platform '{platform.getName()}' ({exc}); falling "
            "back to OpenMM's default platform."
        )
        simulation = Simulation(modeller.topology, system, integrator)

    simulation.context.setPositions(modeller.positions)

    # The trajectory contains the hydrogens Modeller just added, so prepared.pdb
    # (heavy atoms only) is NOT a valid topology for it. Write the real simulated
    # topology for MDTraj and for any external analysis.
    topology_path = prepared.path.parent / "topology.pdb"
    with topology_path.open("w", encoding="utf-8") as fh:
        PDBFile.writeFile(modeller.topology, modeller.positions, fh)

    topology_info = {
        "n_atoms": modeller.topology.getNumAtoms(),
        "n_residues": modeller.topology.getNumResidues(),
        "n_constraints": system.getNumConstraints(),
        "platform": simulation.context.getPlatform().getName(),
        "platform_properties": properties,
        # True only for a single-threaded CPU run: see select_platform.
        "bit_reproducible": (
            simulation.context.getPlatform().getName() == "CPU"
            and properties.get("Threads") == "1"
        ),
        "nonbonded_cutoff_nm": preset.nonbonded_cutoff_nm,
        "topology_file": topology_path.name,
        "forcefield": list(preset.forcefield),
        "ca_indices": [
            atom.index
            for atom in modeller.topology.atoms()
            if atom.name == "CA" and atom.residue.name in _STANDARD_AA
        ],
        "residue_ids": [
            f"{r.chain.id}:{r.id}" for r in modeller.topology.residues()
        ],
        "residue_types": [r.name for r in modeller.topology.residues()],
    }
    return simulation, topology_info, notes
