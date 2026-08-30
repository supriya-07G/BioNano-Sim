"""Tests for storage quotas, retention, cleanup and diagnostics (#23, #26).

This module deletes files, so the safety properties are tested harder than the
happy path. The acceptance criteria are that repeated simulations cannot
silently exhaust disk, and that cleanup never removes approved dataset or
precomputed evidence.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.core import diagnostics, storage
from app.core.storage import (
    CleanupCandidate,
    StorageReport,
    UnsafeDeletionError,
    admission_check,
    assert_deletable,
    cleanup_candidates,
    directory_usage,
    run_cleanup,
)


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    """A throwaway runtime tree, so no test can touch the real one."""
    root = tmp_path / "runtime"
    for name in ("jobs", "uploads", "reports", "logs"):
        (root / name).mkdir(parents=True)
    # jobs_dir, uploads_dir, reports_dir and logs_dir are read-only properties
    # derived from runtime_dir, so redirecting the root redirects all of them.
    monkeypatch.setattr(storage.settings, "runtime_dir", root)
    return root


def make_job(runtime: Path, job_id: str, status: str, age_days: float,
             payload_bytes: int = 1024) -> Path:
    job_dir = runtime / "jobs" / job_id
    job_dir.mkdir(parents=True)
    finished = datetime.now(UTC) - timedelta(days=age_days)
    (job_dir / "status.json").write_text(json.dumps({
        "job_id": job_id, "status": status,
        "created_at": finished.isoformat(), "finished_at": finished.isoformat(),
    }), encoding="utf-8")
    (job_dir / "trajectory.dcd").write_bytes(b"x" * payload_bytes)
    return job_dir


# --------------------------------------------------------------------------- #
# Safety: what must never be deletable
# --------------------------------------------------------------------------- #
def test_a_path_outside_runtime_is_refused(runtime, tmp_path):
    outside = tmp_path / "elsewhere"
    outside.mkdir()
    with pytest.raises(UnsafeDeletionError, match="outside the runtime tree"):
        assert_deletable(outside)


def test_the_runtime_root_itself_is_refused(runtime):
    with pytest.raises(UnsafeDeletionError, match="runtime root"):
        assert_deletable(runtime)


def test_a_traversal_escape_is_refused(runtime):
    """`..` must be resolved and caught, not followed."""
    escape = runtime / "jobs" / ".." / ".." / "etc"
    with pytest.raises(UnsafeDeletionError):
        assert_deletable(escape)


def test_the_real_dataset_is_not_deletable(runtime):
    """data/ holds published evidence and is outside runtime by design."""
    repo = Path(__file__).resolve().parents[2]
    with pytest.raises(UnsafeDeletionError):
        assert_deletable(repo / "data" / "ml")


def test_the_precomputed_fallback_is_not_deletable(runtime):
    repo = Path(__file__).resolve().parents[2]
    with pytest.raises(UnsafeDeletionError):
        assert_deletable(repo / "data" / "precomputed" / "1UBQ")


def test_the_model_bundles_are_not_deletable(runtime):
    repo = Path(__file__).resolve().parents[2]
    with pytest.raises(UnsafeDeletionError):
        assert_deletable(repo / "models")


def test_an_unsafe_candidate_is_reported_not_deleted(runtime, tmp_path):
    """A refusal must surface, not pass silently as a success."""
    outside = tmp_path / "precious"
    outside.mkdir()
    (outside / "keep.txt").write_text("important", encoding="utf-8")
    candidate = CleanupCandidate("evil", outside, "completed", 99.0, 10, "forged")

    result = run_cleanup([candidate], dry_run=False)
    assert result["deleted"] == []
    assert len(result["failed"]) == 1
    assert (outside / "keep.txt").exists()


# --------------------------------------------------------------------------- #
# Retention
# --------------------------------------------------------------------------- #
def test_a_fresh_completed_job_is_kept(runtime):
    make_job(runtime, "fresh", "completed", age_days=1)
    assert cleanup_candidates() == []


def test_an_expired_completed_job_is_a_candidate(runtime):
    make_job(runtime, "old", "completed", age_days=99)
    candidates = cleanup_candidates()
    assert [c.job_id for c in candidates] == ["old"]
    assert "retention window" in candidates[0].reason


def test_failed_jobs_expire_sooner_than_completed(runtime):
    make_job(runtime, "failed_job", "failed", age_days=10)
    make_job(runtime, "completed_job", "completed", age_days=10)
    assert [c.job_id for c in cleanup_candidates()] == ["failed_job"]


def test_a_running_job_is_never_a_candidate(runtime):
    """Deleting a live job's directory would kill work in progress."""
    make_job(runtime, "running_job", "running", age_days=999)
    assert cleanup_candidates() == []


