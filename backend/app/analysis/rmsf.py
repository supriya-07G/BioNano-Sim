"""Per-residue RMSF: fluctuation about each atom's own mean position.

Frames are superposed onto the mean structure first, so RMSF reports internal
flexibility rather than whole-molecule tumbling.
"""

from __future__ import annotations

import numpy as np


def _optimal_rotation(p: np.ndarray, q: np.ndarray) -> np.ndarray:
    v, _, wt = np.linalg.svd(p.T @ q)
    d = np.sign(np.linalg.det(v @ wt))
    return v @ np.diag([1.0, 1.0, d]) @ wt


def superpose_to_mean(frames: np.ndarray, max_iter: int = 2) -> np.ndarray:
    """Iteratively superpose all frames onto their running mean structure."""
    if frames.shape[0] == 0:
        return frames
    centred = frames - frames.mean(axis=1, keepdims=True)
    reference = centred[0]
    for _ in range(max_iter):
        aligned = np.stack(
            [frame @ _optimal_rotation(frame, reference) for frame in centred]
        )
        new_reference = aligned.mean(axis=0)
        if np.allclose(new_reference, reference, atol=1e-9):
            reference = new_reference
            break
        reference = new_reference
    return np.stack([frame @ _optimal_rotation(frame, reference) for frame in centred])


def rmsf_per_atom(frames: np.ndarray) -> np.ndarray:
    """Root-mean-square fluctuation per atom, in the input length unit."""
    if frames.ndim != 3 or frames.shape[0] < 2:
        return np.zeros(frames.shape[1] if frames.ndim == 3 else 0)
    aligned = superpose_to_mean(frames)
    mean_pos = aligned.mean(axis=0)
    return np.sqrt(((aligned - mean_pos) ** 2).sum(axis=-1).mean(axis=0))
