#!/usr/bin/env python
"""Cut the COSMORA logo source into the assets the app actually uses.

The source is one wide lockup on a near-black plate: a circular protein mark,
then the wordmark and tagline. The app needs those separately -- a 28 px header
slot cannot show a 1191 px lockup, and scaling the whole thing down turns the
mark into mud.

The plate is made transparent rather than kept. The UI has three themes and a
starfield behind it; a baked-in black rectangle would show as a hard box in all
of them.

Usage:
    .venv311/Scripts/python.exe scripts/build_logo_assets.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / "image.png"
OUT = REPO / "frontend" / "public"

#: Anything at or below this luminance is plate, not art. The mark's darkest
#: real pixels sit well above it, so nothing of the ribbon is lost.
PLATE_LUMA = 26

#: The blank gutter separating the circular mark from the wordmark, measured
#: from the source rather than guessed.
MARK_WORDMARK_GAP_X = 418


def transparent(image: Image.Image) -> Image.Image:
    """Fade the dark plate to alpha, keeping antialiased edges intact.

    A hard threshold would leave a jagged black fringe around the ribbon, so
    alpha ramps with luminance across the darkest part of the range instead.
    """
    rgba = np.array(image.convert("RGBA")).astype(np.float32)
    luma = rgba[..., :3].max(axis=2)
    alpha = np.clip((luma - PLATE_LUMA) / 40.0, 0.0, 1.0)
    rgba[..., 3] = rgba[..., 3] * alpha
    return Image.fromarray(rgba.astype(np.uint8), "RGBA")


def trim(image: Image.Image, pad: int = 0) -> Image.Image:
    box = image.getbbox()
    if box is None:
        return image
    left, top, right, bottom = box
    return image.crop((
        max(0, left - pad),
        max(0, top - pad),
        min(image.width, right + pad),
        min(image.height, bottom + pad),
    ))


def squared(image: Image.Image) -> Image.Image:
    """Centre on a square canvas so the header slot never distorts it."""
    side = max(image.size)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(image, ((side - image.width) // 2, (side - image.height) // 2))
    return canvas


def main() -> int:
    if not SOURCE.is_file():
        print(f"source not found: {SOURCE}")
        return 1

    source = transparent(Image.open(SOURCE))
    OUT.mkdir(parents=True, exist_ok=True)

    mark = squared(trim(source.crop((0, 0, MARK_WORDMARK_GAP_X, source.height))))
    mark.resize((512, 512), Image.LANCZOS).save(OUT / "logo-mark.png")
    print(f"logo-mark.png      512x512   (from {mark.size[0]}px square)")

    full = trim(source, pad=8)
    full.save(OUT / "logo-full.png")
    print(f"logo-full.png      {full.size[0]}x{full.size[1]}")

    # Favicons. 32 px is where the ribbon stops being readable, so the smaller
    # sizes exist only because browsers ask for them.
    for size in (180, 32):
        mark.resize((size, size), Image.LANCZOS).save(OUT / f"logo-{size}.png")
        print(f"logo-{size}.png{' ' * (10 - len(str(size)))} {size}x{size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
