"""Logging setup: console for the developer, rotating file for job forensics."""

from __future__ import annotations

import logging
import logging.handlers
import sys

from app.config import settings

_CONFIGURED = False
_FMT = "%(asctime)s %(levelname)-7s [%(name)s] %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"


def configure_logging() -> None:
    """Idempotent root-logger setup."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    settings.ensure_runtime_dirs()
    root = logging.getLogger()
    root.setLevel(settings.log_level.upper())

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter(_FMT, _DATEFMT))
    root.addHandler(console)

    try:
        file_handler = logging.handlers.RotatingFileHandler(
            settings.logs_dir / "backend.log",
            maxBytes=2_000_000,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(logging.Formatter(_FMT, _DATEFMT))
        root.addHandler(file_handler)
    except OSError:
        # A read-only runtime directory must not stop the API from booting.
        root.warning("Could not open runtime log file; continuing with console only.")

    # Uvicorn's access log is noisy under 1 s job polling.
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    configure_logging()
    return logging.getLogger(name)
