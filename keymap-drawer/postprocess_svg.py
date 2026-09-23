#!/usr/bin/env python3
"""Post-process keymap-drawer SVG: white page + horizontal layer dividers only."""

from __future__ import annotations

import re
import sys
from pathlib import Path


def postprocess(svg: str) -> str:
    # Strip leftover frames/dividers so re-runs stay idempotent.
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

    layer_re = re.compile(
        r'<g transform="translate\(([\d.]+),\s*([\d.]+)\)" class="layer-([^"]+)">'
    )
    layers = list(layer_re.finditer(svg))
    if not layers:
        return svg

    ys = sorted({float(m.group(2)) for m in layers})
    if len(ys) < 2:
        return svg

    size = re.search(r'<svg[^>]*width="([\d.]+)"[^>]*height="([\d.]+)"', svg)
    board_w = float(size.group(1)) if size else 1000.0
    row_pitch = ys[1] - ys[0]
    margin = 24.0

    lines = [
        '<g id="layer-dividers" fill="none" stroke="#9aa3ad" '
        'stroke-width="2" stroke-linecap="butt">'
    ]
    for i in range(len(ys) - 1):
        # Gutter midpoint between stacked layer rows.
        y = round(ys[i] + row_pitch / 2, 1)
        lines.append(
            f'<line class="layer-divider-h" x1="{margin}" y1="{y}" '
            f'x2="{board_w - margin}" y2="{y}"/>'
        )
    lines.append("</g>")

    return svg.replace(
        '<rect id="page-bg" width="100%" height="100%" fill="#ffffff"/>',
        '<rect id="page-bg" width="100%" height="100%" fill="#ffffff"/>\n'
        + "\n".join(lines),
        1,
    )


def main() -> None:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "keymap-drawer/keymap.svg")
    path.write_text(postprocess(path.read_text(encoding="utf-8")), encoding="utf-8")


if __name__ == "__main__":
    main()
