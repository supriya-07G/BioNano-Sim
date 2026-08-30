"""Constant-velocity steered molecular dynamics: the mechanical pulling protocol.

What this is
------------
A harmonic restraint is applied to the *distance between two atoms* — an anchor
and a pulled atom — and the restraint centre ``r0`` recedes at a constant
velocity. The spring stretches until the molecule follows it. Sampling the force
the spring carries against the distance the molecule actually reached gives a
force-extension curve from a real applied perturbation.

The reaction coordinate is an interatomic distance, which is invariant under
translation and rotation of the whole molecule. That is deliberate: nothing has
to be pinned in the laboratory frame, so the curve carries no artefact from a
centre-of-mass restraint fighting against global tumbling.

What this is NOT
----------------
  * Not an experimental AFM measurement. The pulling velocity here is of order
    0.05 nm/ps = 5e7 nm/s. AFM pulls at 1e2-1e4 nm/s. This protocol is therefore
    around a *million times faster* than the experiment it is named after, and
    non-equilibrium SMD forces grow roughly logarithmically with loading rate.
    The forces reported here are consequently far larger than experimental
    rupture forces for the same protein. They are comparable to each other under
    an identical protocol, and to nothing else.
  * Not an unfolding trajectory. Picosecond runs reach the elastic and early
    yield regime only. No native-contact rupture is expected or claimed.
  * Not equilibrium elasticity. The extracted stiffness is an *apparent*,
    loading-rate-dependent slope, not a thermodynamic elastic constant.
  * Not statistics. One trajectory is one sample. There are no error bars,
    because a single pull cannot produce them.

The numbers this module returns are only meaningful when compared against
another run of the *same* protocol with the same spring constant, velocity,
temperature and preset. That is exactly the comparison a paired pristine-vs-
damaged experiment makes, which is what it is built for.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np

from app.core.logging import get_logger
from app.schemas.simulation import JobStage

logger = get_logger("COSMORA.simulation.pulling")

# 1 kJ/mol/nm = 1000 / (N_A * 1e-9) newtons = 1.6605390667 pN.
# N_A = 6.02214076e23 /mol exactly (SI 2019), so this constant is exact.
KJ_PER_MOL_NM_IN_PN = 1000.0 / (6.02214076e23 * 1.0e-9) * 1.0e12

# --- Hard safety limits (task 8) ------------------------------------------- #
MIN_SPRING_CONSTANT = 1.0          # kJ/mol/nm^2
MAX_SPRING_CONSTANT = 100_000.0    # kJ/mol/nm^2
MAX_PULL_VELOCITY = 10.0           # nm/ps
MAX_EXTENSION_FACTOR = 4.0         # abort past 4x the initial end-to-end distance
# A protein pulled harder than this is being destroyed by the protocol rather
# than probed by it. Real SMD forces on a small domain are hundreds of pN.
MAX_FORCE_PN = 10_000.0


@dataclass(frozen=True)
class PullConfig:
    """Every parameter needed to reproduce a pull. Serialised into the result."""

    spring_constant_kj_mol_nm2: float = 1000.0
    pull_velocity_nm_per_ps: float = 0.05
    # r0 is a staircase, not a ramp: OpenMM has no per-step callback, so the
    # restraint centre is advanced every ``restraint_update_steps``. At the
    # defaults that is one 0.001 nm step every 20 fs, far below the thermal
    # amplitude of the coordinate, so the staircase is not resolvable.
    restraint_update_steps: int = 10
    sample_interval_steps: int = 50
    anchor_selection: str = "n_terminal_ca"
    pulled_selection: str = "c_terminal_ca"
    # The stiffness fit ignores the start of the pull until the restraint has
    # travelled this many times the measured thermal fluctuation of the
    # end-to-end distance. Below that the spring force is noise, not signal.
    fit_noise_multiple: float = 3.0
    min_fit_points: int = 5
    # The instantaneous spring force tracks the thermal motion of the end-to-end
    # distance, so a per-sample fit is dominated by noise rather than by the
    # elastic response. Consecutive samples are averaged into blocks of this size
    # before fitting, which is standard practice for SMD force-extension work.
    # 1 disables blocking.
    fit_block_size: int = 25

    def validate(self) -> None:
        from app.core.exceptions import InvalidSimulationInputError

        k = self.spring_constant_kj_mol_nm2
        if not MIN_SPRING_CONSTANT <= k <= MAX_SPRING_CONSTANT:
            raise InvalidSimulationInputError(
                f"Spring constant {k} kJ/mol/nm^2 is outside the permitted range "
                f"[{MIN_SPRING_CONSTANT}, {MAX_SPRING_CONSTANT}].",
                code="PULL_SPRING_CONSTANT_OUT_OF_RANGE",
            )
        if not 0.0 < self.pull_velocity_nm_per_ps <= MAX_PULL_VELOCITY:
            raise InvalidSimulationInputError(
                f"Pull velocity {self.pull_velocity_nm_per_ps} nm/ps is outside the "
                f"permitted range (0, {MAX_PULL_VELOCITY}].",
                code="PULL_VELOCITY_OUT_OF_RANGE",
            )
        if self.restraint_update_steps < 1 or self.sample_interval_steps < 1:
            raise InvalidSimulationInputError(
                "Pull update and sample intervals must be >= 1 step.",
                code="PULL_INTERVAL_INVALID",
            )
        if self.sample_interval_steps % self.restraint_update_steps != 0:
            raise InvalidSimulationInputError(
                f"sample_interval_steps ({self.sample_interval_steps}) must be a "
                f"multiple of restraint_update_steps ({self.restraint_update_steps}) "
                "so that samples land on restraint updates.",
                code="PULL_INTERVAL_MISALIGNED",
            )

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PullResult:
    samples: list[dict[str, float]] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    steps_completed: int = 0


CSV_HEADER = [
    "time_ps",
    "restraint_center_nm",
    "end_to_end_nm",
    "extension_nm",
    "force_pn",
    "work_kj_mol",
    "potential_energy_kj_mol",
]


def select_pull_atoms(topology: Any) -> tuple[int, int, dict[str, Any]]:
    """Anchor = first Cα of the chain, pulled = last Cα (task 1).

    Cα termini are the standard SMD attachment points for a single-domain pull:
    they are backbone atoms, present in every standard residue, and pulling
    between them loads the chain end-to-end the way an AFM experiment does.
    """
    from app.core.exceptions import InvalidSimulationInputError

    ca_atoms = [a for a in topology.atoms() if a.name == "CA"]
    if len(ca_atoms) < 2:
        raise InvalidSimulationInputError(
            f"A pull needs at least two Cα atoms; this topology has {len(ca_atoms)}.",
            code="PULL_INSUFFICIENT_CA",
        )
    anchor, pulled = ca_atoms[0], ca_atoms[-1]
    description = {
        "anchor_atom_index": anchor.index,
        "pulled_atom_index": pulled.index,
        "anchor_residue": f"{anchor.residue.chain.id}:{anchor.residue.id}:{anchor.residue.name}",
        "pulled_residue": f"{pulled.residue.chain.id}:{pulled.residue.id}:{pulled.residue.name}",
        "n_ca_atoms": len(ca_atoms),
        "selection_rule": "first and last Cα of the prepared chain (N- to C-terminus)",
    }
    return anchor.index, pulled.index, description


class PullCancelledError(Exception):
    """Raised when a cancel request is observed mid-pull (task 7)."""


def _fit_apparent_stiffness(
    samples: list[dict[str, float]], config: PullConfig, velocity: float
) -> dict[str, Any]:
    """Least-squares slope of force vs extension over the *driven* part of the pull.

    The opening stretch of any pull is noise rather than signal. Until the
    restraint centre has travelled further than the thermal fluctuation of the
    end-to-end distance, the spring force is dominated by the molecule wandering
    under its own dynamics, and a slope fitted there is meaningless — routinely
    even negative, because the coordinate happens to stretch while the spring is
    still compressed. The fit therefore starts only once the restraint has moved
    ``fit_noise_multiple`` times the measured fluctuation amplitude.

    The result is an *apparent* stiffness at this loading rate. It carries a
    ``reliable`` flag, and when that flag is false the number must not be quoted:
    the reasons say what failed.
    """
    if len(samples) < config.min_fit_points:
        return {
            "available": False,
            "reliable": False,
            "reason": (
                f"Only {len(samples)} force-extension samples were collected; "
                f"{config.min_fit_points} are needed to fit a slope."
            ),
        }

    times = np.array([s["time_ps"] for s in samples], dtype=float)
    ext = np.array([s["extension_nm"] for s in samples], dtype=float)
    frc = np.array([s["force_pn"] for s in samples], dtype=float)

    # Fluctuation amplitude: spread of the extension about its linear-in-time
    # trend. Measuring against the trend rather than the mean avoids counting
    # the pull itself as noise.
    duration = float(times.max() - times.min())
    if times.size >= 3 and duration > 0.0:
        residual = ext - np.polyval(np.polyfit(times, ext, 1), times)
        noise_nm = float(np.std(residual))
    else:
        noise_nm = 0.0

    travel_nm = float(velocity * duration)
    onset_nm = float(config.fit_noise_multiple * noise_nm)
    onset_ps = float(times.min() + onset_nm / velocity) if velocity > 0 else float(times.min())

    mask = times >= onset_ps
    truncated = False
    if int(mask.sum()) < max(config.min_fit_points, config.fit_block_size):
        # Never cleanly escaped the noise floor, or too few samples to block.
        # Fit everything so the number exists for inspection, but the reasons
        # below will mark it unreliable.
        mask = np.ones_like(times, dtype=bool)
        truncated = True

    ext_fit, frc_fit = ext[mask], frc[mask]

    # Raw per-sample fit, kept for transparency: it is what a naive analysis
    # would report, and the gap between it and the blocked fit is the size of
    # the thermal noise the blocking removes.
    raw_slope, raw_intercept = np.polyfit(ext_fit, frc_fit, 1)
    raw_pred = raw_slope * ext_fit + raw_intercept
    raw_ss_res = float(((frc_fit - raw_pred) ** 2).sum())
    raw_ss_tot = float(((frc_fit - frc_fit.mean()) ** 2).sum())
    raw_r_squared = 1.0 - raw_ss_res / raw_ss_tot if raw_ss_tot > 0.0 else 0.0

    block = max(1, int(config.fit_block_size))
    n_blocks = ext_fit.size // block
    if block > 1 and n_blocks >= config.min_fit_points:
        # Time-ordered, non-overlapping blocks; the remainder is dropped so every
        # block carries the same weight.
        usable = n_blocks * block
        ext_fit = ext_fit[:usable].reshape(n_blocks, block).mean(axis=1)
        frc_fit = frc_fit[:usable].reshape(n_blocks, block).mean(axis=1)
        blocked = True
    else:
        blocked = False
        n_blocks = ext_fit.size

    slope, intercept = np.polyfit(ext_fit, frc_fit, 1)
    predicted = slope * ext_fit + intercept
    ss_res = float(((frc_fit - predicted) ** 2).sum())
    ss_tot = float(((frc_fit - frc_fit.mean()) ** 2).sum())
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0.0 else 0.0

    reasons: list[str] = []
    if travel_nm < onset_nm:
        reasons.append(
            f"The restraint travelled {travel_nm:.3f} nm, less than the "
            f"{onset_nm:.3f} nm needed to exceed {config.fit_noise_multiple}x the "
            f"{noise_nm:.3f} nm thermal fluctuation of the end-to-end distance. "
            "Pull further or faster before reading this slope."
        )
    if truncated:
        reasons.append(
            "No samples survived the noise-floor cut, so the fit used the whole "
            "curve including its noise-dominated start."
        )
    if slope <= 0.0:
        reasons.append(
            f"The fitted slope is {slope:.1f} pN/nm. A negative stiffness is "
            "unphysical for an elastic pull and indicates the pull was dominated "
            "by thermal motion rather than the applied load."
        )
    if r_squared < 0.5:
        reasons.append(
            f"r squared is {r_squared:.3f}; a straight line does not describe this "
            "force-extension curve well enough to quote a single stiffness."
        )

    return {
        "available": True,
        "reliable": not reasons,
        "unreliable_reasons": reasons,
        "apparent_stiffness_pn_per_nm": round(float(slope), 4),
        "intercept_pn": round(float(intercept), 4),
        "r_squared": round(float(r_squared), 5),
        "n_points": int(n_blocks),
        "n_samples_in_fit": int(mask.sum()),
        "n_samples_total": len(samples),
        "block_averaged": bool(blocked),
        "block_size": int(block) if blocked else 1,
        "raw_stiffness_pn_per_nm": round(float(raw_slope), 4),
        "raw_r_squared": round(float(raw_r_squared), 5),
        "fit_start_ps": round(onset_ps, 4),
        "extension_fluctuation_nm": round(noise_nm, 5),
        "restraint_travel_nm": round(travel_nm, 5),
        "extension_window_nm": [
            round(float(ext_fit.min()), 5),
            round(float(ext_fit.max()), 5),
        ],
        "method": (
            "numpy.polyfit degree 1 of force (pN) against extension (nm), over "
            f"samples after the restraint had travelled {config.fit_noise_multiple}x "
            f"the extension fluctuation, block-averaged in groups of {block}"
        ),
    }


def run_steered_pull(
    *,
    simulation: Any,
    config: PullConfig,
    n_steps: int,
    steps_done: int,
    total_dynamics: int,
    timestep_fs: float,
    report: Callable[[JobStage, str, dict[str, Any] | None], None],
    should_cancel: Callable[[], bool],
    log: Callable[[str], None],
) -> tuple[int, PullResult]:
    """Run the pull. Returns (steps_done, result). Raises PullCancelledError on cancel."""
    from openmm import CustomBondForce
    from openmm.unit import kilojoule_per_mole, nanometer

    config.validate()

    anchor_idx, pulled_idx, selection = select_pull_atoms(simulation.topology)
    k = float(config.spring_constant_kj_mol_nm2)
    velocity = float(config.pull_velocity_nm_per_ps)

    def _positions_nm() -> np.ndarray:
        state = simulation.context.getState(getPositions=True)
        return np.asarray(
            state.getPositions(asNumpy=True).value_in_unit(nanometer), dtype=float
        )

    xyz = _positions_nm()
    d0 = float(np.linalg.norm(xyz[pulled_idx] - xyz[anchor_idx]))

    # U = 0.5 k (r - r0)^2 on the anchor-pulled distance. Its own force group so
    # the restraint energy can be separated from the molecular potential.
    force = CustomBondForce("0.5*k_pull*(r - r0_pull)^2")
    force.addGlobalParameter("k_pull", k)
    force.addGlobalParameter("r0_pull", d0)
    force.addBond(anchor_idx, pulled_idx, [])
    force.setForceGroup(31)
    simulation.system.addForce(force)
    # The Context caches the System, so it must be rebuilt for the new force to
    # take effect. preserveState keeps the equilibrated positions and velocities.
    simulation.context.reinitialize(preserveState=True)

    log(
        "pull: anchor {} (atom {}) -> pulled {} (atom {})".format(
            selection["anchor_residue"],
            anchor_idx,
            selection["pulled_residue"],
            pulled_idx,
        )
    )
    log(
        f"pull: k={k} kJ/mol/nm^2, v={velocity} nm/ps, initial end-to-end "
        f"{d0:.4f} nm, {n_steps} steps at {timestep_fs} fs"
    )

    samples: list[dict[str, float]] = []
    work_kj = 0.0
    prev_force_kj = 0.0
    prev_distance = d0
    pull_steps = 0
    remaining = n_steps
    abort_reason: str | None = None

    while remaining > 0:
        if should_cancel():
            log(f"pull: cancellation observed at pull step {pull_steps}")
            raise PullCancelledError()

        chunk = min(config.restraint_update_steps, remaining)
        r0 = d0 + velocity * (pull_steps * timestep_fs / 1000.0)
        simulation.context.setParameter("r0_pull", r0)
        simulation.step(chunk)
        remaining -= chunk
        pull_steps += chunk
        steps_done += chunk

        due = pull_steps % config.sample_interval_steps == 0
        if not due and remaining > 0:
            continue

        state = simulation.context.getState(getPositions=True, getEnergy=True)
        xyz = np.asarray(
            state.getPositions(asNumpy=True).value_in_unit(nanometer), dtype=float
        )
        distance = float(np.linalg.norm(xyz[pulled_idx] - xyz[anchor_idx]))
        total_pe = float(state.getPotentialEnergy().value_in_unit(kilojoule_per_mole))
        # The same expression OpenMM integrates, so this is exact, not an estimate.
        restraint_pe = 0.5 * k * (distance - r0) ** 2
        force_kj = k * (r0 - distance)

        work_kj += 0.5 * (force_kj + prev_force_kj) * (distance - prev_distance)
        prev_force_kj, prev_distance = force_kj, distance

        samples.append(
            {
                "time_ps": round(pull_steps * timestep_fs / 1000.0, 6),
                "restraint_center_nm": round(r0, 6),
                "end_to_end_nm": round(distance, 6),
                "extension_nm": round(distance - d0, 6),
                "force_pn": round(force_kj * KJ_PER_MOL_NM_IN_PN, 5),
                "work_kj_mol": round(work_kj, 5),
                "potential_energy_kj_mol": round(total_pe - restraint_pe, 4),
            }
        )

        latest = samples[-1]
        report(
            JobStage.PRODUCTION,
            "pulling: {}/{} steps, {:.1f} pN at {:+.3f} nm".format(
                pull_steps, n_steps, latest["force_pn"], latest["extension_nm"]
            ),
            {
                "steps_completed": steps_done,
                "steps_total": total_dynamics,
                "potential_energy_kj_mol": latest["potential_energy_kj_mol"],
                "pull_force_pn": latest["force_pn"],
                "pull_extension_nm": latest["extension_nm"],
            },
        )

        if abs(latest["force_pn"]) > MAX_FORCE_PN:
            abort_reason = (
                f"The restraint force reached {latest['force_pn']:.0f} pN, above the "
                f"{MAX_FORCE_PN:.0f} pN safety limit. The molecule cannot follow the "
                "restraint at this pulling velocity, so the pull was stopped early. "
                "Lower the velocity or the spring constant."
            )
            log(f"pull: {abort_reason}")
            break

        if distance > d0 * MAX_EXTENSION_FACTOR:
            abort_reason = (
                f"End-to-end distance reached {distance:.3f} nm, above the safety "
                f"limit of {MAX_EXTENSION_FACTOR}x the initial {d0:.3f} nm. The pull "
                "was stopped early; the curve up to that point is still valid."
            )
            log(f"pull: {abort_reason}")
            break

    stiffness = _fit_apparent_stiffness(samples, config, velocity)
    forces = [s["force_pn"] for s in samples] or [0.0]
    extensions = [s["extension_nm"] for s in samples] or [0.0]

    summary: dict[str, Any] = {
        "protocol": "constant_velocity_steered_md",
        "reaction_coordinate": "anchor-pulled interatomic distance",
        "n_samples": len(samples),
        "pull_steps_completed": pull_steps,
        "pull_time_ps": round(pull_steps * timestep_fs / 1000.0, 6),
        "initial_end_to_end_nm": round(d0, 6),
        "final_end_to_end_nm": (
            round(samples[-1]["end_to_end_nm"], 6) if samples else round(d0, 6)
        ),
        "max_extension_nm": round(max(extensions), 6),
        "max_force_pn": round(max(forces), 5),
        "work_kj_mol": round(work_kj, 5),
        "pull_velocity_nm_per_ps": velocity,
        "spring_constant_kj_mol_nm2": k,
        "spring_constant_pn_per_nm": round(k * KJ_PER_MOL_NM_IN_PN, 4),
        "stiffness_fit": stiffness,
        "selection": selection,
        "completed": abort_reason is None,
        "abort_reason": abort_reason,
    }

    notes = [
        "Force-extension came from a real applied moving harmonic restraint on the "
        "anchor-pulled distance, integrated by OpenMM.",
        f"Pulling velocity {velocity} nm/ps is around a million times faster than an "
        "AFM experiment. Non-equilibrium SMD forces rise with loading rate, so these "
        "forces are far above experimental rupture forces and are comparable only to "
        "other runs of this same protocol.",
        "Picosecond pulls probe the elastic and early-yield regime. No unfolding or "
        "native-contact rupture is claimed.",
        "The fitted stiffness is an apparent, loading-rate-dependent slope, not an "
        "equilibrium elastic constant.",
        "One trajectory is one sample: no error bars are reported, because a single "
        "pull cannot produce them.",
        "Potential energies in force_extension.csv have the restraint term removed. "
        "The energies in state.csv do not, so they rise during the pull stage.",
    ]
    if abort_reason:
        notes.append(abort_reason)

    return steps_done, PullResult(
        samples=samples,
        summary=summary,
        config={
            **config.as_dict(),
            "timestep_fs": timestep_fs,
            "requested_steps": n_steps,
            "anchor_atom_index": anchor_idx,
            "pulled_atom_index": pulled_idx,
            "force_expression": "0.5*k_pull*(r - r0_pull)^2",
            "restraint_force_group": 31,
            "units": {
                "spring_constant": "kJ/mol/nm^2",
                "velocity": "nm/ps",
                "force": "pN",
                "distance": "nm",
                "work": "kJ/mol",
            },
        },
        notes=notes,
        steps_completed=pull_steps,
    )
