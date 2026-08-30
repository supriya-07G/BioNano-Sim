"""Tests for the steered-MD pulling protocol.

The unit tests run everywhere. The live-run tests are marked ``slow`` and are
skipped when OpenMM is unavailable, matching the rest of the suite.
"""

from __future__ import annotations

import dataclasses
import math
from pathlib import Path

import numpy as np
import pytest

from app.core.exceptions import InvalidSimulationInputError
from app.simulation.presets import MECHANICAL_PULL, PRESETS
from app.simulation.pulling import (
    CSV_HEADER,
    KJ_PER_MOL_NM_IN_PN,
    MAX_FORCE_PN,
    MAX_PULL_VELOCITY,
    MAX_SPRING_CONSTANT,
    PullCancelledError,
    PullConfig,
    _fit_apparent_stiffness,
)

REPO = Path(__file__).resolve().parents[2]
UBIQUITIN = REPO / "data" / "proteins" / "pdb" / "1UBQ.pdb"


# --------------------------------------------------------------------------- #
# Units and configuration
# --------------------------------------------------------------------------- #
def test_force_unit_conversion_matches_the_si_definition():
    """1 kJ/mol/nm expressed in piconewtons, from N_A = 6.02214076e23 exactly."""
    expected = 1000.0 / (6.02214076e23 * 1.0e-9) * 1.0e12
    assert KJ_PER_MOL_NM_IN_PN == pytest.approx(expected, rel=1e-12)
    # Sanity: the well-known value to five significant figures.
    assert KJ_PER_MOL_NM_IN_PN == pytest.approx(1.66054, abs=1e-5)


def test_default_config_is_valid():
    PullConfig().validate()


@pytest.mark.parametrize(
    "kwargs, code",
    [
        ({"spring_constant_kj_mol_nm2": 0.0}, "PULL_SPRING_CONSTANT_OUT_OF_RANGE"),
        (
            {"spring_constant_kj_mol_nm2": MAX_SPRING_CONSTANT * 2},
            "PULL_SPRING_CONSTANT_OUT_OF_RANGE",
        ),
        ({"pull_velocity_nm_per_ps": 0.0}, "PULL_VELOCITY_OUT_OF_RANGE"),
        ({"pull_velocity_nm_per_ps": MAX_PULL_VELOCITY + 1}, "PULL_VELOCITY_OUT_OF_RANGE"),
        ({"restraint_update_steps": 0}, "PULL_INTERVAL_INVALID"),
        ({"sample_interval_steps": 0}, "PULL_INTERVAL_INVALID"),
        ({"restraint_update_steps": 7, "sample_interval_steps": 50}, "PULL_INTERVAL_MISALIGNED"),
    ],
)
def test_unsafe_configurations_are_rejected(kwargs, code):
    with pytest.raises(InvalidSimulationInputError) as exc:
        PullConfig(**kwargs).validate()
    assert exc.value.code == code


def test_mechanical_pull_preset_is_registered_and_carries_a_protocol():
    assert PRESETS["mechanical_pull"] is MECHANICAL_PULL
    assert MECHANICAL_PULL.pulling is not None
    MECHANICAL_PULL.pulling.validate()
    # Every other preset must stay free-dynamics, or existing runs change meaning.
    assert all(p.pulling is None for pid, p in PRESETS.items() if pid != "mechanical_pull")


def test_preset_dict_exposes_the_protocol_to_the_api():
    body = MECHANICAL_PULL.as_dict()
    assert body["pulling"]["spring_constant_kj_mol_nm2"] > 0
    assert body["pulling"]["pull_velocity_nm_per_ps"] > 0
    assert "steered" in body["scientific_label"].lower()


# --------------------------------------------------------------------------- #
# The stiffness fit must refuse to overclaim
# --------------------------------------------------------------------------- #
def _samples(times, extensions, forces):
    return [
        {"time_ps": t, "extension_nm": e, "force_pn": f}
        for t, e, f in zip(times, extensions, forces, strict=True)
    ]


def test_clean_linear_pull_recovers_the_slope():
    times = np.linspace(0.1, 10.0, 100)
    ext = 0.05 * times                      # driven, no noise
    frc = 400.0 * ext                       # exactly 400 pN/nm
    fit = _fit_apparent_stiffness(_samples(times, ext, frc), PullConfig(), 0.05)
    assert fit["available"] and fit["reliable"]
    assert fit["apparent_stiffness_pn_per_nm"] == pytest.approx(400.0, rel=1e-6)
    assert fit["r_squared"] == pytest.approx(1.0, abs=1e-9)


def test_a_negative_slope_is_reported_as_unreliable():
    """Thermal noise can produce an anti-correlated curve. It must never be quoted."""
    times = np.linspace(0.1, 2.0, 20)
    ext = np.linspace(0.0, 0.2, 20)
    frc = -500.0 * ext                      # unphysical for an elastic pull
    fit = _fit_apparent_stiffness(_samples(times, ext, frc), PullConfig(), 0.05)
    assert fit["available"] is True
    assert fit["reliable"] is False
    assert any("negative stiffness" in r for r in fit["unreliable_reasons"])


