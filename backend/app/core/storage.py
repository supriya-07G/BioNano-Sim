"""Runtime storage accounting, quotas and safe cleanup (issues #23 and #26).

Jobs, uploads, trajectories and reports accumulate under ``runtime/``. A single
paired experiment writes hundreds of megabytes of trajectory, so repeated team
use fills a disk quietly and the first symptom is a simulation failing halfway
through for reasons that look nothing like "out of space".

Three rules govern everything here.

**Deletion is opt-in.** Every entry point defaults to a dry run. A function
that removes a user's results by default is a function that will one day remove
them by accident.

**Evidence is not deletable.** ``data/``, ``models/`` and the precomputed
fallback are the artifacts a scientific claim rests on. They are not under
``runtime/``, and :func:`assert_deletable` refuses anything outside it —
including a path that tries to escape via ``..`` or a symlink.

**Admission is checked before work starts, not after.** A job rejected at
submission is an error message; a job that dies at step 18,000 because the disk
filled is lost work.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from app.config import settings

#: Directory trees that hold published evidence. Nothing here is ever a
#: cleanup candidate, and the guard below is belt-and-braces on top of the
#: containment check.
PROTECTED_DIRECTORY_NAMES = ("data", "models", "precomputed")


@dataclass(frozen=True)
class DirectoryUsage:
    """Bytes and file count for one runtime area."""

    name: str
    path: Path
    bytes_used: int
    file_count: int
    entry_count: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "bytes_used": self.bytes_used,
            "megabytes_used": round(self.bytes_used / 1_048_576, 2),
            "file_count": self.file_count,
            "entry_count": self.entry_count,
        }


@dataclass(frozen=True)
class StorageReport:
    areas: list[DirectoryUsage]
    total_bytes: int
    quota_bytes: int
    disk_free_bytes: int
    disk_total_bytes: int
    min_free_bytes: int

    @property
    def over_quota(self) -> bool:
        return self.total_bytes > self.quota_bytes

    @property
    def disk_low(self) -> bool:
        return self.disk_free_bytes < self.min_free_bytes

    @property
    def cleanup_required(self) -> bool:
        return self.over_quota or self.disk_low

    @property
    def quota_used_fraction(self) -> float:
        return self.total_bytes / self.quota_bytes if self.quota_bytes else 0.0

    def warnings(self) -> list[str]:
        messages = []
        if self.over_quota:
            messages.append(
                f"runtime/ is using {self.total_bytes / 1_048_576:,.0f} MB against a "
                f"{self.quota_bytes / 1_048_576:,.0f} MB quota. Run cleanup."
            )
        elif self.quota_used_fraction >= 0.8:
            messages.append(
                f"runtime/ is at {self.quota_used_fraction:.0%} of its quota. "
                "Cleanup will be required soon."
            )
        if self.disk_low:
            messages.append(
                f"only {self.disk_free_bytes / 1_048_576:,.0f} MB free on disk, "
                f"below the {self.min_free_bytes / 1_048_576:,.0f} MB floor."
            )
        return messages

    def as_dict(self) -> dict[str, Any]:
        return {
            "areas": [a.as_dict() for a in self.areas],
            "total_bytes": self.total_bytes,
            "total_megabytes": round(self.total_bytes / 1_048_576, 2),
            "quota_bytes": self.quota_bytes,
            "quota_used_fraction": round(self.quota_used_fraction, 4),
            "over_quota": self.over_quota,
            "disk_free_bytes": self.disk_free_bytes,
            "disk_total_bytes": self.disk_total_bytes,
            "disk_low": self.disk_low,
            "cleanup_required": self.cleanup_required,
            "warnings": self.warnings(),
        }


def directory_usage(name: str, path: Path) -> DirectoryUsage:
    total, files = 0, 0
    if path.is_dir():
        for item in path.rglob("*"):
            if item.is_file():
                try:
                    total += item.stat().st_size
                except OSError:
                    # A file removed mid-walk is not an error worth failing on.
                    continue
                files += 1
    entries = len(list(path.iterdir())) if path.is_dir() else 0
    return DirectoryUsage(name=name, path=path, bytes_used=total,
                          file_count=files, entry_count=entries)


def storage_report() -> StorageReport:
    areas = [
        directory_usage("jobs", settings.jobs_dir),
        directory_usage("uploads", settings.uploads_dir),
        directory_usage("reports", settings.reports_dir),
        directory_usage("logs", settings.logs_dir),
    ]
    total = sum(a.bytes_used for a in areas)
    try:
        usage = shutil.disk_usage(settings.runtime_dir)
        free, capacity = usage.free, usage.total
    except OSError:
        free, capacity = 0, 0
    return StorageReport(
        areas=areas,
        total_bytes=total,
        quota_bytes=settings.runtime_quota_bytes,
        disk_free_bytes=free,
        disk_total_bytes=capacity,
        min_free_bytes=settings.min_free_disk_bytes,
    )


def admission_check(report: StorageReport | None = None) -> tuple[bool, str | None]:
    """May a new job start? Checked before work, not after.

    A job rejected at submission is an error message the user can act on. A job
    that dies at step 18,000 because the disk filled is lost work.
    """
    report = report or storage_report()
    if report.disk_low:
        return False, (
            f"Not enough disk space to start a simulation: "
            f"{report.disk_free_bytes / 1_048_576:,.0f} MB free, "
            f"{report.min_free_bytes / 1_048_576:,.0f} MB required. "
            "Delete old experiments and retry."
        )
    if report.over_quota:
        return False, (
            f"The runtime storage quota is exhausted: "
            f"{report.total_bytes / 1_048_576:,.0f} MB used of "
            f"{report.quota_bytes / 1_048_576:,.0f} MB. "
            "Run cleanup before starting another simulation."
        )
    return True, None


# --------------------------------------------------------------------------- #
# Deletion safety
# --------------------------------------------------------------------------- #
class UnsafeDeletionError(RuntimeError):
    """Raised when a path outside the runtime tree is offered for deletion."""


def assert_deletable(path: Path) -> Path:
    """Refuse anything that is not a real entry inside ``runtime/``.

    Resolves first, so ``..`` traversal and symlinks pointing out of the tree
    are caught rather than followed. Refusing the runtime root itself is
    deliberate: ``rm -rf runtime/`` must not be reachable through this API.
    """
    runtime_root = settings.runtime_dir.resolve()
    resolved = path.resolve()

    if resolved == runtime_root:
        raise UnsafeDeletionError(
            f"refusing to delete the runtime root itself: {resolved}"
        )
    if runtime_root not in resolved.parents:
        raise UnsafeDeletionError(
            f"refusing to delete {resolved}: outside the runtime tree "
            f"({runtime_root}). Published evidence under data/ and models/ is "
            "never a cleanup candidate."
        )
    if any(part in PROTECTED_DIRECTORY_NAMES for part in resolved.parts):
        raise UnsafeDeletionError(
            f"refusing to delete {resolved}: the path crosses a protected "
            f"directory name {PROTECTED_DIRECTORY_NAMES}"
        )
    return resolved


# --------------------------------------------------------------------------- #
# Retention
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class CleanupCandidate:
    job_id: str
    path: Path
    status: str
    age_days: float
    bytes_used: int
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "age_days": round(self.age_days, 2),
            "bytes_used": self.bytes_used,
            "megabytes_used": round(self.bytes_used / 1_048_576, 2),
            "reason": self.reason,
        }


def _retention_days(status: str) -> int | None:
    """None means "keep indefinitely" -- a running job is never a candidate."""
    return {
        "completed": settings.retention_days_completed,
        "failed": settings.retention_days_failed,
        "cancelled": settings.retention_days_cancelled,
    }.get(status)


def _age_days(job_dir: Path, status_payload: dict[str, Any]) -> float:
    stamp = (status_payload.get("finished_at")
             or status_payload.get("created_at"))
    if stamp:
        try:
            finished = datetime.fromisoformat(str(stamp).replace("Z", "+00:00"))
            if finished.tzinfo is None:
                finished = finished.replace(tzinfo=UTC)
            return (datetime.now(UTC) - finished) / timedelta(days=1)
        except ValueError:
            pass
    try:
        mtime = datetime.fromtimestamp(job_dir.stat().st_mtime, tz=UTC)
        return (datetime.now(UTC) - mtime) / timedelta(days=1)
    except OSError:
        return 0.0


def cleanup_candidates() -> list[CleanupCandidate]:
    """Job directories past their retention window, newest kept.

    A job whose ``status.json`` cannot be read is *not* a candidate. Deleting
    something we failed to identify is exactly the mistake this module exists
    to avoid.
    """
    from app.utils.files import read_json  # noqa: PLC0415 - avoids a cycle

    if not settings.jobs_dir.is_dir():
        return []

    candidates: list[CleanupCandidate] = []
    for entry in sorted(settings.jobs_dir.iterdir()):
        if not entry.is_dir():
            continue
        try:
            payload = read_json(entry / "status.json") or {}
        except Exception:  # noqa: BLE001
            continue
        status = str(payload.get("status", "")).lower()
        limit = _retention_days(status)
        if limit is None:
            continue
        age = _age_days(entry, payload)
        if age < limit:
            continue
        candidates.append(CleanupCandidate(
            job_id=entry.name,
            path=entry,
            status=status,
            age_days=age,
            bytes_used=directory_usage(entry.name, entry).bytes_used,
            reason=f"{status} and {age:.1f} days old, past the {limit}-day "
                   f"retention window for {status} jobs",
        ))
    return candidates


def run_cleanup(
    candidates: list[CleanupCandidate] | None = None, *, dry_run: bool = True
) -> dict[str, Any]:
    """Delete expired job directories. **Dry run unless told otherwise.**"""
    candidates = cleanup_candidates() if candidates is None else candidates
    deleted, failed = [], []

    for candidate in candidates:
        try:
            safe_path = assert_deletable(candidate.path)
        except UnsafeDeletionError as exc:
            failed.append({"job_id": candidate.job_id, "error": str(exc)})
            continue
        if not dry_run:
            try:
                shutil.rmtree(safe_path)
            except OSError as exc:
                failed.append({"job_id": candidate.job_id, "error": str(exc)})
                continue
        deleted.append(candidate.as_dict())

    return {
        "dry_run": dry_run,
        "candidates": len(candidates),
        "deleted": deleted,
        "failed": failed,
        "bytes_reclaimed": sum(c["bytes_used"] for c in deleted),
        "megabytes_reclaimed": round(
            sum(c["bytes_used"] for c in deleted) / 1_048_576, 2
        ),
    }
