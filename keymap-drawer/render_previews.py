#!/usr/bin/env python3
"""Render matching full + close-up previews from the current keymap SVGs.

Always crops the close-up from the same PNG as the full preview so they
cannot drift apart. Full preview stacks letter page 1 + page 2.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PAGE1 = ROOT / "keymap-drawer" / "keymap.svg"
PAGE2 = ROOT / "keymap-drawer" / "keymap-page2.svg"
ART = Path("/opt/cursor/artifacts")


def _render(svg: Path, out: Path, width: int = 1100) -> Image.Image:
    subprocess.check_call(
        ["rsvg-convert", "-w", str(width), "-b", "white", str(svg), "-o", str(out)]
    )
    return Image.open(out).convert("RGB")


def main() -> None:
    if not PAGE1.is_file():
        sys.exit(f"missing {PAGE1}")
    if not PAGE2.is_file():
        sys.exit(f"missing {PAGE2}")
    ART.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%H%M%S")
    full = ART / f"keymap-full-{ts}.png"
    page1_art = ART / f"keymap-page1-{ts}.png"
    page2_art = ART / f"keymap-page2-{ts}.png"
    close = ART / f"keymap-default-{ts}.png"

    tmp1 = ART / f".tmp-page1-{ts}.png"
    tmp2 = ART / f".tmp-page2-{ts}.png"
    try:
        im1 = _render(PAGE1, tmp1)
        im2 = _render(PAGE2, tmp2)
        im1.save(page1_art)
        im2.save(page2_art)

        gap = 20
        w = max(im1.width, im2.width)
        h = im1.height + gap + im2.height
        stacked = Image.new("RGB", (w, h), (255, 255, 255))
        stacked.paste(im1, ((w - im1.width) // 2, 0))
        stacked.paste(im2, ((w - im2.width) // 2, im1.height + gap))
        stacked.save(full)

        # Top-left of page 1 (default + edit).
        im1.crop((0, 0, im1.width // 2 + 20, int(im1.height * 0.38))).save(close)
    finally:
        tmp1.unlink(missing_ok=True)
        tmp2.unlink(missing_ok=True)

    shutil.copy2(full, ART / "keymap-full.png")
    shutil.copy2(page1_art, ART / "keymap-page1.png")
    shutil.copy2(page2_art, ART / "keymap-page2.png")
    shutil.copy2(close, ART / "keymap-default.png")

    print(f"full={full}")
    print(f"page1={page1_art}")
    print(f"page2={page2_art}")
    print(f"closeup={close}")
    print(f"size={stacked.size[0]}x{stacked.size[1]}")


if __name__ == "__main__":
    main()
