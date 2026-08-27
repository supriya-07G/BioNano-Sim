"""Simulation presets with hard safety limits.

The Rapid Demo preset is deliberately tiny. It is a real OpenMM integration —
real force field, real integrator, real trajectory — run for a number of steps
that finishes inside a demo. That is emphatically not production molecular
dynamics, and every preset carries the label the UI must use for its results.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from app.config import settings


@dataclass(frozen=True)
class Preset:
    preset_id: str
    label: str
    summary: str
    platform: str
    solvent: str
    nonbonded_cutoff_nm: float
    forcefield: tuple[str, ...]
    production_steps: int
    equilibration_steps: int
    minimisation_steps: int
    timestep_fs: float
    report_interval: int
    friction_per_ps: float
    constraints: str
    estimated_runtime_note: str
    scientific_label: str
    is_default: bool = False
    limitations: list[str] = field(default_factory=list)

    @property
    def simulated_time_ps(self) -> float:
        return (self.production_steps + self.equilibration_steps) * self.timestep_fs / 1000.0

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["forcefield"] = list(self.forcefield)
        d["simulated_time_ps"] = round(self.simulated_time_ps, 4)
        return d


_SHARED_LIMITATIONS = [
    "A 1.2 nm nonbonded cutoff is applied. Implicit-solvent GBn2 with no cutoff is "
    "roughly 8x slower and infeasible for a live demo; the cutoff is standard "
    "practice for implicit solvent but does neglect long-range electrostatics.",
    "Implicit solvent (GBn2). There are no explicit water molecules, so hydration "
    "shell effects and solvent viscosity are approximated.",
    "Standard OpenMM does not model ionising-radiation events. No particle track, "
    "energy deposition, radical chemistry or bond scission is simulated.",
    "Simulated time is picoseconds to nanoseconds. Real degradation processes occur "
    "over seconds to years, so this cannot be extrapolated to mission timescales.",
]

RAPID_DEMO = Preset(
    preset_id="rapid_demo",
    label="Rapid Demo",
    summary=(
        "Minimal real OpenMM run sized to finish in a live demonstration. "
        "Implicit solvent, 1.2 nm nonbonded cutoff, fastest available platform, "
        "deterministic seed."
    ),
    platform="auto",
    solvent="implicit_gbn2",
    nonbonded_cutoff_nm=1.2,
    forcefield=("amber14-all.xml", "implicit/gbn2.xml"),
    production_steps=5_000,
    equilibration_steps=1_000,
    minimisation_steps=500,
    timestep_fs=2.0,
    report_interval=100,
    friction_per_ps=1.0,
    constraints="HBonds",
    estimated_runtime_note=(
        "About 15-25 s on a GPU platform (OpenCL/CUDA) or 80-120 s on a multi-core "
        "CPU, for a 56-107 residue domain."
    ),
    scientific_label="Rapid OpenMM Simulation",
    is_default=True,
    limitations=[
        "12 ps total simulated time. This is a smoke-scale run: long enough to show "
        "real dynamics and produce genuine metrics, far too short for equilibrium "
        "sampling or any statistical claim.",
        *_SHARED_LIMITATIONS,
    ],
)

EXTENDED_DEMO = Preset(
    preset_id="extended_demo",
    label="Extended Demo",
    summary=(
        "Four times the Rapid Demo trajectory, for a smoother RMSD curve when you "
        "can wait a few minutes."
    ),
    platform="auto",
    solvent="implicit_gbn2",
    nonbonded_cutoff_nm=1.2,
    forcefield=("amber14-all.xml", "implicit/gbn2.xml"),
    production_steps=20_000,
    equilibration_steps=2_000,
    minimisation_steps=1_000,
    timestep_fs=2.0,
    report_interval=200,
    friction_per_ps=1.0,
    constraints="HBonds",
    estimated_runtime_note=(
        "About 60-90 s on a GPU platform or 5-8 min on a multi-core CPU."
    ),
    scientific_label="Rapid OpenMM Simulation",
    limitations=[
        "44 ps total simulated time. Still far below equilibrium sampling.",
        *_SHARED_LIMITATIONS,
    ],
)

MINIMISATION_ONLY = Preset(
    preset_id="minimisation_only",
    label="Minimisation only",
    summary=(
        "Energy minimisation with no dynamics. The safe fallback when a structure "
        "fails to equilibrate, and the fastest way to confirm the engine works."
    ),
    platform="auto",
    solvent="implicit_gbn2",
    nonbonded_cutoff_nm=1.2,
    forcefield=("amber14-all.xml", "implicit/gbn2.xml"),
    production_steps=0,
    equilibration_steps=0,
    minimisation_steps=1_000,
    timestep_fs=2.0,
    report_interval=1,
    friction_per_ps=1.0,
    constraints="HBonds",
    estimated_runtime_note="Usually under 15 s.",
    scientific_label="Energy Minimisation Only (no dynamics)",
    limitations=[
        "No dynamics are run, so there is no trajectory: RMSF and time series are "
        "unavailable and the degradation proxy is not computed.",
        "Implicit solvent (GBn2) with a 1.2 nm nonbonded cutoff.",
        "Standard OpenMM does not model ionising-radiation events.",
    ],
)

PRESETS: dict[str, Preset] = {
    p.preset_id: p for p in (RAPID_DEMO, EXTENDED_DEMO, MINIMISATION_ONLY)
}

DEFAULT_PRESET_ID = RAPID_DEMO.preset_id
SAFE_RETRY_PRESET_ID = MINIMISATION_ONLY.preset_id


def get_preset(preset_id: str) -> Preset:
    from app.core.exceptions import InvalidSimulationInputError

    preset = PRESETS.get(preset_id)
    if preset is None:
        raise InvalidSimulationInputError(
            f"Unknown simulation preset '{preset_id}'. Available: "
            f"{', '.join(sorted(PRESETS))}.",
            code="UNKNOWN_PRESET",
        )
    if preset.production_steps > settings.max_production_steps:
        raise InvalidSimulationInputError(
            f"Preset '{preset_id}' requests {preset.production_steps} production "
            f"steps, above the configured cap of {settings.max_production_steps}.",
            code="PRESET_EXCEEDS_LIMIT",
        )
    return preset


def list_presets() -> list[dict[str, Any]]:
    return [p.as_dict() for p in PRESETS.values()]