def test_a_queued_job_is_never_a_candidate(runtime):
    make_job(runtime, "queued_job", "queued", age_days=999)
    assert cleanup_candidates() == []


def test_an_unreadable_job_is_not_a_candidate(runtime):
    """Deleting something we failed to identify is the mistake to avoid."""
    broken = runtime / "jobs" / "broken"
    broken.mkdir()
    (broken / "status.json").write_text("{not json", encoding="utf-8")
    assert cleanup_candidates() == []
    assert broken.exists()


# --------------------------------------------------------------------------- #
# Cleanup behaviour
# --------------------------------------------------------------------------- #
def test_cleanup_is_a_dry_run_by_default(runtime):
    job = make_job(runtime, "old", "completed", age_days=99)
    result = run_cleanup()
    assert result["dry_run"] is True
    assert len(result["deleted"]) == 1
    assert job.exists(), "a default call must not delete anything"


def test_apply_actually_deletes(runtime):
    job = make_job(runtime, "old", "completed", age_days=99)
    result = run_cleanup(dry_run=False)
    assert not job.exists()
    assert result["bytes_reclaimed"] > 0


def test_cleanup_leaves_other_jobs_alone(runtime):
    keep = make_job(runtime, "keep", "completed", age_days=1)
    make_job(runtime, "drop", "completed", age_days=99)
    run_cleanup(dry_run=False)
    assert keep.exists()
    assert not (runtime / "jobs" / "drop").exists()


# --------------------------------------------------------------------------- #
# Quotas and admission
# --------------------------------------------------------------------------- #
def test_usage_counts_bytes_and_files(runtime):
    make_job(runtime, "a", "completed", age_days=1, payload_bytes=4096)
    usage = directory_usage("jobs", runtime / "jobs")
    assert usage.bytes_used >= 4096
    assert usage.file_count == 2


def _report(**overrides) -> StorageReport:
    base = {
        "areas": [], "total_bytes": 1_000, "quota_bytes": 10_000,
        "disk_free_bytes": 10 * 1024**3, "disk_total_bytes": 100 * 1024**3,
        "min_free_bytes": 2 * 1024**3,
    }
    return StorageReport(**(base | overrides))


def test_a_healthy_report_admits_a_job():
    allowed, reason = admission_check(_report())
    assert allowed and reason is None


def test_a_job_is_refused_when_over_quota():
    allowed, reason = admission_check(_report(total_bytes=20_000))
    assert not allowed
    assert "quota is exhausted" in reason


def test_a_job_is_refused_when_the_disk_is_low():
    """Refusing at submission beats dying at step 18,000."""
    allowed, reason = admission_check(_report(disk_free_bytes=100 * 1024**2))
    assert not allowed
    assert "Not enough disk space" in reason


def test_approaching_the_quota_warns_before_it_blocks():
    report = _report(total_bytes=8_500)
    assert not report.over_quota
    assert any("quota" in w for w in report.warnings())


def test_cleanup_required_flags_either_pressure():
    assert _report(total_bytes=20_000).cleanup_required
    assert _report(disk_free_bytes=1).cleanup_required
    assert not _report().cleanup_required


# --------------------------------------------------------------------------- #
# Diagnostics and redaction
# --------------------------------------------------------------------------- #
def test_redaction_strips_sensitive_keys():
    payload = {"upload_path": "C:/Users/supriya/secret.pdb", "count": 3}
    redacted = diagnostics.redact(payload)
    assert redacted["upload_path"] == diagnostics.REDACTED
    assert redacted["count"] == 3


@pytest.mark.parametrize("home", [
    r"C:\Users\supriya\projects\x.pdb",
    "/home/supriya/x.pdb",
    "/Users/supriya/x.pdb",
])
def test_home_directories_are_stripped_from_free_text(home):
    out = diagnostics.redact({"detail": f"failed reading {home}"})
    assert "supriya" not in out["detail"]
    assert diagnostics.REDACTED in out["detail"]


def test_redaction_recurses_into_nested_structures():
    payload = {"jobs": [{"filename": "mine.pdb", "status": "failed"}]}
    out = diagnostics.redact(payload)
    assert out["jobs"][0]["filename"] == diagnostics.REDACTED
    assert out["jobs"][0]["status"] == "failed"


