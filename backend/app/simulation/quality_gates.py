"""Automatic quality gates for simulations and paired experiments (issue #13).

A physically invalid run must not become a training row. The failure modes this
guards against were all observed in practice, not imagined:

* progress reported above 100%, which made a finished job look stuck;
* NaN energies from a blown-up integration, which produce a stiffness number
  that is arithmetically fine and physically meaningless;
* a thermostat that drifted far from its target;
* explicit-solvent runs at implausible density.

Two design choices are deliberate.

**These are pure functions over recorded values.** Nothing here touches a
running simulation, so a gate can be added or tightened without risking the
engine. The engine records; the gate judges afterwards.

**There are three outcomes, not two.** ``warning`` exists because a marginal
fit is worth flagging to a human without discarding data that may still be
usable in aggregate. Only ``rejected`` is barred from training, and
``admissible_for_training`` is the single place that decision is made.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

GateStatus = Literal["valid", "warning", "rejected"]

#: Thermostat drift from the target. A few kelvin is normal fluctuation in a
#: small implicit-solvent system; tens of kelvin means the thermostat lost it.
TEMPERATURE_WARN_K = 10.0
TEMPERATURE_REJECT_K = 30.0

#: A fit needs points to mean anything. Below this the slope is noise.
MIN_FORCE_EXTENSION_SAMPLES = 20
MIN_FIT_POINTS = 5

#: r^2 below the warn line is a poor fit worth flagging; below the reject line
#: the "stiffness" is not a measurement of anything.
FIT_R_SQUARED_WARN = 0.50
FIT_R_SQUARED_REJECT = 0.20

#: Liquid water at 300 K. Only meaningful for explicit solvent.
DENSITY_WARN_RANGE = (0.95, 1.05)
DENSITY_REJECT_RANGE = (0.85, 1.15)

#: Units the contract fixes. Anything else is a producer bug, not a preference.
REQUIRED_FORCE_UNIT = "pN"
REQUIRED_EXTENSION_UNIT = "nm"

#: Protocol keys that must be identical between the pristine and damaged runs.
#: If any of these differ, the pair is not a controlled comparison and the
#: degradation number means nothing.
PAIRED_PROTOCOL_KEYS = (
    "forcefield", "solvent_model", "temperature_kelvin", "timestep_fs",
    "friction_per_ps", "nonbonded_cutoff_nm", "constraints", "integrator",
    "minimisation_steps", "equilibration_steps", "production_steps",
    "spring_constant_kj_mol_nm2", "pull_velocity_nm_per_ps",
)

_SEVERITY = {"valid": 0, "warning": 1, "rejected": 2}


@dataclass(frozen=True)
class GateFinding:
    check: str
    status: GateStatus
    detail: str


@dataclass(frozen=True)
class QualityReport:
    """The verdict, plus every finding that produced it."""

    status: GateStatus
    findings: list[GateFinding] = field(default_factory=list)

    @property
    def rejections(self) -> list[GateFinding]:
        return [f for f in self.findings if f.status == "rejected"]

    @property
    def warnings(self) -> list[GateFinding]:
        return [f for f in self.findings if f.status == "warning"]

    @property
    def reasons(self) -> list[str]:
        """Every non-valid finding, phrased for a human."""
        return [f"{f.check}: {f.detail}"
                for f in self.findings if f.status != "valid"]

    @property
    def admissible_for_training(self) -> bool:
        """The single place the training-admission decision is made."""
        return self.status != "rejected"

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "admissible_for_training": self.admissible_for_training,
            "reasons": self.reasons,
            "findings": [
                {"check": f.check, "status": f.status, "detail": f.detail}
                for f in self.findings
            ],
        }


def combine(findings: Iterable[GateFinding]) -> QualityReport:
    """Worst finding wins. A single rejection rejects the run."""
    collected = list(findings)
    worst = max((_SEVERITY[f.status] for f in collected), default=0)
    status: GateStatus = ("rejected" if worst == 2
                          else "warning" if worst == 1 else "valid")
    return QualityReport(status=status, findings=collected)


# --------------------------------------------------------------------------- #
# Individual checks
# --------------------------------------------------------------------------- #
def check_progress(values: Sequence[float]) -> GateFinding:
    """Progress is a fraction in [0, 1]. Above 1.0 made a done job look stuck."""
    if not values:
        return GateFinding("progress", "rejected", "no progress was recorded")
    out_of_range = [v for v in values if not 0.0 <= v <= 1.0]
    if out_of_range:
        return GateFinding(
            "progress", "rejected",
            f"{len(out_of_range)} sample(s) outside 0-100%, worst "
            f"{max(out_of_range, key=abs) * 100:.1f}%",
        )
    if any(b < a for a, b in zip(values, values[1:], strict=False)):
        return GateFinding("progress", "warning", "progress moved backwards")
    return GateFinding("progress", "valid", "bounded to 0-100% and monotonic")


def check_energies(values: Sequence[float]) -> GateFinding:
    """A NaN energy yields a stiffness that is arithmetically fine and false."""
    if not values:
        return GateFinding("energy", "rejected", "no energies were recorded")
    bad = sum(1 for v in values if v is None or not math.isfinite(v))
    if bad:
        return GateFinding(
            "energy", "rejected",
            f"{bad} of {len(values)} samples are NaN or infinite; the "
            "integration diverged and any derived number is meaningless",
        )
    return GateFinding("energy", "valid", f"{len(values)} finite samples")


def check_temperature(values: Sequence[float], target_k: float) -> GateFinding:
    if not values:
        return GateFinding("temperature", "rejected", "no temperatures recorded")
    finite = [v for v in values if v is not None and math.isfinite(v)]
    if not finite:
        return GateFinding("temperature", "rejected",
                           "every temperature sample is NaN or infinite")
    mean = sum(finite) / len(finite)
    drift = abs(mean - target_k)
    detail = f"mean {mean:.1f} K against a {target_k:.1f} K target ({drift:.1f} K)"
    if drift > TEMPERATURE_REJECT_K:
        return GateFinding("temperature", "rejected",
                           f"{detail}; the thermostat did not hold")
    if drift > TEMPERATURE_WARN_K:
        return GateFinding("temperature", "warning", detail)
    return GateFinding("temperature", "valid", detail)


def check_sample_count(n_samples: int) -> GateFinding:
    if n_samples < MIN_FORCE_EXTENSION_SAMPLES:
        return GateFinding(
            "force_extension_samples", "rejected",
            f"{n_samples} samples, fewer than the {MIN_FORCE_EXTENSION_SAMPLES} "
            "needed for a meaningful fit",
        )
    return GateFinding("force_extension_samples", "valid", f"{n_samples} samples")


def check_units(force_unit: str, extension_unit: str) -> GateFinding:
    wrong = []
    if force_unit != REQUIRED_FORCE_UNIT:
        wrong.append(f"force is {force_unit!r}, must be {REQUIRED_FORCE_UNIT!r}")
    if extension_unit != REQUIRED_EXTENSION_UNIT:
        wrong.append(
            f"extension is {extension_unit!r}, must be {REQUIRED_EXTENSION_UNIT!r}"
        )
    if wrong:
        return GateFinding("units", "rejected", "; ".join(wrong))
    return GateFinding("units", "valid", f"{force_unit} vs {extension_unit}")


def check_fit(r_squared: float | None, n_points: int | None) -> GateFinding:
    if r_squared is None or n_points is None:
        return GateFinding("stiffness_fit", "rejected",
                           "the fit reported no r^2 or point count")
    if not math.isfinite(r_squared):
        return GateFinding("stiffness_fit", "rejected", "r^2 is not finite")
    if n_points < MIN_FIT_POINTS:
        return GateFinding(
            "stiffness_fit", "rejected",
            f"fitted on {n_points} points, fewer than {MIN_FIT_POINTS}",
        )
    detail = f"r^2 {r_squared:.3f} over {n_points} points"
    if r_squared < FIT_R_SQUARED_REJECT:
        return GateFinding("stiffness_fit", "rejected",
                           f"{detail}; the slope is not a measurement")
    if r_squared < FIT_R_SQUARED_WARN:
        return GateFinding("stiffness_fit", "warning", detail)
    return GateFinding("stiffness_fit", "valid", detail)


def check_paired_protocols(
    baseline: dict[str, Any], damaged: dict[str, Any]
) -> GateFinding:
    """The pair is only a controlled comparison if the protocols are identical."""
    differences = [
        f"{key}: {baseline.get(key)!r} vs {damaged.get(key)!r}"
        for key in PAIRED_PROTOCOL_KEYS
        if baseline.get(key) != damaged.get(key)
    ]
    if differences:
        return GateFinding(
            "paired_protocol", "rejected",
            f"{len(differences)} parameter(s) differ between the pristine and "
            f"damaged runs -- {'; '.join(differences[:3])}"
            + (" ..." if len(differences) > 3 else "")
            + ". The degradation number is not a controlled comparison.",
        )
    return GateFinding("paired_protocol", "valid",
                       f"all {len(PAIRED_PROTOCOL_KEYS)} paired parameters match")


def check_provenance(seed: int | None, platform: str | None) -> GateFinding:
    absent = [n for n, v in (("random_seed", seed), ("platform", platform))
              if v is None]
    if absent:
        return GateFinding(
            "provenance", "rejected",
            f"{', '.join(absent)} not recorded; the run cannot be reproduced",
        )
    return GateFinding("provenance", "valid", f"seed {seed} on {platform}")


def check_density(
    density_g_cm3: float | None, *, explicit_water: bool
) -> GateFinding:
    """Density is only meaningful with explicit solvent.

    An implicit-solvent run has no water box, so 'density' is not a weak
    signal there -- it is undefined. Marking it not-applicable is different
    from passing it, and the distinction is recorded.
    """
    if not explicit_water:
        return GateFinding("density", "valid",
                           "not applicable: implicit solvent has no water box")
    if density_g_cm3 is None or not math.isfinite(density_g_cm3):
        return GateFinding("density", "rejected",
                           "explicit-solvent run recorded no density")
    detail = f"{density_g_cm3:.3f} g/cm^3"
    low, high = DENSITY_REJECT_RANGE
    if not low <= density_g_cm3 <= high:
        return GateFinding("density", "rejected",
                           f"{detail}, outside {low}-{high}; the box is wrong")
    low, high = DENSITY_WARN_RANGE
    if not low <= density_g_cm3 <= high:
        return GateFinding("density", "warning", f"{detail}, outside {low}-{high}")
    return GateFinding("density", "valid", detail)


# --------------------------------------------------------------------------- #
# Aggregate
# --------------------------------------------------------------------------- #
def evaluate_run(
    *,
    progress: Sequence[float],
    energies: Sequence[float],
    temperatures: Sequence[float],
    target_temperature_k: float,
    n_force_extension_samples: int,
    force_unit: str = REQUIRED_FORCE_UNIT,
    extension_unit: str = REQUIRED_EXTENSION_UNIT,
    fit_r_squared: float | None = None,
    fit_n_points: int | None = None,
    random_seed: int | None = None,
    platform: str | None = None,
    explicit_water: bool = False,
    density_g_cm3: float | None = None,
) -> QualityReport:
    """Gate one simulation run."""
    return combine([
        check_progress(progress),
        check_energies(energies),
        check_temperature(temperatures, target_temperature_k),
        check_sample_count(n_force_extension_samples),
        check_units(force_unit, extension_unit),
        check_fit(fit_r_squared, fit_n_points),
        check_provenance(random_seed, platform),
        check_density(density_g_cm3, explicit_water=explicit_water),
    ])


def evaluate_paired_experiment(
    baseline: QualityReport,
    damaged: QualityReport,
    baseline_protocol: dict[str, Any],
    damaged_protocol: dict[str, Any],
) -> QualityReport:
    """Gate the pair. Either run failing fails the experiment."""
    findings = list(baseline.findings) + list(damaged.findings)
    findings.append(check_paired_protocols(baseline_protocol, damaged_protocol))
    return combine(findings)
