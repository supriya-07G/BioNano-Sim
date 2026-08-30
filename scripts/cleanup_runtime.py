#!/usr/bin/env python
"""Preview or apply runtime cleanup (issue #26).

Deletes job directories that are past their retention window. **Dry run by
default** -- ``--apply`` is required to remove anything, because a command that
deletes a teammate's results by default is one that will eventually do it by
accident.

Published evidence is never a candidate. ``data/``, ``models/`` and the
precomputed fallback live outside ``runtime/``, and every path is re-checked
against the runtime root before deletion, so a traversal or a symlink pointing
out of the tree is refused rather than followed.

Usage:
    python scripts/cleanup_runtime.py              # preview
    python scripts/cleanup_runtime.py --apply      # delete
    python scripts/cleanup_runtime.py --diagnostics-out bundle.json
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

from app.config import settings  # noqa: E402
from app.core import diagnostics, storage  # noqa: E402


def human(num_bytes: int) -> str:
    return f"{num_bytes / 1_048_576:,.1f} MB"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true",
                    help="actually delete (default is a preview)")
    ap.add_argument("--diagnostics-out", type=Path, default=None,
                    help="also write a redacted support bundle here")
    args = ap.parse_args()

    report = storage.storage_report()
    print("runtime storage")
    for area in report.areas:
        print(f"  {area.name:<9} {human(area.bytes_used):>12}  "
              f"{area.file_count:>5} files")
    print(f"  {'total':<9} {human(report.total_bytes):>12}  of "
          f"{human(report.quota_bytes)} quota "
          f"({report.quota_used_fraction:.0%})")
    print(f"  disk free {human(report.disk_free_bytes)}")

    for message in report.warnings():
        print(f"  [warn] {message}")

    print("\nretention")
    print(f"  completed {settings.retention_days_completed} d   "
          f"failed {settings.retention_days_failed} d   "
          f"cancelled {settings.retention_days_cancelled} d")
    print("  running and queued jobs are never candidates")

    candidates = storage.cleanup_candidates()
    if not candidates:
        print("\nnothing is past its retention window")
    else:
        print(f"\n{len(candidates)} candidate(s):")
        for candidate in candidates:
            print(f"  {candidate.job_id}  {human(candidate.bytes_used):>10}  "
                  f"{candidate.reason}")

    result = storage.run_cleanup(candidates, dry_run=not args.apply)

    if result["failed"]:
        print(f"\n{len(result['failed'])} refused or failed:", file=sys.stderr)
        for failure in result["failed"]:
            print(f"  [FAIL] {failure['job_id']}: {failure['error']}",
                  file=sys.stderr)

    if args.diagnostics_out:
        written = diagnostics.write_support_bundle(args.diagnostics_out)
        print(f"\nsupport bundle written to {written} "
              "(uploads and absolute paths redacted)")

    if args.apply:
        print(f"\nDELETED {len(result['deleted'])} job(s), reclaimed "
              f"{result['megabytes_reclaimed']:,.1f} MB")
    elif candidates:
        print(f"\nPREVIEW ONLY -- would reclaim "
              f"{result['megabytes_reclaimed']:,.1f} MB. "
              "Re-run with --apply to delete.")

    return 1 if result["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
