"""Radius of gyration: a compactness measure sensitive to unfolding/swelling."""

from __future__ import annotations

import numpy as np


def radius_of_gyration(coords: np.ndarray, masses: np.ndarray | None = None) -> float:
    """Mass-weighted Rg for one (N, 3) frame. Unweighted if ``masses`` is None."""
    if coords.size == 0:
        return float("nan")
    if masses is None:
        centre = coords.mean(axis=0)
        return float(np.sqrt(((coords - centre) ** 2).sum(axis=1).mean()))
    m = np.asarray(masses, dtype=float).reshape(-1, 1)
    total = float(m.sum())
    if total <= 0:
        return float("nan")
    centre = (coords * m).sum(axis=0) / total
    sq = ((coords - centre) ** 2).sum(axis=1)
    return float(np.sqrt((sq * m.ravel()).sum() / total))


def rg_series(frames: np.ndarray, masses: np.ndarray | None = None) -> np.ndarray:
    if frames.ndim != 3 or frames.shape[0] == 0:
        return np.zeros(0)
    return np.array([radius_of_gyration(f, masses) for f in frames], dtype=float)
