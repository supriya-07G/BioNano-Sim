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
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
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


# --- Static frontend ---------------------------------------------------------
# Serves a Vite build if one has been copied to backend/app/static. Absent in
# a normal checkout, in which case the API behaves exactly as before and Vite
# serves the frontend on :5173, or Vercel serves it in production.
#
# Kept because it is the escape hatch when CORS is inconvenient: build the
# frontend into that directory and the app and API share an origin, so the
# relative /api/v1 base works with no cross-origin configuration at all.
STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_INDEX = STATIC_DIR / "index.html"
SERVING_FRONTEND = STATIC_INDEX.is_file()

if SERVING_FRONTEND:
    # Hashed build assets, mounted explicitly so they never reach the catch-all.
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")


# response_model=None is required: FastAPI otherwise tries to build a response
# model from the union return annotation, and FileResponse is not a valid
# Pydantic field type, so the app fails to import at all.
@app.get("/", include_in_schema=False, response_model=None)
def root() -> FileResponse | dict[str, str]:
    if SERVING_FRONTEND:
        return FileResponse(STATIC_INDEX)
    return {
        "app": settings.app_name,
        "version": settings.version,
        "docs": "/docs",
        "api": settings.api_prefix,
        "scientific_status": "MVP — see /api/v1/model and /api/v1/system/readiness",
    }


if SERVING_FRONTEND:

    @app.get("/{asset_path:path}", include_in_schema=False)
    def spa_fallback(asset_path: str) -> FileResponse:
        """Serve a real file if one exists, else index.html for a client route.

        Registered last, so /api/v1/*, /docs and /openapi.json still match their
        own routes first. This only catches paths no route claimed.
        """
        candidate = (STATIC_DIR / asset_path).resolve()
        # Containment check: a crafted path must not escape the build output.
        if asset_path and candidate.is_file() and STATIC_DIR in candidate.parents:
            return FileResponse(candidate)
        return FileResponse(STATIC_INDEX)
