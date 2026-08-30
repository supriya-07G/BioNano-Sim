"""Tests for the automatic quality gates (issue #13).

The acceptance criterion names three previously observed failure patterns:
excessive temperature, low explicit-solvent density, and progress above 100%.
Each gets a test proving it is detected *and* that it cannot produce an
accepted training row -- detection alone would not satisfy the issue.
"""

from __future__ import annotations

import math

import pytest

from app.simulation.quality_gates import (
    FIT_R_SQUARED_REJECT,
    MIN_FORCE_EXTENSION_SAMPLES,
    GateFinding,
    check_density,
    check_energies,
    check_fit,
    check_paired_protocols,
    check_progress,
    check_provenance,
    check_sample_count,
    check_temperature,
    check_units,
    combine,
    evaluate_paired_experiment,
    evaluate_run,
)

GOOD_PROTOCOL = {
    "forcefield": ["amber14-all.xml", "implicit/gbn2.xml"],
    "solvent_model": "implicit_gbn2", "temperature_kelvin": 300.0,
    "timestep_fs": 2.0, "friction_per_ps": 1.0, "nonbonded_cutoff_nm": 1.2,
    "constraints": "HBonds", "integrator": "LangevinMiddleIntegrator",
    "minimisation_steps": 1000, "equilibration_steps": 5000,
    "production_steps": 20000, "spring_constant_kj_mol_nm2": 1000.0,
    "pull_velocity_nm_per_ps": 0.03,
}


def healthy_run(**overrides):
    kwargs = {
        "progress": [0.0, 0.25, 0.5, 0.75, 1.0],
        "energies": [-12958.7, -12100.2, -11680.7],
        "temperatures": [299.1, 300.4, 301.2, 299.8],
        "target_temperature_k": 300.0,
        "n_force_extension_samples": 400,
        "fit_r_squared": 0.89,
        "fit_n_points": 42,
        "random_seed": 1,
        "platform": "CPU",
    }
    return evaluate_run(**(kwargs | overrides))


# --------------------------------------------------------------------------- #
# The three failure patterns the issue names
# --------------------------------------------------------------------------- #
def test_progress_above_100_percent_is_rejected():
    report = healthy_run(progress=[0.0, 0.5, 1.4])
    assert report.status == "rejected"
    assert not report.admissible_for_training
    assert any("outside 0-100%" in r for r in report.reasons)


def test_excessive_temperature_is_rejected():
    report = healthy_run(temperatures=[420.0, 430.0, 425.0])
    assert report.status == "rejected"
    assert not report.admissible_for_training
    assert any("thermostat did not hold" in r for r in report.reasons)


def test_low_explicit_solvent_density_is_rejected():
    report = healthy_run(explicit_water=True, density_g_cm3=0.62)
    assert report.status == "rejected"
    assert not report.admissible_for_training
    assert any("the box is wrong" in r for r in report.reasons)


# --------------------------------------------------------------------------- #
# Progress
# --------------------------------------------------------------------------- #
def test_bounded_progress_is_valid():
    assert check_progress([0.0, 0.5, 1.0]).status == "valid"


def test_negative_progress_is_rejected():
    assert check_progress([0.0, -0.2]).status == "rejected"


def test_backwards_progress_only_warns():
    """Recoverable and worth a human's attention, not a discard."""
    assert check_progress([0.0, 0.6, 0.4, 1.0]).status == "warning"


def test_absent_progress_is_rejected():
    assert check_progress([]).status == "rejected"


# --------------------------------------------------------------------------- #
# Energies
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf])
def test_non_finite_energy_is_rejected(bad):
    finding = check_energies([-100.0, bad, -102.0])
    assert finding.status == "rejected"
    assert "diverged" in finding.detail


def test_finite_energies_are_valid():
    assert check_energies([-100.0, -101.5]).status == "valid"


# --------------------------------------------------------------------------- #
# Temperature
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "temps,expected",
    [([300.0, 299.5], "valid"), ([315.0, 316.0], "warning"), ([260.0, 258.0], "rejected")],
)
def test_temperature_bands(temps, expected):
    assert check_temperature(temps, 300.0).status == expected


def test_all_nan_temperatures_are_rejected():
    assert check_temperature([math.nan, math.nan], 300.0).status == "rejected"


