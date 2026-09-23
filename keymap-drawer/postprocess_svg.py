#!/usr/bin/env python3
"""Post-process keymap-drawer SVG: white page background only."""

from __future__ import annotations

import re
import sys
from pathlib import Path


def postprocess(svg: str) -> str:
    # Strip any leftover frames/dividers from older renders.
    svg = re.sub(r'\n?<rect class="layer-frame"[^/]*/>', "", svg)
    svg = re.sub(
        r'\n?<g id="layer-dividers\b[^"]*"[^>]*>.*?</g>',
        "",
        svg,
        flags=re.DOTALL,
    )

    if 'id="page-bg"' not in svg:
        svg = re.sub(
            r"(<svg\b[^>]*>)",
            r'\1\n<rect id="page-bg" width="100%" height="100%" fill="#ffffff"/>',
            svg,
            count=1,
        )
    return svg


def main() -> None:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "keymap-drawer/keymap.svg")
    path.write_text(postprocess(path.read_text(encoding="utf-8")), encoding="utf-8")


if __name__ == "__main__":
    main()
