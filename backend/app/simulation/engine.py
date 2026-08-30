"""The OpenMM simulation engine.

Progress reported to the frontend comes from the integrator's own step counter,
not from a timer. The production loop advances in chunks and publishes
``steps_completed`` after each chunk, so a stalled or slow run shows a stalled
progress bar — which is the honest behaviour.

The trajectory is read back with MDTraj when available, and otherwise with a
small self-contained DCD reader, so every chart the dashboard shows is derived
from real coordinates either way.
"""

from __future__ import annotations

import struct
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from app.analysis import degradation as degradation_analysis
from app.analysis.energy import parse_state_csv
from app.analysis.radius_gyration import rg_series
from app.analysis.rmsd import rmsd_series
from app.analysis.rmsf import rmsf_per_atom
from app.core.logging import get_logger
from app.schemas.simulation import JobStage
from app.simulation.preparation import build_openmm_system, extract_chain
from app.simulation.pulling import (
    CSV_HEADER as PULL_CSV_HEADER,
)
from app.simulation.pulling import (
    PullCancelledError,
    PullResult,
    run_steered_pull,
)
from app.utils.files import write_csv

logger = get_logger("bionano.simulation.engine")

# Steps per publish. Small enough that the UI updates ~10x/s at demo scale,
# large enough that context switching does not dominate runtime.
PRODUCTION_CHUNK = 250


@dataclass
class EngineResult:
    metrics: dict[str, Any] = field(default_factory=dict)
    series: dict[str, list[dict[str, float]]] = field(default_factory=dict)
    rmsf: list[dict[str, Any]] = field(default_factory=list)
    highest_mobility_residues: list[dict[str, Any]] = field(default_factory=list)
    stability_summary: dict[str, Any] = field(default_factory=dict)
    degradation_proxy: dict[str, Any] = field(default_factory=dict)
    topology: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Minimal DCD reader (fallback when MDTraj is unavailable)
# --------------------------------------------------------------------------- #
def read_dcd(path: Path) -> np.ndarray:
    """Read a CHARMM/OpenMM DCD file into an (n_frames, n_atoms, 3) array in nm.

    Deliberately minimal: handles the fixed-format 32-bit little-endian DCD that
    OpenMM's DCDReporter writes. Coordinates are converted from ångström to nm to
    match MDTraj's convention so both paths produce identical downstream numbers.
    """
    data = path.read_bytes()
    if len(data) < 100:
        raise ValueError("DCD file is too short to contain a header.")

    # Header block 1: 84-byte record, 'CORD' magic at offset 4.
    if data[4:8] != b"CORD":
        raise ValueError("Not a DCD file (missing CORD magic).")
    n_frames_header = struct.unpack_from("<i", data, 8)[0]
    n_fixed = struct.unpack_from("<i", data, 8 + 8 * 4)[0]
    unit_cell = struct.unpack_from("<i", data, 8 + 10 * 4)[0]

    offset = 4 + 84 + 4  # leading size + block + trailing size

    # Title block: length-prefixed record.
    title_len = struct.unpack_from("<i", data, offset)[0]
    offset += 4 + title_len + 4

    # Natoms block.
    natom_len = struct.unpack_from("<i", data, offset)[0]
    if natom_len != 4:
        raise ValueError(f"Unexpected natoms record length {natom_len}.")
    n_atoms = struct.unpack_from("<i", data, offset + 4)[0]
    offset += 4 + 4 + 4

    if n_fixed != 0:
        raise ValueError("DCD files with fixed atoms are not supported.")

    frames: list[np.ndarray] = []
    coord_bytes = n_atoms * 4
    while offset < len(data):
        if unit_cell:
            if offset + 4 > len(data):
                break
            cell_len = struct.unpack_from("<i", data, offset)[0]
            offset += 4 + cell_len + 4
        xyz = np.empty((3, n_atoms), dtype=np.float32)
        ok = True
        for axis in range(3):
            if offset + 4 > len(data):
                ok = False
                break
            block_len = struct.unpack_from("<i", data, offset)[0]
            if block_len != coord_bytes or offset + 8 + block_len > len(data):
                ok = False
                break
            xyz[axis] = np.frombuffer(
                data, dtype="<f4", count=n_atoms, offset=offset + 4
            )
            offset += 4 + block_len + 4
        if not ok:
            break
        frames.append(xyz.T.copy())

    if not frames:
        raise ValueError("DCD file contained no readable frames.")
    if n_frames_header and len(frames) != n_frames_header:
        logger.debug(
            "DCD header claims %d frames, read %d.", n_frames_header, len(frames)
        )
    return np.stack(frames) / 10.0  # Å -> nm


