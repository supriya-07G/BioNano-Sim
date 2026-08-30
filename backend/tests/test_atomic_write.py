"""Tests for the atomic write, including the Windows sharing-violation retry.

A real 22,000-step job died at equilibration step 500 when os.replace hit
PermissionError (WinError 5) while rewriting status.json, losing the whole run.
status.json is rewritten on every progress publish, so a long job gets hundreds
of chances to hit it. These tests pin the retry down.
"""

from __future__ import annotations

import json
import os

import pytest

from app.utils import files as files_module
from app.utils.files import atomic_write_json, atomic_write_text, read_json


def test_a_normal_write_lands(tmp_path):
    target = tmp_path / "status.json"
    atomic_write_text(target, "hello")
    assert target.read_text(encoding="utf-8") == "hello"


def test_no_temp_files_are_left_behind(tmp_path):
    target = tmp_path / "status.json"
    atomic_write_text(target, "hello")
    assert [p.name for p in tmp_path.iterdir()] == ["status.json"]


def test_a_transient_sharing_violation_is_retried(tmp_path, monkeypatch):
    """The scanner holds the file for a moment, then lets go. The write must land."""
    target = tmp_path / "status.json"
    real_replace = os.replace
    calls = {"n": 0}

    def flaky(src, dest):
        calls["n"] += 1
        if calls["n"] <= 3:
            raise PermissionError(5, "Access is denied")
        return real_replace(src, dest)

    monkeypatch.setattr(files_module.os, "replace", flaky)
    monkeypatch.setattr(files_module, "_REPLACE_BACKOFF_S", 0.0)

    atomic_write_text(target, "survived")
    assert target.read_text(encoding="utf-8") == "survived"
    assert calls["n"] == 4, "should have retried until it succeeded"


def test_a_permanent_sharing_violation_still_raises(tmp_path, monkeypatch):
    """The retry is bounded: a genuinely stuck file must not hang the job."""
    target = tmp_path / "status.json"
    calls = {"n": 0}

    def always_denied(src, dest):
        calls["n"] += 1
        raise PermissionError(5, "Access is denied")

    monkeypatch.setattr(files_module.os, "replace", always_denied)
    monkeypatch.setattr(files_module, "_REPLACE_BACKOFF_S", 0.0)

    with pytest.raises(PermissionError):
        atomic_write_text(target, "never lands")
    assert calls["n"] == files_module._REPLACE_ATTEMPTS
    # The temp file must be cleaned up even on the failing path.
    assert list(tmp_path.iterdir()) == []


def test_other_oserrors_are_not_retried(tmp_path, monkeypatch):
    """Only sharing violations are transient. A real error must surface at once."""
    target = tmp_path / "status.json"
    calls = {"n": 0}

    def broken(src, dest):
        calls["n"] += 1
        raise OSError("disk is on fire")

    monkeypatch.setattr(files_module.os, "replace", broken)

    with pytest.raises(OSError, match="disk is on fire"):
        atomic_write_text(target, "nope")
    assert calls["n"] == 1, "a non-PermissionError must not be retried"


def test_json_round_trip_survives_a_transient_denial(tmp_path, monkeypatch):
    target = tmp_path / "status.json"
    real_replace = os.replace
    calls = {"n": 0}

    def flaky(src, dest):
        calls["n"] += 1
        if calls["n"] == 1:
            raise PermissionError(5, "Access is denied")
        return real_replace(src, dest)

    monkeypatch.setattr(files_module.os, "replace", flaky)
    monkeypatch.setattr(files_module, "_REPLACE_BACKOFF_S", 0.0)

    payload = {"job_id": "abc", "status": "running", "steps_completed": 500}
    atomic_write_json(target, payload)
    assert read_json(target) == payload
    assert json.loads(target.read_text(encoding="utf-8")) == payload
