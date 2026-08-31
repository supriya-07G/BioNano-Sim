"""The demo script's results summary (backend-ci openmm-smoke).

CI runs ``scripts/run_demo_simulation.py --preset-id minimisation_only``. That
preset runs no dynamics, so the engine emits no RMSD, RMSF, radius of gyration
or temperature. The script printed all four unconditionally and died on
``KeyError: 'rmsd_nm'`` -- after the simulation had already completed
successfully. A reporting crash was surfacing as a simulation failure, and
nothing caught it because the code sat inside main(), which needs a real
OpenMM run to reach.

These tests exercise the summary directly, with both payload shapes.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "run_demo_simulation.py"


def _load_script():
    """Import the script by path; it is not on a package path."""
    spec = importlib.util.spec_from_file_location("run_demo_simulation", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def script():
    return _load_script()


def _base(metrics: dict, *, proxy_pct: float | None) -> dict:
    return {
        "result_label": "Test Result",
        "metadata": {"topology": {"platform": "CPU"}},
        "metrics": metrics,
        "stability_summary": {"verdict": "not_assessed"},
        "comparison": {
            "ml_degradation_percent": 49.5,
            "simulation_degradation_proxy_percent": proxy_pct,
            "difference_percentage_points": None if proxy_pct is None else 1.0,
            "agreement": "unavailable" if proxy_pct is None else "divergent",
        },
    }


MINIMISATION_ONLY = _base(
    {
        # Exactly the keys a minimisation-only run emits. Nothing else.
        "dynamics_run": False,
        "engine": "openmm",
        "n_frames": 0,
        "preset_id": "minimisation_only",
        "result_label": "Energy Minimisation Only (no dynamics)",
        "simulated_time_ps": 0.0,
        "minimisation": {
            "potential_energy_before_kj_mol": -12541.6,
            "potential_energy_after_kj_mol": -15209.8,
            "delta_kj_mol": -2668.2,
            "max_iterations": 1000,
        },
    },
    proxy_pct=None,
)

WITH_DYNAMICS = _base(
    {
        "dynamics_run": True,
        "engine": "openmm",
        "n_frames": 60,
        "preset_id": "rapid_demo",
        "result_label": "Rapid OpenMM Simulation",
        "simulated_time_ps": 12.0,
        "rmsd_nm": {"final": 0.1484},
        "rmsf_nm": {"mean": 0.0603},
        "radius_of_gyration_nm": {"relative_change": 0.0008},
        "temperature_kelvin": {"mean": 291.7},
        "degradation_proxy": {"percent": 17.6, "label": "proxy"},
    },
    proxy_pct=17.6,
)


def test_minimisation_only_summary_does_not_raise(script, capsys):
    """The regression: this raised KeyError('rmsd_nm') and failed CI."""
    script.print_results_summary(MINIMISATION_ONLY)

    out = capsys.readouterr().out
    assert "minimisation-only preset" in out
    assert "-2668.2" in out, "the energy drop is the result worth printing here"
    # Nothing may claim a trajectory metric that was never computed.
    for absent in ("final RMSD", "mean RMSF", "Rg change", "mean temperature"):
        assert absent not in out


def test_minimisation_only_summary_reports_no_comparison(script, capsys):
    script.print_results_summary(MINIMISATION_ONLY)
    out = capsys.readouterr().out
    assert "no simulation proxy to compare against" in out
    # A null proxy must not be printed as if it were a measurement.
    assert "None %" not in out


def test_dynamics_summary_still_reports_the_trajectory(script, capsys):
    script.print_results_summary(WITH_DYNAMICS)
    out = capsys.readouterr().out
    assert "final RMSD       : 0.1484 nm" in out
    assert "mean RMSF" in out
    assert "17.6 %" in out
    assert "minimisation-only" not in out


def test_summary_tolerates_a_null_degradation_proxy(script, capsys):
    """job_results emits degradation_proxy: null, not a missing key."""
    payload = _base({**WITH_DYNAMICS["metrics"], "degradation_proxy": None}, proxy_pct=None)
    script.print_results_summary(payload)
    assert "drift proxy" in capsys.readouterr().out