def load_trajectory(
    dcd_path: Path, topology_path: Path
) -> tuple[np.ndarray, str]:
    """Load a trajectory as (n_frames, n_atoms, 3) nm. Returns (array, reader_name)."""
    try:
        import mdtraj

        traj = mdtraj.load_dcd(str(dcd_path), top=str(topology_path))
        return np.asarray(traj.xyz, dtype=float), f"mdtraj {mdtraj.__version__}"
    except Exception as exc:  # noqa: BLE001
        logger.info("MDTraj unavailable or failed (%s); using built-in DCD reader.", exc)
        return read_dcd(dcd_path), "bionano-builtin-dcd"


# --------------------------------------------------------------------------- #
# Main entry point
# --------------------------------------------------------------------------- #
def run_simulation(
    *,
    source_pdb: Path,
    job_dir: Path,
    chain_id: str,
    preset: Any,
    temperature_kelvin: float,
    seed: int,
    report: Callable[[JobStage, str, dict[str, Any] | None], None],
    should_cancel: Callable[[], bool],
    log: Callable[[str], None],
) -> EngineResult:
    """Run the full pipeline. ``report`` publishes stage/progress; ``log`` appends
    to ``simulation.log``. Raises on failure — the caller marks the job failed.
    """
    from openmm.app import DCDReporter, PDBFile, StateDataReporter
    from openmm.unit import kelvin, kilojoule_per_mole

    analysis_dir = job_dir / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    notes: list[str] = []

    # --- Stage 2: preparation -------------------------------------------
    report(JobStage.PROTEIN_PREPARATION, "Extracting chain and cleaning residues", None)
    prepared = extract_chain(source_pdb, job_dir / "prepared.pdb", chain_id)
    notes.extend(prepared.notes)
    for note in prepared.notes:
        log(f"prepare: {note}")
    log(
        f"prepare: chain {chain_id}, {prepared.n_residues} residues, "
        f"{prepared.n_atoms_heavy} heavy atoms"
    )
    if should_cancel():
        raise _CancelledError()

    # --- Stage 3: system construction -----------------------------------
    report(JobStage.SYSTEM_CONSTRUCTION, "Building force field and integrator", None)
    simulation, topology, build_notes = build_openmm_system(
        prepared, preset, temperature_kelvin, seed
    )
    notes.extend(build_notes)
    for note in build_notes:
        log(f"system: {note}")
    log(
        f"system: {topology['n_atoms']} atoms, {topology['n_residues']} residues, "
        f"{topology['n_constraints']} constraints, platform {topology['platform']}"
    )
    log(f"system: forcefield {', '.join(topology['forcefield'])}, seed {seed}")
    if should_cancel():
        raise _CancelledError()

    def _potential_kj() -> float:
        state = simulation.context.getState(getEnergy=True)
        return float(state.getPotentialEnergy().value_in_unit(kilojoule_per_mole))

    # --- Stage 4: minimisation ------------------------------------------
    report(JobStage.ENERGY_MINIMIZATION, "Minimising energy", None)
    e_before = _potential_kj()
    log(f"minimise: initial potential energy {e_before:.2f} kJ/mol")
    simulation.minimizeEnergy(maxIterations=preset.minimisation_steps)
    e_after = _potential_kj()
    log(
        f"minimise: final potential energy {e_after:.2f} kJ/mol "
        f"(Δ {e_after - e_before:+.2f})"
    )
    report(
        JobStage.ENERGY_MINIMIZATION,
        "Minimisation complete",
        {"potential_energy_kj_mol": e_after},
    )
    if should_cancel():
        raise _CancelledError()

    total_dynamics = preset.equilibration_steps + preset.production_steps

    if total_dynamics == 0:
        # Minimisation-only preset: honest early exit, no fabricated trajectory.
        report(JobStage.EQUILIBRATION, "Skipped (minimisation-only preset)", None)
        report(JobStage.PRODUCTION, "Skipped (minimisation-only preset)", None)
        with (job_dir / "final.pdb").open("w", encoding="utf-8") as fh:
            PDBFile.writeFile(
                simulation.topology,
                simulation.context.getState(getPositions=True).getPositions(),
                fh,
            )
        report(JobStage.TRAJECTORY_ANALYSIS, "No trajectory to analyse", None)
        result = EngineResult(
            metrics={
                "preset_id": preset.preset_id,
                "engine": "openmm",
                "result_label": preset.scientific_label,
                "minimisation": {
                    "potential_energy_before_kj_mol": round(e_before, 4),
                    "potential_energy_after_kj_mol": round(e_after, 4),
                    "delta_kj_mol": round(e_after - e_before, 4),
                    "max_iterations": preset.minimisation_steps,
                },
                "dynamics_run": False,
                "n_frames": 0,
                "simulated_time_ps": 0.0,
            },
            topology=topology,
            notes=[
                *notes,
                "Minimisation-only preset: no dynamics were run, so RMSD, RMSF, Rg "
                "and the degradation proxy are unavailable rather than estimated.",
            ],
        )
        return result

    # --- Reporters -------------------------------------------------------
    dcd_path = job_dir / "trajectory.dcd"
    state_path = job_dir / "state.csv"
    simulation.reporters.append(
        DCDReporter(str(dcd_path), preset.report_interval)
    )
    simulation.reporters.append(
        StateDataReporter(
            str(state_path),
            preset.report_interval,
            step=True,
            time=True,
            potentialEnergy=True,
            kineticEnergy=True,
            totalEnergy=True,
            temperature=True,
            speed=False,
            separator=",",
        )
    )

    # --- Stage 5: equilibration -----------------------------------------
    report(JobStage.EQUILIBRATION, "Assigning velocities and equilibrating", None)
    simulation.context.setVelocitiesToTemperature(temperature_kelvin * kelvin, int(seed))
    log(
        f"equilibrate: {preset.equilibration_steps} steps at {temperature_kelvin} K, "
        f"timestep {preset.timestep_fs} fs"
    )
    steps_done = 0
    steps_done = _advance(
        simulation, preset.equilibration_steps, steps_done, total_dynamics,
        JobStage.EQUILIBRATION, report, should_cancel, log, simulation_kelvin=kelvin,
    )

    # The post-equilibration, pre-production conformation. A paired experiment
    # can start both of its runs from this one structure, which removes the
    # single largest nuisance term in a baseline-vs-damaged comparison: two
    # independent equilibration trajectories drifting to different microstates.
    with (job_dir / "equilibrated.pdb").open("w", encoding="utf-8") as fh:
        PDBFile.writeFile(
            simulation.topology,
            simulation.context.getState(getPositions=True).getPositions(),
            fh,
        )
    log("equilibrate: wrote equilibrated.pdb")

    # --- Stage 6: production --------------------------------------------
    # A pulling preset replaces free production dynamics with a steered-MD
    # pull. Everything downstream (trajectory, analysis, proxy) is unchanged,
    # because the pull writes the same DCD through the same reporters.
    pull_config = getattr(preset, "pulling", None)
    pull_result: PullResult | None = None
    if pull_config is not None:
        report(JobStage.PRODUCTION, "Running steered-MD pull", None)
        log(f"production: steered-MD pull, {preset.production_steps} steps")
        try:
            steps_done, pull_result = run_steered_pull(
                simulation=simulation,
                config=pull_config,
                n_steps=preset.production_steps,
                steps_done=steps_done,
                total_dynamics=total_dynamics,
                timestep_fs=preset.timestep_fs,
                report=report,
                should_cancel=should_cancel,
                log=log,
            )
        except PullCancelledError as exc:
            raise _CancelledError() from exc
        notes.extend(pull_result.notes)
    else:
        report(JobStage.PRODUCTION, "Running production dynamics", None)
        log(f"production: {preset.production_steps} steps")
        steps_done = _advance(
            simulation, preset.production_steps, steps_done, total_dynamics,
            JobStage.PRODUCTION, report, should_cancel, log,
            simulation_kelvin=kelvin,
        )

    # Flush reporters so the DCD is complete before we read it.
    for reporter in list(simulation.reporters):
        close = getattr(reporter, "close", None)
        if callable(close):
            close()
    simulation.reporters.clear()

    final_state = simulation.context.getState(getPositions=True, getEnergy=True)
    with (job_dir / "final.pdb").open("w", encoding="utf-8") as fh:
        PDBFile.writeFile(simulation.topology, final_state.getPositions(), fh)
    log("production: wrote final.pdb")

    # --- Stage 7: trajectory analysis -----------------------------------
    report(JobStage.TRAJECTORY_ANALYSIS, "Computing RMSD, RMSF, Rg and energies", None)
    result = _analyse(
        job_dir=job_dir,
        analysis_dir=analysis_dir,
        dcd_path=dcd_path,
        state_path=state_path,
        # topology.pdb (written after hydrogens are added) is the real topology
        # of the trajectory; prepared.pdb is heavy-atom only and would mismatch.
        topology_pdb=job_dir / "topology.pdb",
        topology=topology,
        preset=preset,
        temperature_kelvin=temperature_kelvin,
        minimisation=(e_before, e_after),
        total_dynamics_steps=total_dynamics,
        log=log,
    )
    # --- Force-extension export (task 5) ---------------------------------
    if pull_result is not None:
        fe_path = analysis_dir / "force_extension.csv"
        write_csv(
            fe_path,
            PULL_CSV_HEADER,
            [[s[col] for col in PULL_CSV_HEADER] for s in pull_result.samples],
        )
        log(
            f"analysis: wrote force_extension.csv "
            f"({len(pull_result.samples)} samples)"
        )
        result.series["force_extension"] = pull_result.samples
        result.metrics["pulling"] = {
            **pull_result.summary,
            # Everything needed to reproduce this pull exactly (task 6).
            # bit_reproducible is false unless the run was pinned to a
            # single-threaded CPU, so nobody reads repeatability into a
            # trajectory that cannot deliver it.
            "config": {
                **pull_result.config,
                "preset_id": preset.preset_id,
                "seed": seed,
                "temperature_kelvin": temperature_kelvin,
                "platform": topology["platform"],
                "platform_properties": topology["platform_properties"],
                "bit_reproducible": topology.get("bit_reproducible", False),
            },
            "force_extension_csv": "analysis/force_extension.csv",
            "units": {
                "force": "pN",
                "extension": "nm",
                "work": "kJ/mol",
                "stiffness": "pN/nm",
            },
        }

    result.notes = [*notes, *result.notes]
    return result


