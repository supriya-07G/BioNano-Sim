"""Shared test fixtures.

Tests run against the real model bundle and the real protein registry — the
point of most of them is to prove the *actual* artefacts behave correctly, so
mocking the pipeline would defeat the exercise. Only the runtime job directory
is redirected, so tests never touch a developer's real job history.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

REPO = BACKEND.parent


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO


@pytest.fixture(scope="session")
def client():
    """A TestClient with lifespan run, so the model is loaded once for the session."""
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def api() -> str:
    from app.config import settings

    return settings.api_prefix


@pytest.fixture(scope="session")
def model_state():
    from app.ml.loader import get_model

    return get_model()


@pytest.fixture(scope="session")
def openmm_available() -> bool:
    from app.simulation.validators import openmm_availability

    return bool(openmm_availability()["available"])


@pytest.fixture
def valid_pdb_text() -> str:
    """A minimal but genuinely parseable 5-residue poly-alanine fragment.

    Coordinates are a plausible extended backbone; the file exists to exercise
    upload validation, not to be physically meaningful.
    """
    lines = []
    serial = 1
    for i in range(1, 6):
        x = 3.8 * i
        for name, element, dx, dy, dz in (
            ("N", "N", 0.0, 0.0, 0.0),
            ("CA", "C", 1.45, 0.0, 0.0),
            ("C", "C", 2.45, 1.05, 0.0),
            ("O", "O", 2.10, 2.22, 0.0),
            ("CB", "C", 1.95, -0.80, 1.20),
        ):
            lines.append(
                f"ATOM  {serial:>5}  {name:<3} ALA A{i:>4}    "
                f"{x + dx:>8.3f}{dy:>8.3f}{dz:>8.3f}  1.00  0.00          {element:>2}"
            )
            serial += 1
    lines.append("TER")
    lines.append("END")
    return "\n".join(lines) + "\n"
