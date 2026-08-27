"""Make script output safe on a Windows console.

The default Windows console codepage is cp1252, which cannot encode the
em-dashes, deltas and angstrom signs that appear in scientific output. Without
this, a script can complete its real work and then die on a ``print``. We switch
stdout/stderr to UTF-8 where the runtime allows it, and fall back to replacing
unencodable characters rather than raising.

Import this first in every script:

    from _console import init_console
    init_console()
"""

from __future__ import annotations

import sys


def init_console() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            # Some redirected streams reject reconfigure; degrade to replacement
            # on the existing encoding instead of crashing.
            try:
                reconfigure(errors="replace")
            except (ValueError, OSError):
                pass
