"""Energy/temperature series read back from the OpenMM StateDataReporter CSV."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


def _find_column(header: list[str], *needles: str) -> int | None:
    """Locate a column by fuzzy name; OpenMM decorates headers with units."""
    lowered = [h.lower() for h in header]
    for needle in needles:
        for i, name in enumerate(lowered):
            if needle in name:
                return i
    return None


def parse_state_csv(path: Path) -> dict[str, list[Any]]:
    """Parse ``state.csv`` into named series.

    Returns keys: step, time_ps, potential_energy, kinetic_energy,
    total_energy, temperature. Missing columns come back as empty lists.
    """
    empty: dict[str, list[Any]] = {
        "step": [], "time_ps": [], "potential_energy": [],
        "kinetic_energy": [], "total_energy": [], "temperature": [],
    }
    if not path.exists():
        return empty

    with path.open("r", encoding="utf-8", newline="") as fh:
        rows = list(csv.reader(fh))
    if len(rows) < 2:
        return empty

    header = [h.strip().strip('"#') for h in rows[0]]
    idx = {
        "step": _find_column(header, "step"),
        "time_ps": _find_column(header, "time (ps)", "time"),
        "potential_energy": _find_column(header, "potential energy"),
        "kinetic_energy": _find_column(header, "kinetic energy"),
        "total_energy": _find_column(header, "total energy"),
        "temperature": _find_column(header, "temperature"),
    }

    out: dict[str, list[Any]] = {k: [] for k in empty}
    for row in rows[1:]:
        if not row:
            continue
        for key, col in idx.items():
            if col is None or col >= len(row):
                continue
            try:
                out[key].append(float(row[col]))
            except (TypeError, ValueError):
                continue
    return out
