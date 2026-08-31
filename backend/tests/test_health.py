"""Health and readiness endpoints."""

from __future__ import annotations


def test_health_returns_ok(client, api):
    response = client.get(f"{api}/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["app"] == "COSMORA"
    assert body["time_utc"]


def test_root_points_at_docs(client):
    body = client.get("/").json()
    assert body["docs"] == "/docs"
    assert body["api"] == "/api/v1"


def test_readiness_reports_every_subsystem(client, api):
    response = client.get(f"{api}/system/readiness")
    assert response.status_code == 200
    body = response.json()

    names = {c["name"] for c in body["components"]}
    assert names >= {
        "ml_model",
        "simulation_engine",
        "trajectory_analysis",
        "protein_registry",
        "scenarios",
        "runtime_storage",
        "precomputed_fallback",
    }
    for component in body["components"]:
        assert component["status"] in {"ready", "degraded", "unavailable"}
        assert component["detail"], f"{component['name']} must explain its status"
        # An unready component must tell the operator how to fix it.
        if not component["ready"]:
            assert component["remediation"], (
                f"{component['name']} is not ready but offers no remediation"
            )


def test_readiness_counts_are_consistent(client, api):
    counts = client.get(f"{api}/system/readiness").json()["counts"]
    assert counts["approved_proteins"] >= 5
    assert counts["ml_supported_scenarios"] <= counts["scenarios"]
    assert counts["completed_jobs"] <= counts["total_jobs"]


def test_request_id_header_is_echoed(client, api):
    response = client.get(f"{api}/health", headers={"X-Request-ID": "test-req-42"})
    assert response.headers["X-Request-ID"] == "test-req-42"


def test_unknown_route_uses_the_error_envelope(client, api):
    response = client.get(f"{api}/does-not-exist")
    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "NOT_FOUND"
    assert "request_id" in error
    assert isinstance(error["details"], list)


def test_cors_origins_accept_a_comma_separated_env_value(monkeypatch):
    """A split frontend/backend deployment sets this, and it used to crash boot.

    pydantic-settings JSON-decodes complex-typed fields from the environment
    before validators run, so a comma-separated value raised SettingsError and
    the app never started. NoDecode on the field is what lets the validator see
    the raw string.
    """
    from app.config import Settings

    monkeypatch.setenv(
        "COSMORA_CORS_ORIGINS", "https://a.example.com, https://b.example.com"
    )
    assert Settings().cors_origins == [
        "https://a.example.com",
        "https://b.example.com",
    ]


def test_cors_origins_default_to_local_dev(monkeypatch):
    from app.config import Settings

    monkeypatch.delenv("COSMORA_CORS_ORIGINS", raising=False)
    assert "http://localhost:5173" in Settings().cors_origins
