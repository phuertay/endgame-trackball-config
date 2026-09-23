#!/usr/bin/env python3
"""Post-process keymap-drawer SVG: white page + layer separator frames."""

from __future__ import annotations

import re
import sys
from pathlib import Path


def postprocess(svg: str) -> str:
    if 'id="page-bg"' not in svg:
        svg = re.sub(
            r"(<svg\b[^>]*>)",
            r'\1\n<rect id="page-bg" width="100%" height="100%" fill="#ffffff"/>',
            svg,
            count=1,
        )

    if 'class="layer-frame"' in svg:
        return svg

    layer_re = re.compile(
        r'<g transform="translate\(([\d.]+),\s*([\d.]+)\)" class="layer-([^"]+)">'
    )
    layers = list(layer_re.finditer(svg))
    if not layers:
        return svg

    xs = sorted({float(m.group(1)) for m in layers})
    ys = sorted({float(m.group(2)) for m in layers})
    col_pitch = (xs[1] - xs[0]) if len(xs) > 1 else 500.0
    row_pitch = (ys[1] - ys[0]) if len(ys) > 1 else 280.0
    # Leave a small gutter so neighboring frames don't touch.
    frame_w = round(col_pitch - 18, 1)
    frame_h = round(row_pitch - 14, 1)

    def inject(match: re.Match[str]) -> str:
        return (
            f'{match.group(0)}\n'
            f'<rect class="layer-frame" x="-10" y="-4" '
            f'width="{frame_w}" height="{frame_h}" rx="14" ry="14"/>'
        )

    return layer_re.sub(inject, svg)


def main() -> None:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "keymap-drawer/keymap.svg")
    path.write_text(postprocess(path.read_text(encoding="utf-8")), encoding="utf-8")


if __name__ == "__main__":
    main()