# --------------------------------------------------------------------------- #
# Samples, units and fit
# --------------------------------------------------------------------------- #
def test_too_few_samples_is_rejected():
    assert check_sample_count(MIN_FORCE_EXTENSION_SAMPLES - 1).status == "rejected"
    assert check_sample_count(MIN_FORCE_EXTENSION_SAMPLES).status == "valid"


def test_wrong_force_unit_is_rejected():
    finding = check_units("kJ/mol/nm", "nm")
    assert finding.status == "rejected"
    assert "force" in finding.detail


def test_wrong_extension_unit_is_rejected():
    assert check_units("pN", "angstrom").status == "rejected"


def test_a_hopeless_fit_is_rejected():
    finding = check_fit(FIT_R_SQUARED_REJECT - 0.01, 40)
    assert finding.status == "rejected"
    assert "not a measurement" in finding.detail


def test_a_marginal_fit_only_warns():
    assert check_fit(0.35, 40).status == "warning"


def test_a_fit_on_too_few_points_is_rejected():
    assert check_fit(0.99, 2).status == "rejected"


def test_a_missing_fit_is_rejected():
    assert check_fit(None, None).status == "rejected"


# --------------------------------------------------------------------------- #
# Provenance and density
# --------------------------------------------------------------------------- #
def test_a_missing_seed_is_rejected():
    finding = check_provenance(None, "CPU")
    assert finding.status == "rejected"
    assert "random_seed" in finding.detail


def test_a_missing_platform_is_rejected():
    assert check_provenance(1, None).status == "rejected"


def test_density_is_not_applicable_for_implicit_solvent():
    """Undefined, not merely unmeasured. The distinction is recorded."""
    finding = check_density(None, explicit_water=False)
    assert finding.status == "valid"
    assert "not applicable" in finding.detail


def test_explicit_solvent_without_density_is_rejected():
    assert check_density(None, explicit_water=True).status == "rejected"


@pytest.mark.parametrize(
    "density,expected",
    [(1.00, "valid"), (0.92, "warning"), (1.30, "rejected")],
)
def test_density_bands_for_explicit_solvent(density, expected):
    assert check_density(density, explicit_water=True).status == expected


# --------------------------------------------------------------------------- #
# Aggregation
# --------------------------------------------------------------------------- #
def test_a_healthy_run_is_valid_and_admissible():
    report = healthy_run()
    assert report.status == "valid"
    assert report.admissible_for_training
    assert report.reasons == []


def test_the_worst_finding_decides():
    report = combine([
        GateFinding("a", "valid", ""),
        GateFinding("b", "warning", ""),
        GateFinding("c", "rejected", ""),
    ])
    assert report.status == "rejected"


def test_a_warning_run_is_still_admissible():
    """Marginal data is flagged for a human, not discarded."""
    report = healthy_run(fit_r_squared=0.35)
    assert report.status == "warning"
    assert report.admissible_for_training


def test_every_rejection_reports_a_reason():
    report = healthy_run(progress=[2.0], temperatures=[500.0], fit_n_points=1)
    assert report.status == "rejected"
    assert len(report.rejections) >= 3
    assert all(f.detail for f in report.rejections), "a reason must never be blank"


def test_the_report_serialises():
    payload = healthy_run().as_dict()
    assert payload["status"] == "valid"
    assert payload["admissible_for_training"] is True
    assert all({"check", "status", "detail"} <= set(f) for f in payload["findings"])


# --------------------------------------------------------------------------- #
# Paired experiments
# --------------------------------------------------------------------------- #
def test_matching_protocols_pass():
    assert check_paired_protocols(GOOD_PROTOCOL, dict(GOOD_PROTOCOL)).status == "valid"


def test_a_mismatched_paired_protocol_is_rejected():
    damaged = dict(GOOD_PROTOCOL) | {"temperature_kelvin": 310.0}
    finding = check_paired_protocols(GOOD_PROTOCOL, damaged)
    assert finding.status == "rejected"
    assert "not a controlled comparison" in finding.detail


def test_a_pair_fails_if_either_run_fails():
    good, bad = healthy_run(), healthy_run(temperatures=[500.0])
    report = evaluate_paired_experiment(
        good, bad, GOOD_PROTOCOL, dict(GOOD_PROTOCOL)
    )
    assert report.status == "rejected"
    assert not report.admissible_for_training


def test_a_healthy_pair_is_admissible():
    good = healthy_run()
    report = evaluate_paired_experiment(
        good, healthy_run(), GOOD_PROTOCOL, dict(GOOD_PROTOCOL)
    )
    assert report.status == "valid"
    assert report.admissible_for_training
