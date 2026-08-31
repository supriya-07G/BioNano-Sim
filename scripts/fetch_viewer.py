#!/usr/bin/env python
"""Vendor the 3Dmol.js viewer bundle into frontend/public/vendor/.

The bundle is ~540 KB of third-party JavaScript, so it is fetched rather than
committed. Once fetched, the application runs entirely offline.

    python scripts/fetch_viewer.py
    python scripts/fetch_viewer.py --force
"""

from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

# scripts/ is not a package, so the shared console helper is imported by
# path. init_console() must run before any output is written.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _console import init_console

init_console()

REPO = Path(__file__).resolve().parents[1]
DEST = REPO / "frontend" / "public" / "vendor" / "3Dmol-min.js"
URL = "https://3dmol.org/build/3Dmol-min.js"
MIN_PLAUSIBLE_BYTES = 200_000


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="re-download if present")
    args = parser.parse_args()

    if DEST.exists() and not args.force:
        print(
            f"  {DEST.relative_to(REPO)} present "
            f"({DEST.stat().st_size:,} bytes), skipped (use --force)"
        )
        return 0

    DEST.parent.mkdir(parents=True, exist_ok=True)
    print(f"  downloading {URL}")
    try:
        body = urllib.request.urlopen(URL, timeout=120).read()
    except Exception as exc:  # noqa: BLE001
        print(f"  FAILED: {exc}", file=sys.stderr)
        print(
            "\n  The application still runs without this file; only the molecular\n"
            "  viewport is unavailable, and it reports the missing file inline.\n"
            f"  To install manually, save {URL}\n"
            f"  to {DEST.relative_to(REPO)}",
            file=sys.stderr,
        )
        return 1

    # A captive-portal or error page would be far smaller than the real bundle.
    if len(body) < MIN_PLAUSIBLE_BYTES:
        print(
            f"  FAILED: downloaded only {len(body):,} bytes, which is too small to "
            "be the 3Dmol bundle. Refusing to write it.",
            file=sys.stderr,
        )
        return 1

    DEST.write_bytes(body)
    print(f"  wrote {DEST.relative_to(REPO)} ({len(body):,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
