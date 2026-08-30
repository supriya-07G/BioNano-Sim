"""Filesystem helpers with atomic writes.

Job status is polled roughly once a second while it is being rewritten by a
worker thread, so a half-written ``status.json`` would surface as a parse error
in the UI. Every write goes through a temp file plus ``os.replace``, which is
atomic on both Windows and POSIX.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

# os.replace is atomic, but on Windows it can still fail transiently with
# PermissionError (WinError 5 / 32) when an antivirus scanner or the search
# indexer briefly holds a handle on the temp file or the destination. This is
# not hypothetical: a real 22,000-step job died at equilibration step 500 with
#   PermissionError: [WinError 5] Access is denied:
#   '...\\.status.json.khlkq4_1.tmp' -> '...\\status.json'
# and lost 43 seconds of work plus the whole run. status.json is rewritten on
# every progress publish, so a long job gets hundreds of chances to hit it.
#
# A bounded retry costs milliseconds in the normal case and saves the job in the
# pathological one. The total budget below is about 2.75 s before giving up.
_REPLACE_ATTEMPTS = 10
_REPLACE_BACKOFF_S = 0.05


def _replace_with_retry(src: Path, dest: Path) -> None:
    """os.replace, retried through transient Windows sharing violations."""
    for attempt in range(_REPLACE_ATTEMPTS):
        try:
            os.replace(src, dest)
            return
        except PermissionError:
            if attempt == _REPLACE_ATTEMPTS - 1:
                raise
            time.sleep(_REPLACE_BACKOFF_S * (attempt + 1))


def atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
    )
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="\n") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        _replace_with_retry(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def atomic_write_json(path: Path, payload: Any) -> None:
    atomic_write_text(path, json.dumps(payload, indent=2, default=str) + "\n")


def read_json(path: Path, default: Any = None) -> Any:
    """Tolerant read: a missing or momentarily unparseable file yields ``default``."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def write_csv(path: Path, header: list[str], rows: list[list[Any]]) -> None:
    import csv
    import io

    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    atomic_write_text(path, buf.getvalue())


def tail_lines(path: Path, n: int = 200) -> list[str]:
    """Last ``n`` lines, reading only the tail of the file."""
    if not path.exists():
        return []
    try:
        with path.open("rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            block = min(size, max(4096, n * 200))
            fh.seek(size - block)
            data = fh.read().decode("utf-8", errors="replace")
        return data.splitlines()[-n:]
    except OSError:
        return []


def dir_size_bytes(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
