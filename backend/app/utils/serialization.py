"""JSON-safe conversion for NumPy scalars and non-finite floats."""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def to_jsonable(value: Any) -> Any:
    """Recursively convert to something ``json.dumps`` accepts.

    NumPy scalars become Python scalars, and NaN/Inf become ``None`` — the
    frontend charts treat null as a gap, whereas literal NaN is invalid JSON and
    would break the whole response.
    """
    import numpy as np

    if value is None or isinstance(value, str | bool | int):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, np.generic):
        return to_jsonable(value.item())
    if isinstance(value, np.ndarray):
        return [to_jsonable(v) for v in value.tolist()]
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple | set):
        return [to_jsonable(v) for v in value]
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    return str(value)


def round_series(points: list[tuple[float, float]], nd: int = 5) -> list[dict[str, float]]:
    """Chart-ready ``[{x, y}]`` with non-finite y dropped to null."""
    out = []
    for x, y in points:
        yv = float(y)
        out.append({"x": round(float(x), nd), "y": round(yv, nd) if math.isfinite(yv) else None})
    return out
