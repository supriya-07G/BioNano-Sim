#!/usr/bin/env python
"""Delete generated runtime artefacts (jobs, uploads, reports, logs).

    python scripts/clean_runtime.py            # ask first
    python scripts/clean_runtime.py --yes      # no prompt
    python scripts/clean_runtime.py --jobs     # only runtime/jobs
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path
import sys

# scripts/ is not a package, so the shared console helper is imported by
# path. init_console() must run before any output is written.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _console import init_console  # noqa: E402

init_console()

REPO = Path(__file__).resolve().parents[1]
TARGETS = ("jobs", "uploads", "reports", "logs")


def dir_size(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yes", "-y", action="store_true", help="skip confirmation")
    for name in TARGETS:
        parser.add_argument(
            f"--{name}", action="store_true", help=f"clean only runtime/{name}"
        )
    args = parser.parse_args()

    selected = [n for n in TARGETS if getattr(args, n)] or list(TARGETS)

    plan = []
    for name in selected:
        path = REPO / "runtime" / name
        if not path.exists():
            continue
        entries = [p for p in path.iterdir() if p.name != ".gitkeep"]
        if entries:
            plan.append((path, entries, dir_size(path)))

    if not plan:
        print("Nothing to clean; runtime directories are already empty.")
        return 0

    print("Will delete:")
    total = 0
    for path, entries, size in plan:
        label = "entry" if len(entries) == 1 else "entries"
        print(f"  runtime/{path.name}: {len(entries)} {label}, {size / 1e6:.2f} MB")
        total += size
    print(f"  total: {total / 1e6:.2f} MB")

    if not args.yes:
        try:
            answer = input("\nProceed? [y/N] ").strip().lower()
        except EOFError:
            print("\nNo interactive input available; re-run with --yes to confirm.")
            return 1
        if answer not in ("y", "yes"):
            print("Aborted.")
            return 0

    for path, entries, _ in plan:
        for entry in entries:
            if entry.is_dir():
                shutil.rmtree(entry, ignore_errors=True)
            else:
                entry.unlink(missing_ok=True)
        (path / ".gitkeep").touch()
    print("Runtime directories cleaned.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