class _CancelledError(Exception):
    """Raised internally when a cancel request is observed mid-run."""


def _advance(
    simulation: Any,
    n_steps: int,
    steps_done: int,
    total: int,
    stage: JobStage,
    report: Callable[[JobStage, str, dict[str, Any] | None], None],
    should_cancel: Callable[[], bool],
    log: Callable[[str], None],
    *,
    simulation_kelvin: Any,
) -> int:
    """Step in chunks, publishing real integrator progress after each chunk."""
    from openmm.unit import kilojoule_per_mole

    remaining = n_steps
    while remaining > 0:
        if should_cancel():
            log(f"{stage.value}: cancellation observed at step {steps_done}")
            raise _CancelledError()
        chunk = min(PRODUCTION_CHUNK, remaining)
        simulation.step(chunk)
        remaining -= chunk
        steps_done += chunk

        state = simulation.context.getState(getEnergy=True)
        pe = float(state.getPotentialEnergy().value_in_unit(kilojoule_per_mole))
        ke = float(state.getKineticEnergy().value_in_unit(kilojoule_per_mole))
        # Instantaneous temperature from kinetic energy: T = 2*KE / (dof * kB).
        dof = max(
            1,
            3 * simulation.topology.getNumAtoms()
            - simulation.system.getNumConstraints()
            - 3,
        )
        temp = 2.0 * ke / (dof * 0.00831446261815324)  # kJ/mol/K

        report(
            stage,
            f"{stage.value} step {steps_done}/{total}",
            {
                "steps_completed": steps_done,
                "steps_total": total,
                "potential_energy_kj_mol": round(pe, 4),
                "temperature_kelvin": round(temp, 3),
            },
        )
    return steps_done


