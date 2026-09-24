#!/usr/bin/env python3
"""Render matching full + close-up previews from the current keymap SVG.

Always crops the close-up from the same PNG as the full preview so they
cannot drift apart.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SVG = ROOT / "keymap-drawer" / "keymap.svg"
ART = Path("/opt/cursor/artifacts")


def main() -> None:
    if not SVG.is_file():
        sys.exit(f"missing {SVG}")
    ART.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%H%M%S")
    full = ART / f"keymap-full-{ts}.png"
    close = ART / f"keymap-default-{ts}.png"

    subprocess.check_call(
        ["rsvg-convert", "-w", "1100", "-b", "white", str(SVG), "-o", str(full)]
    )
    im = Image.open(full)
    w, h = im.size
    # Top-left layer cluster (default + start of system) from the same bitmap.
    im.crop((0, 0, w // 2 + 20, int(h * 0.34))).save(close)

    # Stable names for the latest pair (same timestamp content).
    shutil.copy2(full, ART / "keymap-full.png")
    shutil.copy2(close, ART / "keymap-default.png")

    print(f"full={full}")
    print(f"closeup={close}")
    print(f"size={w}x{h}")


if __name__ == "__main__":
    main()
