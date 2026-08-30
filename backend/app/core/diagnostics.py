"""Runtime diagnostics for team testing and demos (issue #23).

The acceptance criterion is behavioural: a teammate should diagnose a failed
demo from one output, without opening four runtime directories and correlating
timestamps by eye. So this assembles job outcomes, stage timings, the resolved
OpenMM platform, storage pressure and log state into a single document.

**Nothing here returns uploaded structures or file contents.** A support bundle
that quietly carries someone's protein upload is a privacy problem, so the
payload is counts, sizes, statuses and error *messages* only. Anything that
could hold a path, a filename or a user value goes through :func:`redact`.
"""

from __future__ import annotations

import platform
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import settings
from app.core.storage import storage_report

#: Substrings that mark a key as carrying a user value rather than a metric.
SENSITIVE_KEY_PARTS = (
    "path", "file", "filename", "dir", "directory", "upload", "token",
    "secret", "key", "password", "email", "sequence",
)

REDACTED = "[redacted]"

#: Absolute paths leak the operator's home directory and username into any
#: bundle that gets shared. Replaced wherever they appear in free text.
_HOME_PATTERN = re.compile(
    r"(?:[A-Za-z]:\\Users\\[^\\\s]+|/(?:home|Users)/[^/\s]+)", re.IGNORECASE
)


def redact(value: Any, *, key: str = "") -> Any:
    """Strip user values from anything bound for a support bundle."""
    lowered = key.lower()
    if any(part in lowered for part in SENSITIVE_KEY_PARTS):
        return REDACTED
    if isinstance(value, dict):
        return {k: redact(v, key=k) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v, key=key) for v in value]
    if isinstance(value, str):
        return _HOME_PATTERN.sub(REDACTED, value)
    return value


def _duration_seconds(start: str | None, end: str | None) -> float | None:
    if not start or not end:
        return None
    try:
        a = datetime.fromisoformat(str(start).replace("Z", "+00:00"))
        b = datetime.fromisoformat(str(end).replace("Z", "+00:00"))
    except ValueError:
        return None
    if a.tzinfo is None:
        a = a.replace(tzinfo=UTC)
    if b.tzinfo is None:
        b = b.replace(tzinfo=UTC)
    return round((b - a).total_seconds(), 3)


def _is_stale(payload: dict[str, Any]) -> bool:
    """A job still 'running' with nothing written for an hour is stale.

    Distinguishing this from 'failed' matters: a stale job usually means the
    process died without ever writing a terminal status, which looks like a
    hang to a user and is invisible in the status counts otherwise.
    """
    if str(payload.get("status", "")).lower() not in {"running", "queued"}:
        return False
    stamp = payload.get("updated_at") or payload.get("started_at") \
        or payload.get("created_at")
    if not stamp:
        return True
    try:
        seen = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
    except ValueError:
        return True
    if seen.tzinfo is None:
        seen = seen.replace(tzinfo=UTC)
    return (datetime.now(UTC) - seen).total_seconds() > 3600