def test_diagnostics_counts_jobs_by_status(runtime):
    make_job(runtime, "a", "completed", age_days=1)
    make_job(runtime, "b", "failed", age_days=1)
    make_job(runtime, "c", "completed", age_days=1)
    result = diagnostics.job_diagnostics()
    assert result["counts_by_status"]["completed"] == 2
    assert result["counts_by_status"]["failed"] == 1
    assert result["total"] == 3


def test_diagnostics_reports_failures_with_their_message(runtime):
    job = make_job(runtime, "bad", "failed", age_days=1)
    payload = json.loads((job / "status.json").read_text(encoding="utf-8"))
    payload["error_message"] = "OpenMM diverged at step 500"
    (job / "status.json").write_text(json.dumps(payload), encoding="utf-8")

    failures = diagnostics.job_diagnostics()["recent_failures"]
    assert len(failures) == 1
    assert "diverged" in failures[0]["error"]


def test_a_stale_running_job_is_flagged(runtime):
    """Invisible in status counts otherwise, and it looks like a hang."""
    job = make_job(runtime, "stuck", "running", age_days=1)
    payload = json.loads((job / "status.json").read_text(encoding="utf-8"))
    payload["updated_at"] = (
        datetime.now(UTC) - timedelta(hours=5)
    ).isoformat()
    (job / "status.json").write_text(json.dumps(payload), encoding="utf-8")

    assert diagnostics.job_diagnostics()["stale_jobs"] == ["stuck"]


def test_a_recently_updated_running_job_is_not_stale(runtime):
    make_job(runtime, "busy", "running", age_days=0)
    job = runtime / "jobs" / "busy"
    payload = json.loads((job / "status.json").read_text(encoding="utf-8"))
    payload["updated_at"] = datetime.now(UTC).isoformat()
    (job / "status.json").write_text(json.dumps(payload), encoding="utf-8")
    assert diagnostics.job_diagnostics()["stale_jobs"] == []


def test_the_support_bundle_excludes_uploads_by_default(runtime):
    bundle = diagnostics.support_bundle()
    assert bundle["bundle"]["includes_uploaded_structures"] is False
    assert "uploaded structure files" in bundle["bundle"]["excluded"]
    assert "uploaded_structure_count" not in bundle["bundle"]


def test_opting_in_counts_uploads_but_never_embeds_them(runtime):
    (runtime / "uploads" / "mine.pdb").write_text("ATOM", encoding="utf-8")
    bundle = diagnostics.support_bundle(include_uploads=True)
    assert bundle["bundle"]["uploaded_structure_count"] == 1
    assert "ATOM" not in json.dumps(bundle)


def test_collect_returns_everything_needed_to_diagnose(runtime):
    make_job(runtime, "a", "failed", age_days=1)
    payload = diagnostics.collect()
    for section in ("jobs", "engine", "storage", "logs", "warnings"):
        assert section in payload, f"{section} missing from diagnostics"
    assert payload["storage"]["cleanup_required"] in (True, False)


def test_the_bundle_writes_to_disk(runtime, tmp_path):
    written = diagnostics.write_support_bundle(tmp_path / "bundle.json")
    assert written.is_file()
    assert json.loads(written.read_text(encoding="utf-8"))["app"]["name"]


# --------------------------------------------------------------------------- #
# Admission is enforced at submission, not mid-run
# --------------------------------------------------------------------------- #
def test_submission_is_refused_when_storage_is_exhausted(runtime, monkeypatch):
    """The acceptance criterion: repeated runs cannot silently exhaust disk."""
    from app.core.exceptions import InsufficientStorageError
    from app.simulation import job_manager

    monkeypatch.setattr(
        job_manager, "admission_check",
        lambda *a, **k: (False, "Not enough disk space to start a simulation"),
    )
    # A real preset id: the admission check sits just after preset lookup, and
    # the point of the test is the storage refusal, not input validation.
    request = SimpleNamespace(preset_id="rapid_demo")
    manager = job_manager.get_job_manager()
    with pytest.raises(InsufficientStorageError, match="Not enough disk space"):
        manager.submit(
            request=request, source_pdb=Path("x.pdb"), structure_info={},
            scenario={}, validation_warnings=[],
        )


def test_the_storage_error_is_a_507(runtime):
    from app.core.exceptions import InsufficientStorageError

    assert InsufficientStorageError.http_status == 507
    assert InsufficientStorageError.code == "INSUFFICIENT_STORAGE"