def _analyse(
    *,
    job_dir: Path,
    analysis_dir: Path,
    dcd_path: Path,
    state_path: Path,
    topology_pdb: Path,
    topology: dict[str, Any],
    preset: Any,
    temperature_kelvin: float,
    minimisation: tuple[float, float],
    total_dynamics_steps: int,
    log: Callable[[str], None],
) -> EngineResult:
    """Derive every reported metric from the real trajectory."""
    notes: list[str] = []

    frames, reader = load_trajectory(dcd_path, topology_pdb)
    log(f"analysis: loaded {frames.shape[0]} frames x {frames.shape[1]} atoms via {reader}")
    notes.append(f"Trajectory read with {reader}.")

    ca_idx = np.array(
        [i for i in topology.get("ca_indices", []) if i < frames.shape[1]], dtype=int
    )
    if ca_idx.size == 0:
        notes.append(
            "No Cα atoms were identified in the topology; metrics fall back to all atoms."
        )
        ca_frames = frames
    else:
        ca_frames = frames[:, ca_idx, :]

    # --- time axis -------------------------------------------------------
    ps_per_frame = preset.report_interval * preset.timestep_fs / 1000.0
    times = np.arange(frames.shape[0], dtype=float) * ps_per_frame

    # --- RMSD (Cα, vs first frame) --------------------------------------
    rmsd = rmsd_series(ca_frames)
    # --- Rg (Cα, unweighted) --------------------------------------------
    rg = rg_series(ca_frames)
    # --- RMSF per Cα -----------------------------------------------------
    rmsf = rmsf_per_atom(ca_frames)

    # --- energies from the reporter CSV ---------------------------------
    state = parse_state_csv(state_path)
    energy_time = state.get("time_ps") or list(times)
    potential = state.get("potential_energy") or []
    kinetic = state.get("kinetic_energy") or []
    total_energy = state.get("total_energy") or []
    temps = state.get("temperature") or []

    # --- residue attribution --------------------------------------------
    residue_ids = list(topology.get("residue_ids", []))
    residue_types = list(topology.get("residue_types", []))
    n = min(len(residue_ids), len(residue_types), rmsf.size)
    rmsf_rows = [
        {
            "residue_index": i + 1,
            "residue_id": residue_ids[i],
            "residue_type": residue_types[i],
            "rmsf_nm": round(float(rmsf[i]), 6),
        }
        for i in range(n)
    ]

    # --- persist CSVs ----------------------------------------------------
    write_csv(
        analysis_dir / "rmsd.csv",
        ["frame", "time_ps", "rmsd_nm"],
        [[i, round(float(times[i]), 6), round(float(rmsd[i]), 6)] for i in range(rmsd.size)],
    )
    write_csv(
        analysis_dir / "rmsf.csv",
        ["residue_index", "residue_id", "residue_type", "rmsf_nm"],
        [[r["residue_index"], r["residue_id"], r["residue_type"], r["rmsf_nm"]] for r in rmsf_rows],
    )
    write_csv(
        analysis_dir / "radius_gyration.csv",
        ["frame", "time_ps", "radius_of_gyration_nm"],
        [[i, round(float(times[i]), 6), round(float(rg[i]), 6)] for i in range(rg.size)],
    )
    energy_rows = []
    for i in range(len(potential)):
        energy_rows.append(
            [
                round(float(energy_time[i]), 6) if i < len(energy_time) else None,
                round(float(potential[i]), 6),
                round(float(kinetic[i]), 6) if i < len(kinetic) else None,
                round(float(total_energy[i]), 6) if i < len(total_energy) else None,
                round(float(temps[i]), 6) if i < len(temps) else None,
            ]
        )
    write_csv(
        analysis_dir / "energy.csv",
        ["time_ps", "potential_energy_kj_mol", "kinetic_energy_kj_mol",
         "total_energy_kj_mol", "temperature_kelvin"],
        energy_rows,
    )
    log(f"analysis: wrote 4 CSVs to {analysis_dir.name}/")

    # --- degradation proxy ----------------------------------------------
    proxy = degradation_analysis.compute_degradation_proxy(
        final_rmsd_nm=float(rmsd[-1]) if rmsd.size else None,
        rg_initial_nm=float(rg[0]) if rg.size else None,
        rg_final_nm=float(rg[-1]) if rg.size else None,
        mean_rmsf_nm=float(rmsf.mean()) if rmsf.size else None,
    )
    log(f"analysis: degradation proxy {proxy.percent:.2f}%")

    stability = degradation_analysis.stability_summary(
        rmsd_series=rmsd, rg_series=rg, rmsf_values=rmsf, temperature_series=temps
    )
    top_mobility = degradation_analysis.highest_mobility_residues(
        residue_ids, residue_types, rmsf, top_n=10
    )

    def _series(xs: Any, ys: Any) -> list[dict[str, float]]:
        # strict=False is deliberate: the StateDataReporter CSV and the DCD are
        # written by independent reporters and can differ by a sample at the
        # tail, so pairing up to the shorter of the two is correct.
        out = []
        for x, y in zip(xs, ys, strict=False):
            yv = float(y)
            out.append(
                {"x": round(float(x), 5), "y": round(yv, 6) if np.isfinite(yv) else None}
            )
        return out

    e_before, e_after = minimisation
    metrics = {
        "preset_id": preset.preset_id,
        "engine": "openmm",
        "result_label": preset.scientific_label,
        "dynamics_run": True,
        "n_frames": int(frames.shape[0]),
        "n_atoms": int(frames.shape[1]),
        "n_ca_atoms": int(ca_idx.size),
        "trajectory_reader": reader,
        "steps_total": total_dynamics_steps,
        "timestep_fs": preset.timestep_fs,
        "report_interval": preset.report_interval,
        "simulated_time_ps": round(total_dynamics_steps * preset.timestep_fs / 1000.0, 4),
        "requested_temperature_kelvin": temperature_kelvin,
        "minimisation": {
            "potential_energy_before_kj_mol": round(e_before, 4),
            "potential_energy_after_kj_mol": round(e_after, 4),
            "delta_kj_mol": round(e_after - e_before, 4),
            "max_iterations": preset.minimisation_steps,
        },
        "rmsd_nm": {
            "final": round(float(rmsd[-1]), 6) if rmsd.size else None,
            "max": round(float(rmsd.max()), 6) if rmsd.size else None,
            "mean": round(float(rmsd.mean()), 6) if rmsd.size else None,
        },
        "radius_of_gyration_nm": {
            "initial": round(float(rg[0]), 6) if rg.size else None,
            "final": round(float(rg[-1]), 6) if rg.size else None,
            "relative_change": (
                round(float(abs(rg[-1] - rg[0]) / rg[0]), 6) if rg.size and rg[0] > 0 else None
            ),
        },
        "rmsf_nm": {
            "mean": round(float(rmsf.mean()), 6) if rmsf.size else None,
            "max": round(float(rmsf.max()), 6) if rmsf.size else None,
        },
        "potential_energy_kj_mol": {
            "initial": round(float(potential[0]), 4) if potential else None,
            "final": round(float(potential[-1]), 4) if potential else None,
            "mean": round(float(np.mean(potential)), 4) if potential else None,
        },
        "temperature_kelvin": {
            "mean": round(float(np.mean(temps)), 3) if temps else None,
            "std": round(float(np.std(temps)), 3) if temps else None,
        },
        "degradation_proxy": proxy.as_dict(),
    }

    return EngineResult(
        metrics=metrics,
        series={
            "rmsd": _series(times, rmsd),
            "radius_of_gyration": _series(times, rg),
            "potential_energy": _series(energy_time, potential),
            "kinetic_energy": _series(energy_time, kinetic),
            "total_energy": _series(energy_time, total_energy),
            "temperature": _series(energy_time, temps),
        },
        rmsf=rmsf_rows,
        highest_mobility_residues=top_mobility,
        stability_summary=stability,
        degradation_proxy=proxy.as_dict(),
        topology=topology,
        notes=notes,
    )