def job_diagnostics(limit: int = 200) -> dict[str, Any]:
    from app.utils.files import read_json  # noqa: PLC0415 - avoids a cycle

    counts: dict[str, int] = {}
    durations: list[float] = []
    stale: list[str] = []
    failures: list[dict[str, Any]] = []
    platforms: dict[str, int] = {}
    unreadable = 0

    if settings.jobs_dir.is_dir():
        for entry in sorted(settings.jobs_dir.iterdir())[:limit]:
            if not entry.is_dir():
                continue
            try:
                payload = read_json(entry / "status.json") or {}
            except Exception:  # noqa: BLE001
                unreadable += 1
                continue

            status = str(payload.get("status", "unknown")).lower()
            counts[status] = counts.get(status, 0) + 1

            elapsed = _duration_seconds(
                payload.get("started_at"), payload.get("finished_at")
            )
            if elapsed is not None:
                durations.append(elapsed)

            if _is_stale(payload):
                stale.append(entry.name)

            if status == "failed":
                failures.append({
                    "job_id": entry.name,
                    # The message is the diagnostic value; any path inside it
                    # is not, and is stripped.
                    "error": redact(payload.get("error_message") or "unknown"),
                    "finished_at": payload.get("finished_at"),
                })

            resolved = payload.get("platform") or payload.get("openmm_platform")
            if resolved:
                platforms[str(resolved)] = platforms.get(str(resolved), 0) + 1

    durations.sort()
    return {
        "counts_by_status": counts,
        "total": sum(counts.values()),
        "unreadable_status_files": unreadable,
        "stale_jobs": stale,
        "recent_failures": failures[-10:],
        "platforms_used": platforms,
        "duration_seconds": {
            "n": len(durations),
            "min": durations[0] if durations else None,
            "median": durations[len(durations) // 2] if durations else None,
            "max": durations[-1] if durations else None,
        },
    }


def engine_diagnostics() -> dict[str, Any]:
    """The resolved platform and why, which is the first thing to check."""
    info: dict[str, Any] = {}
    try:
        from app.simulation.validators import openmm_availability  # noqa: PLC0415

        info = dict(openmm_availability())
    except Exception as exc:  # noqa: BLE001
        info = {"available": False, "detail": f"{type(exc).__name__}: {exc}"}

    try:
        from openmm import Platform  # noqa: PLC0415

        info["platforms_available"] = [
            Platform.getPlatform(i).getName()
            for i in range(Platform.getNumPlatforms())
        ]
        info["fastest_platform"] = max(
            (Platform.getPlatform(i) for i in range(Platform.getNumPlatforms())),
            key=lambda p: p.getSpeed(),
        ).getName()
    except Exception:  # noqa: BLE001
        info["platforms_available"] = None
        info["fastest_platform"] = None
    return info


def log_diagnostics() -> dict[str, Any]:
    """Log sizes only. Contents can hold uploaded filenames."""
    logs: list[dict[str, Any]] = []
    if settings.logs_dir.is_dir():
        for entry in sorted(settings.logs_dir.glob("*")):
            if entry.is_file():
                try:
                    stat = entry.stat()
                except OSError:
                    continue
                logs.append({
                    "name": entry.name,
                    "bytes": stat.st_size,
                    "modified_utc": datetime.fromtimestamp(
                        stat.st_mtime, tz=UTC).isoformat(),
                })
    return {
        "files": logs,
        "total_bytes": sum(item["bytes"] for item in logs),
        "rotation_note": (
            "Logs are not rotated automatically. Delete or archive them when "
            "the storage report warns; they are excluded from job retention "
            "because they outlive individual jobs."
        ),
    }


def collect(*, include_environment: bool = True) -> dict[str, Any]:
    """The whole diagnostics document. Safe to paste into an issue."""
    storage = storage_report()
    payload: dict[str, Any] = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "app": {"name": settings.app_name, "version": settings.version},
        "jobs": job_diagnostics(),
        "engine": engine_diagnostics(),
        "storage": storage.as_dict(),
        "logs": log_diagnostics(),
        "warnings": storage.warnings(),
    }
    if include_environment:
        payload["environment"] = {
            "python": platform.python_version(),
            "os": f"{platform.system()} {platform.release()}",
            "machine": platform.machine(),
        }
    # One final pass: nothing reaches a bundle without going through redact.
    return redact(payload)


def support_bundle(*, include_uploads: bool = False) -> dict[str, Any]:
    """Diagnostics plus an explicit statement of what was left out.

    ``include_uploads`` names the uploaded structures rather than embedding
    them, and is off by default. A support bundle that quietly carries
    someone's protein upload is a privacy problem, and a bundle that does not
    say what it omitted invites the reader to assume it omitted nothing.
    """
    payload = collect()
    payload["bundle"] = {
        "includes_uploaded_structures": include_uploads,
        "excluded": [
            "uploaded structure files",
            "trajectory and structure contents",
            "log file contents",
            "absolute filesystem paths",
        ],
    }
    if include_uploads and settings.uploads_dir.is_dir():
        payload["bundle"]["uploaded_structure_count"] = sum(
            1 for p in settings.uploads_dir.rglob("*") if p.is_file()
        )
    return payload


def write_support_bundle(destination: Path, *, include_uploads: bool = False) -> Path:
    import json  # noqa: PLC0415

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(support_bundle(include_uploads=include_uploads),
                   indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    return destination