def test_a_pull_that_never_beats_the_noise_floor_is_unreliable():
    rng = np.random.default_rng(0)
    times = np.linspace(0.1, 2.0, 20)
    ext = rng.normal(0.0, 0.05, size=20)    # pure noise, no net travel
    frc = rng.normal(0.0, 50.0, size=20)
    fit = _fit_apparent_stiffness(_samples(times, ext, frc), PullConfig(), 0.001)
    assert fit["reliable"] is False
    assert fit["unreliable_reasons"]


def test_too_few_samples_yields_no_slope_at_all():
    fit = _fit_apparent_stiffness(_samples([0.1, 0.2], [0.0, 0.1], [0.0, 10.0]), PullConfig(), 0.05)
    assert fit["available"] is False
    assert fit["reliable"] is False


# --------------------------------------------------------------------------- #
# Live OpenMM runs
# --------------------------------------------------------------------------- #
def _fast_pull_preset(**overrides):
    """A real pull, sized for a test rather than a demo. CPU for reproducibility."""
    base = dict(
        platform="CPU",
        minimisation_steps=100,
        equilibration_steps=200,
        production_steps=2_000,
        report_interval=100,
        pulling=PullConfig(pull_velocity_nm_per_ps=0.15, sample_interval_steps=50),
    )
    base.update(overrides)
    return dataclasses.replace(MECHANICAL_PULL, **base)


def _run(job_dir: Path, preset, should_cancel=lambda: False, seed: int = 42):
    from app.simulation.engine import run_simulation

    return run_simulation(
        source_pdb=UBIQUITIN,
        job_dir=job_dir,
        chain_id="A",
        preset=preset,
        temperature_kelvin=300.0,
        seed=seed,
        report=lambda *_: None,
        should_cancel=should_cancel,
        log=lambda _: None,
    )


@pytest.mark.slow
def test_pristine_ubiquitin_produces_a_real_force_extension_curve(tmp_path, openmm_available):
    """Issue #9 acceptance criterion, end to end."""
    if not openmm_available:
        pytest.skip("OpenMM is not installed in this environment.")

    result = _run(tmp_path, _fast_pull_preset())

    # --- the curve exists and is non-empty ---
    pull = result.metrics["pulling"]
    samples = result.series["force_extension"]
    assert pull["n_samples"] == len(samples) == 2_000 // 50
    assert pull["completed"] is True

    csv_path = tmp_path / "analysis" / "force_extension.csv"
    assert csv_path.exists(), "force_extension.csv was not written"
    rows = csv_path.read_text(encoding="utf-8").strip().splitlines()
    assert rows[0].split(",") == CSV_HEADER
    assert len(rows) == len(samples) + 1

    # --- it came from a real applied load ---
    ext = np.array([s["extension_nm"] for s in samples])
    frc = np.array([s["force_pn"] for s in samples])
    assert frc.max() > 50.0, "no meaningful force was ever carried"

    # Both must rise from the start of the pull to the end of it. Comparing
    # quartile means rather than endpoints or a pointwise correlation keeps the
    # assertion about the applied load instead of about thermal noise.
    q = len(samples) // 4
    assert ext[-q:].mean() > ext[:q].mean() + 0.05, "the molecule never extended"
    assert frc[-q:].mean() > frc[:q].mean() + 50.0, "the load never grew"

    # --- the load was applied between the chain termini ---
    selection = pull["selection"]
    assert selection["anchor_residue"].startswith("A:1:")
    assert selection["pulled_residue"].startswith("A:76:")
    assert selection["n_ca_atoms"] == 76
    assert selection["anchor_atom_index"] != selection["pulled_atom_index"]

    # --- units are declared, not implied ---
    assert pull["units"] == {
        "force": "pN",
        "extension": "nm",
        "work": "kJ/mol",
        "stiffness": "pN/nm",
    }


@pytest.mark.slow
def test_the_pull_is_reproducible_from_its_recorded_configuration(tmp_path, openmm_available):
    """The other half of the acceptance criterion: same config + seed, same curve."""
    if not openmm_available:
        pytest.skip("OpenMM is not installed in this environment.")

    # deterministic=True pins the run to a single-threaded CPU. A multi-threaded
    # CPU run sums forces in a nondeterministic order and does NOT repeat: see
    # test_multithreaded_runs_are_not_claimed_to_be_reproducible below.
    preset = _fast_pull_preset(
        production_steps=500, equilibration_steps=100, deterministic=True
    )
    first = _run(tmp_path / "a", preset, seed=7)
    second = _run(tmp_path / "b", preset, seed=7)

    config = first.metrics["pulling"]["config"]
    # Everything a third party needs to repeat the run is recorded.
    for key in (
        "spring_constant_kj_mol_nm2",
        "pull_velocity_nm_per_ps",
        "restraint_update_steps",
        "sample_interval_steps",
        "timestep_fs",
        "requested_steps",
        "anchor_atom_index",
        "pulled_atom_index",
        "force_expression",
    ):
        assert key in config, f"{key} missing from the reproducibility record"
    assert config["seed"] == 7
    assert config["bit_reproducible"] is True
    assert config["platform_properties"]["Threads"] == "1"
    assert second.metrics["pulling"]["config"] == config

    a = [s["force_pn"] for s in first.series["force_extension"]]
    b = [s["force_pn"] for s in second.series["force_extension"]]
    assert a == b, "identical seed and configuration produced a different curve"


