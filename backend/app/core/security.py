"""Input-safety helpers: filename sanitising and path confinement.

The API accepts a user-supplied filename on upload and user-supplied job ids in
URLs, both of which reach the filesystem. Everything that touches a path goes
through here.
"""

from __future__ import annotations

import re
import unicodedata
import uuid
from pathlib import Path

from app.core.exceptions import UnsafePathError

_SAFE_CHARS = re.compile(r"[^A-Za-z0-9._-]")
_PDB_ID = re.compile(r"^[0-9A-Za-z]{4}$")
_UUID4_HEX = re.compile(r"^[0-9a-f]{32}$")


def sanitise_filename(raw: str, *, default_stem: str = "upload") -> str:
    r"""Reduce a user filename to a flat, safe basename.

    Strips directory components (including Windows ``\`` separators, which
    ``PurePosixPath`` would keep), normalises Unicode, and collapses anything
    outside ``[A-Za-z0-9._-]``.
    """
    name = unicodedata.normalize("NFKD", raw or "").encode("ascii", "ignore").decode()
    name = name.replace("\\", "/").split("/")[-1]
    name = _SAFE_CHARS.sub("_", name).lstrip(".")
    if not name or name in {".", ".."}:
        name = f"{default_stem}.pdb"
    return name[:120]


def validate_pdb_id(pdb_id: str) -> str:
    """Accept only a canonical 4-character PDB id, returned upper-cased.

    This is the sole guard for the protein registry's path lookups, so it is a
    strict allow-list rather than an escaping pass.
    """
    if not _PDB_ID.match(pdb_id or ""):
        raise UnsafePathError(
            f"'{pdb_id}' is not a valid 4-character PDB identifier.",
            code="INVALID_PDB_ID",
        )
    return pdb_id.upper()


def validate_job_id(job_id: str) -> str:
    """Accept only a 32-hex-character UUID4 (as produced by ``uuid4().hex``)."""
    candidate = (job_id or "").strip().lower().replace("-", "")
    if not _UUID4_HEX.match(candidate):
        raise UnsafePathError(
            f"'{job_id}' is not a valid job identifier.", code="INVALID_JOB_ID"
        )
    return candidate


def new_job_id() -> str:
    return uuid.uuid4().hex


def resolve_within(base: Path, *parts: str) -> Path:
    """Join ``parts`` onto ``base`` and prove the result stays inside ``base``.

    Defends against traversal that survives sanitising (symlinks, ``..`` in a
    segment we did not sanitise).
    """
    base_resolved = base.resolve()
    target = base_resolved.joinpath(*parts).resolve()
    if base_resolved != target and base_resolved not in target.parents:
        raise UnsafePathError("Resolved path escapes its permitted directory.")
    return target
