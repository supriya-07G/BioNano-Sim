"""Error taxonomy and the single JSON error envelope used by every endpoint.

Envelope (spec 9):

    {"error": {"code": ..., "message": ..., "details": [...], "request_id": ...}}
"""

from __future__ import annotations

from typing import Any

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class COSMORAError(Exception):
    """Base class for every deliberate application error.

    ``code`` is a stable machine-readable identifier the frontend switches on;
    ``message`` is shown to the user and must stay human-readable.
    """

    code = "INTERNAL_ERROR"
    http_status = status.HTTP_500_INTERNAL_SERVER_ERROR

    def __init__(
        self,
        message: str,
        *,
        details: list[Any] | None = None,
        code: str | None = None,
        http_status: int | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or []
        if code is not None:
            self.code = code
        if http_status is not None:
            self.http_status = http_status


class NotFoundError(COSMORAError):
    code = "NOT_FOUND"
    http_status = status.HTTP_404_NOT_FOUND


class ValidationFailedError(COSMORAError):
    code = "VALIDATION_FAILED"
    http_status = status.HTTP_422_UNPROCESSABLE_ENTITY


class ModelUnavailableError(COSMORAError):
    """The ML bundle could not be loaded, so predictions cannot be served.

    Returned as 503 rather than 500: the rest of the API keeps working and the
    frontend renders a readiness indicator instead of an error page.
    """

    code = "MODEL_UNAVAILABLE"
    http_status = status.HTTP_503_SERVICE_UNAVAILABLE


class PredictionError(COSMORAError):
    code = "PREDICTION_FAILED"
    http_status = status.HTTP_400_BAD_REQUEST


class InvalidProteinError(COSMORAError):
    code = "INVALID_PROTEIN_FILE"
    http_status = status.HTTP_400_BAD_REQUEST


class InvalidSimulationInputError(COSMORAError):
    code = "INVALID_SIMULATION_INPUT"
    http_status = status.HTTP_400_BAD_REQUEST


class SimulationEngineUnavailableError(COSMORAError):
    """OpenMM is missing or unusable on this machine."""

    code = "SIMULATION_ENGINE_UNAVAILABLE"
    http_status = status.HTTP_503_SERVICE_UNAVAILABLE


class JobConflictError(COSMORAError):
    """Concurrency limit reached, or an illegal state transition was requested."""

    code = "JOB_CONFLICT"
    http_status = status.HTTP_409_CONFLICT


class UnsafePathError(COSMORAError):
    code = "UNSAFE_PATH"
    http_status = status.HTTP_400_BAD_REQUEST


class InsufficientStorageError(COSMORAError):
    """Not enough disk or quota headroom to start a job (issue #26).

    Raised at submission rather than mid-run: a rejected submission is an
    error message the user can act on, while a job that dies at step 18,000
    because the disk filled is lost work.
    """

    code = "INSUFFICIENT_STORAGE"
    http_status = status.HTTP_507_INSUFFICIENT_STORAGE


# --------------------------------------------------------------------------- #
# Envelope helpers
# --------------------------------------------------------------------------- #
def error_body(
    code: str,
    message: str,
    request_id: str,
    details: list[Any] | None = None,
) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details or [],
            "request_id": request_id,
        }
    }


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


async def COSMORA_exception_handler(request: Request, exc: COSMORAError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.http_status,
        content=error_body(exc.code, exc.message, _request_id(request), exc.details),
    )


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    code = {
        status.HTTP_404_NOT_FOUND: "NOT_FOUND",
        status.HTTP_405_METHOD_NOT_ALLOWED: "METHOD_NOT_ALLOWED",
        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE: "PAYLOAD_TOO_LARGE",
    }.get(exc.status_code, "HTTP_ERROR")
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(code, str(exc.detail), _request_id(request)),
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Flatten Pydantic errors into the standard envelope's ``details``."""
    details = [
        {
            "field": ".".join(str(p) for p in err.get("loc", ()) if p != "body"),
            "message": err.get("msg", ""),
            "type": err.get("type", ""),
        }
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_body(
            "VALIDATION_FAILED",
            "One or more request fields are invalid.",
            _request_id(request),
            details,
        ),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Last resort. The message stays generic; the traceback goes to the log."""
    from app.core.logging import get_logger

    get_logger("COSMORA.unhandled").exception(
        "Unhandled exception on %s %s", request.method, request.url.path
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_body(
            "INTERNAL_ERROR",
            "An unexpected internal error occurred. See the server log for details.",
            _request_id(request),
        ),
    )
