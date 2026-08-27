"""Simulation configuration validation, job lifecycle, and reporting.

The live-run test is marked ``slow`` and is skipped when OpenMM is unavailable,
so the suite still passes on a machine without it — which is exactly the
degradation behaviour the API promises.
"""

from __future__ import annotations

import time

import pytest


# --------------------------------------------------------------------------- #
# Presets
# --------------------------------------------------------------------------- #
def test_presets_declare_their_scientific_label_and_limits(client, api):
    presets = client.get(f"{api}/simulation/presets").json()
    ids = {p["preset_id"] for p in presets}
    assert ids == {"rapid_demo", "extended_demo", "minimisation_only"}

    for preset in presets:
        assert preset["scientific_label"], "every preset must state its result label"
        assert preset["limitations"], "every preset must state its limitations"
        # The radiation disclaimer must be attached to every preset.
        assert any("does not model ionising" in limit for limit in preset["limitations"])
        assert preset["simulated_time_ps"] >= 0

    rapid = next(p for p in presets if p["preset_id"] == "rapid_demo")
    assert rapid["is_default"] is True
    assert rapid["scientific_label"] == "Rapid OpenMM Simulation"
    assert rapid["solvent"] == "implicit_gbn2"
    assert rapid["nonbonded_cutoff_nm"] == 1.2


def test_rapid_demo_stays_within_configured_safety_limits(client, api):
    from app.config import settings

    rapid = next(
        p for p in client.get(f"{api}/simulation/presets").json()
        if p["preset_id"] == "rapid_demo"
    )
    assert rapid["production_steps"] <= settings.max_production_steps
    assert rapid["minimisation_steps"] <= settings.max_minimisation_steps
    # Picoseconds, not nanoseconds: the honest scale of a demo run.
    assert rapid["simulated_time_ps"] < 100