@pytest.mark.slow
def test_a_cancelled_pull_stops_instead_of_finishing(tmp_path, openmm_available):
    """Cancellation is observed inside the pulling loop, not only around it."""
    if not openmm_available:
        pytest.skip("OpenMM is not installed in this environment.")

    from app.simulation.preparation import build_openmm_system, extract_chain
    from app.simulation.pulling import run_steered_pull

    preset = _fast_pull_preset()
    prepared = extract_chain(UBIQUITIN, tmp_path / "prepared.pdb", "A")
    simulation, _topology, _notes = build_openmm_system(prepared, preset, 300.0, 42)

    with pytest.raises(PullCancelledError):
        run_steered_pull(
            simulation=simulation,
            config=preset.pulling,
            n_steps=1_000,
            steps_done=0,
            total_dynamics=1_000,
            timestep_fs=preset.timestep_fs,
            report=lambda *_: None,
            should_cancel=lambda: True,
            log=lambda _: None,
        )


@pytest.mark.slow
def test_an_over_extended_pull_stops_at_the_safety_limit(tmp_path, openmm_available):
    """A runaway velocity must abort the pull, not run to completion."""
    if not openmm_available:
        pytest.skip("OpenMM is not installed in this environment.")

    # At 8 nm/ps the restraint outruns the molecule immediately, so the spring
    # load explodes and the force ceiling trips long before 1000 steps.
    preset = _fast_pull_preset(
        production_steps=1_000,
        pulling=PullConfig(pull_velocity_nm_per_ps=8.0, sample_interval_steps=10),
    )
    result = _run(tmp_path, preset)

    pull = result.metrics["pulling"]
    assert pull["completed"] is False
    assert pull["abort_reason"] and "safety limit" in pull["abort_reason"]
    assert pull["max_force_pn"] > MAX_FORCE_PN
    assert pull["pull_steps_completed"] < 1_000
    # The curve collected before the abort is still exported.
    assert pull["n_samples"] > 0
    assert (tmp_path / "analysis" / "force_extension.csv").exists()


@pytest.mark.slow
def test_free_dynamics_presets_apply_no_force_and_report_no_curve(tmp_path, openmm_available):
    """The existing presets must be untouched by this feature."""
    if not openmm_available:
        pytest.skip("OpenMM is not installed in this environment.")

    from app.simulation.presets import RAPID_DEMO

    preset = dataclasses.replace(
        RAPID_DEMO,
        platform="CPU",
        minimisation_steps=50,
        equilibration_steps=100,
        production_steps=200,
        report_interval=50,
    )
    result = _run(tmp_path, preset)

    assert "pulling" not in result.metrics
    assert "force_extension" not in result.series
    assert not (tmp_path / "analysis" / "force_extension.csv").exists()


@pytest.mark.slow
def test_work_is_the_integral_of_force_over_extension(tmp_path, openmm_available):
    """Recompute the reported work from the exported curve and compare."""
    if not openmm_available:
        pytest.skip("OpenMM is not installed in this environment.")

    result = _run(tmp_path, _fast_pull_preset(production_steps=1_000))
    samples = result.series["force_extension"]

    ext = np.array([s["extension_nm"] for s in samples])
    frc_kj = np.array([s["force_pn"] for s in samples]) / KJ_PER_MOL_NM_IN_PN
    # Trapezoid from the initial state (extension 0, force 0) through every sample.
    recomputed = float(np.trapezoid(np.concatenate([[0.0], frc_kj]),
                                    np.concatenate([[0.0], ext])))
    reported = result.metrics["pulling"]["work_kj_mol"]
    assert math.isclose(recomputed, reported, rel_tol=1e-3, abs_tol=1e-3)


@pytest.mark.slow
def test_multithreaded_runs_are_not_claimed_to_be_reproducible(tmp_path, openmm_available):
    """The default fast path is NOT bit-reproducible, and must say so.

    OpenMM's CPU platform sums force contributions across threads in a
    nondeterministic order, so an identical configuration and seed still diverge.
    The failure mode this guards against is a run that quietly claims
    repeatability it cannot deliver.
    """
    if not openmm_available:
        pytest.skip("OpenMM is not installed in this environment.")

    preset = _fast_pull_preset(production_steps=200, equilibration_steps=100)
    assert preset.deterministic is False

    result = _run(tmp_path, preset, seed=7)
    config = result.metrics["pulling"]["config"]
    threads = config["platform_properties"].get("Threads")

    if config["platform"] == "CPU" and threads == "1":
        pytest.skip("single-core machine: the default path is deterministic here")
    assert config["bit_reproducible"] is False
