"""FastAPI application entrypoint.

Startup deliberately never fails hard. The ML bundle and OpenMM are both probed
at boot and their status is recorded, but a missing component leaves the API up
with an accurate ``/system/readiness`` report rather than a crashed process —
which is what lets the frontend show precise indicators instead of a blank page.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.router import api_router
from app.config import settings
from app.core.exceptions import (
    BioNanoError,
    bionano_exception_handler,
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.core.logging import configure_logging, get_logger

logger = get_logger("bionano.main")

DESCRIPTION = """
**BioNano-Sim** — AI-assisted stress testing for protein nanomachines in deep space.

This API combines three clearly separated capabilities:

* **ML Prediction** — a degradation estimate from a *mock public-data bootstrap
  model* (`MOCK_PUBLIC_DATA_BOOTSTRAP`). Labels are a synthetic proxy, not
  experimental measurements. The target is per-residue; protein-level figures are
  aggregated by this service and labelled as such.
* **Rapid OpenMM Simulation** — a real but very short molecular-dynamics run in
  implicit solvent. Standard OpenMM does **not** model ionising radiation: no
  particle tracks, energy deposition or bond scission are simulated.
* **Structural analysis** — RMSD, RMSF, radius of gyration and energies computed
  from the real trajectory, plus a clearly-labelled *degradation proxy* that
  BioNano-Sim derives from structural drift.

BioNano-Sim does not claim that proteins replace silicon electronics. It examines
whether selected proteins could serve as nanoscale mechanical components.
"""


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    settings.ensure_runtime_dirs()
    logger.info("Starting %s v%s", settings.app_name, settings.version)

    # Load the model once, at boot, so the first request is not slow. Failures
    # are recorded and surfaced through readiness, never raised.
    try:
        from app.ml.loader import get_model

        state = get_model()
        if state.available:
            logger.info(
                "ML model ready: %s (%s)", state.model_version, state.scientific_status
            )
        else:
            logger.warning("ML model unavailable: %s", state.load_error)
    except Exception:  # noqa: BLE001
        logger.exception("Unexpected error while loading the ML model at startup")

    try:
        from app.simulation.validators import openmm_availability

        info = openmm_availability()
        logger.info("Simulation engine: %s", info["detail"])
    except Exception:  # noqa: BLE001
        logger.exception("Unexpected error while probing OpenMM at startup")

    yield

    try:
        from app.simulation.job_manager import get_job_manager

        get_job_manager().shutdown()
        logger.info("Job manager shut down")
    except Exception:  # noqa: BLE001
        logger.exception("Error during job manager shutdown")


app = FastAPI(
    title=f"{settings.app_name} API",
    description=DESCRIPTION,
    version=settings.version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Accept"],
    expose_headers=["Content-Disposition"],
)


@app.middleware("http")
async def attach_request_id(request: Request, call_next):  # type: ignore[no-untyped-def]
    """Give every request an id so error envelopes are traceable to a log line."""
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


app.add_exception_handler(BioNanoError, bionano_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

app.include_router(api_router, prefix=settings.api_prefix)


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {
        "app": settings.app_name,
        "version": settings.version,
        "docs": "/docs",
        "api": settings.api_prefix,
        "scientific_status": "MVP — see /api/v1/model and /api/v1/system/readiness",
    }