def test_unknown_preset_is_refused(client, api):
    response = client.post(
        f"{api}/simulations",
        json={
            "pdb_id": "1UBQ",
            "scenario_id": "GCR_DEEP_SPACE_REFERENCE",
            "preset_id": "warp_speed",
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "UNKNOWN_PRESET"


# --------------------------------------------------------------------------- #
# Engine availability
# --------------------------------------------------------------------------- #
def test_engine_health_reports_openmm_and_a_trajectory_reader(client, api):
    body = client.get(f"{api}/simulation/engine").json()
    assert "openmm" in body and "mdtraj" in body
    assert body["max_concurrent_jobs"] == 1
    # A trajectory reader is always available, MDTraj or the built-in one.
    assert body["trajectory_analysis"]


def test_missing_openmm_is_reported_as_503_not_a_crash(monkeypatch, client, api):
    """Simulate an OpenMM-less machine: the API must degrade, not fail."""
    import app.simulation.validators as validators

    monkeypatch.setattr(
        validators,
        "openmm_availability",
        lambda: {
            "available": False,
            "version": None,
            "platforms": [],
            "detail": "OpenMM is not usable: ImportError: No module named 'openmm'",
            "remediation": "pip install openmm==8.6.0",
        },
    )
    response = client.post(
        f"{api}/simulations",
        json={"pdb_id": "1UBQ", "scenario_id": "GCR_DEEP_SPACE_REFERENCE"},
    )
    assert response.status_code == 503
    error = response.json()["error"]
    assert error["code"] == "SIMULATION_ENGINE_UNAVAILABLE"
    assert "pip install openmm" in " ".join(str(d) for d in error["details"])


def test_readiness_still_answers_when_openmm_is_missing(monkeypatch, client, api):
    # simulation_service imported the symbol at module load, so patch it there.
    import app.services.simulation_service as sim_service

    monkeypatch.setattr(
        sim_service,
        "openmm_availability",
        lambda: {
            "available": False, "version": None, "platforms": [],
            "detail": "OpenMM is not usable.", "remediation": "pip install openmm==8.6.0",
        },
    )
    body = client.get(f"{api}/system/readiness").json()
    assert body["status"] in ("not_ready", "degraded")
    engine = next(c for c in body["components"] if c["name"] == "simulation_engine")
    assert engine["ready"] is False
    # The protein registry and model must still be reported as working.
    registry = next(c for c in body["components"] if c["name"] == "protein_registry")
    assert registry["ready"] is True


# --------------------------------------------------------------------------- #
# Request validation
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "payload,status,code",
    [
        ({"scenario_id": "GCR_DEEP_SPACE_REFERENCE"}, 422, None),
        ({"pdb_id": "1UBQ", "upload_id": "a" * 32, "scenario_id": "GCR_DEEP_SPACE_REFERENCE"}, 422, None),
        ({"pdb_id": "1UBQ", "scenario_id": "NOPE"}, 404, "NOT_FOUND"),
        ({"pdb_id": "1UBQ", "scenario_id": "GCR_DEEP_SPACE_REFERENCE", "chain_id": "Z"}, 400, "CHAIN_NOT_FOUND"),
        ({"pdb_id": "1UBQ", "scenario_id": "GCR_DEEP_SPACE_REFERENCE", "temperature_kelvin": 50}, 400, "TEMPERATURE_OUT_OF_RANGE"),
        ({"pdb_id": "1UBQ", "scenario_id": "GCR_DEEP_SPACE_REFERENCE", "temperature_kelvin": 700}, 400, "TEMPERATURE_OUT_OF_RANGE"),
        ({"pdb_id": "1UBQ", "scenario_id": "GCR_DEEP_SPACE_REFERENCE", "temperature_kelvin": -1}, 422, None),
    ],
)
def test_invalid_simulation_requests_are_refused(client, api, payload, status, code):
    response = client.post(f"{api}/simulations", json=payload)
    assert response.status_code == status, response.text
    if code:
        assert response.json()["error"]["code"] == code


def test_temperature_bounds_explain_why(client, api):
    response = client.post(
        f"{api}/simulations",
        json={
            "pdb_id": "1UBQ",
            "scenario_id": "GCR_DEEP_SPACE_REFERENCE",
            "temperature_kelvin": 50,
        },
    )
    message = response.json()["error"]["message"]
    assert "100-500 K" in message
    assert "implicit-solvent" in message or "integrator" in message


def test_dose_and_force_produce_provenance_warnings(client, api, openmm_available):
    if not openmm_available:
        pytest.skip("OpenMM is required to accept a job")
    from app.schemas.simulation import SimulationRequest
    from app.services.protein_service import structure_path
    from app.simulation.validators import validate_simulation_request

    request = SimulationRequest(
        pdb_id="1UBQ",
        scenario_id="GCR_DEEP_SPACE_REFERENCE",
        dose=2.5,
        mechanical_force_pn=150.0,
    )
    _, warnings = validate_simulation_request(request, structure_path("1UBQ"))
    joined = " ".join(warnings)
    assert "does not model ionising radiation" in joined
    assert "no external pulling force" in joined


def test_untrained_scenario_is_allowed_for_simulation(client, api, openmm_available):
    """The ML model refuses these, but the physics run must still work."""
    if not openmm_available:
        pytest.skip("OpenMM is required to accept a job")
    from app.schemas.simulation import SimulationRequest
    from app.services.protein_service import structure_path
    from app.simulation.validators import validate_simulation_request

    request = SimulationRequest(
        pdb_id="1UBQ", scenario_id="BASELINE_NO_RADIATION", preset_id="minimisation_only"
    )
    _, warnings = validate_simulation_request(request, structure_path("1UBQ"))
    assert any("no ML degradation estimate" in w for w in warnings)


# --------------------------------------------------------------------------- #
# Job lifecycle
# --------------------------------------------------------------------------- #
def test_unknown_job_id_is_a_clean_404(client, api):
    response = client.get(f"{api}/simulations/{'0' * 32}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_malformed_job_id_is_refused(client, api):
    response = client.get(f"{api}/simulations/..%2f..%2fmodels")
    assert response.status_code in (400, 404)


def test_job_id_traversal_is_blocked_at_the_security_layer():
    from app.core.exceptions import UnsafePathError
    from app.core.security import validate_job_id

    for bad in ["../../etc/passwd", "abc", "", "g" * 32, "../" * 5]:
        with pytest.raises(UnsafePathError):
            validate_job_id(bad)


def test_results_for_a_nonexistent_job_is_404(client, api):
    response = client.get(f"{api}/simulations/{'1' * 32}/results")
    assert response.status_code == 404


def test_history_endpoint_reads_from_disk(client, api):
    response = client.get(f"{api}/simulations")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


# --------------------------------------------------------------------------- #
# Precomputed fallback
# --------------------------------------------------------------------------- #
def test_precomputed_result_is_labelled_as_such(client, api):
    listing = client.get(f"{api}/precomputed").json()
    if not listing["available"]:
        pytest.skip("no precomputed result bundled")
    pdb_id = listing["available"][0]

    body = client.get(f"{api}/precomputed/{pdb_id}/results").json()
    assert body["engine"] == "precomputed"
    assert body["result_label"] == "Precomputed OpenMM Result"
    # The very first warning must say it is not a live run.
    assert "PRECOMPUTED" in body["warnings"][0]
    assert "not a simulation run on this machine now" in body["warnings"][0]


def test_precomputed_structure_is_downloadable(client, api):
    listing = client.get(f"{api}/precomputed").json()
    if not listing["available"]:
        pytest.skip("no precomputed result bundled")
    response = client.get(f"{api}/precomputed/{listing['available'][0]}/structure")
    assert response.status_code == 200
    assert "ATOM" in response.text


# --------------------------------------------------------------------------- #
# The real thing
# --------------------------------------------------------------------------- #
@pytest.mark.slow
def test_minimisation_only_run_completes_and_reports_no_trajectory(
    client, api, openmm_available
):
    """The fastest real OpenMM path. Must succeed and must NOT invent a proxy."""
    if not openmm_available:
        pytest.skip("OpenMM unavailable")

    response = client.post(
        f"{api}/simulations",
        json={
            "pdb_id": "1UBQ",
            "scenario_id": "GCR_DEEP_SPACE_REFERENCE",
            "preset_id": "minimisation_only",
            "random_seed": 7,
        },
    )
    if response.status_code == 409:
        pytest.skip("another job is already running")
    assert response.status_code == 202, response.text
    job_id = response.json()["job_id"]

    deadline = time.monotonic() + 240
    status = {}
    while time.monotonic() < deadline:
        status = client.get(f"{api}/simulations/{job_id}").json()
        if status["status"] in ("completed", "failed", "cancelled"):
            break
        time.sleep(0.4)

    assert status["status"] == "completed", (
        f"{status.get('error_code')}: {status.get('error_message')}"
    )
    assert status["progress"] == 1.0

    results = client.get(f"{api}/simulations/{job_id}/results").json()
    metrics = results["metrics"]
    assert metrics["dynamics_run"] is False
    assert metrics["n_frames"] == 0
    # Minimisation lowers the potential energy: a real physical check.
    assert metrics["minimisation"]["delta_kj_mol"] < 0
    # No dynamics means no fabricated drift proxy.
    assert "degradation_proxy" not in metrics or not metrics.get("degradation_proxy")
    assert results["result_label"] == "Energy Minimisation Only (no dynamics)"

    # Reports must still generate for a dynamics-free run.
    assert client.get(f"{api}/reports/{job_id}.json").status_code == 200
    assert client.get(f"{api}/reports/{job_id}.csv").status_code == 200

    client.delete(f"{api}/simulations/{job_id}")


@pytest.mark.slow
def test_failed_job_is_never_marked_completed(client, api, openmm_available):
    """A structure OpenMM cannot build must land in 'failed' with a retry hint."""
    if not openmm_available:
        pytest.skip("OpenMM unavailable")

    # A 5-residue poly-alanine fragment with no terminal caps and CB-only side
    # chains: amber14 has no matching template, so system construction fails.
    broken = "\n".join(
        f"ATOM  {i:>5}  CA  UNK A{i:>4}       {i * 3.8:>8.3f}   0.000   0.000  1.00  0.00           C"
        for i in range(1, 8)
    ) + "\nTER\nEND\n"

    upload = client.post(
        f"{api}/proteins/upload", files={"file": ("unk.pdb", broken, "chemical/x-pdb")}
    )
    if upload.status_code != 200:
        # Rejected at upload validation, which is also an acceptable outcome.
        assert upload.json()["error"]["code"] in ("NO_PROTEIN_CHAIN", "UNPARSEABLE")
        return

    response = client.post(
        f"{api}/simulations",
        json={
            "upload_id": upload.json()["upload_id"],
            "scenario_id": "GCR_DEEP_SPACE_REFERENCE",
            "preset_id": "minimisation_only",
        },
    )
    if response.status_code != 202:
        assert response.status_code == 400
        return

    job_id = response.json()["job_id"]
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        status = client.get(f"{api}/simulations/{job_id}").json()
        if status["status"] in ("completed", "failed", "cancelled"):
            break
        time.sleep(0.4)

    assert status["status"] != "completed", "a broken structure must not report success"
    if status["status"] == "failed":
        assert status["error_code"]
        assert status["error_message"]
        assert status["retry_hint"]["preset_id"] == "minimisation_only"
        # Results must refuse to serve for a failed job.
        assert client.get(f"{api}/simulations/{job_id}/results").status_code == 404
    client.delete(f"{api}/simulations/{job_id}")
