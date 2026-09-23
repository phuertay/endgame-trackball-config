#!/usr/bin/env python3
"""Post-process keymap-drawer SVG: white page + bold layer divider lines."""

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

    # Strip prior frames/dividers so re-runs stay idempotent.
    svg = re.sub(r'\n?<rect class="layer-frame"[^/]*/>', "", svg)
    svg = re.sub(
        r'\n?<g id="layer-dividers\b[^"]*"[^>]*>.*?</g>',
        "",
        svg,
        flags=re.DOTALL,
    )

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

    size = re.search(r'<svg[^>]*width="([\d.]+)"[^>]*height="([\d.]+)"', svg)
    board_w = float(size.group(1)) if size else xs[-1] + col_pitch
    board_h = float(size.group(2)) if size else ys[-1] + row_pitch

    # Frame each layer with a strong border (no fill — lines do the separating).
    frame_w = round(col_pitch - 20, 1)
    frame_h = round(row_pitch - 16, 1)

    def inject_frame(match: re.Match[str]) -> str:
        return (
            f'{match.group(0)}\n'
            f'<rect class="layer-frame" x="-8" y="-2" '
            f'width="{frame_w}" height="{frame_h}" rx="12" ry="12"/>'
        )

    svg = layer_re.sub(inject_frame, svg)

    # Bold grid lines through the gutters between layers.
    lines: list[str] = [
        '<g id="layer-dividers" fill="none" stroke="#1a1d21" '
        'stroke-width="4" stroke-linecap="square">'
    ]
    margin = 12.0
    if len(xs) > 1:
        for i in range(len(xs) - 1):
            # Center of the gutter between adjacent layer frames.
            x = round(xs[i] - 8 + frame_w + (col_pitch - frame_w) / 2, 1)
            lines.append(
                f'<line class="layer-divider" x1="{x}" y1="{margin}" x2="{x}" y2="{board_h - margin}"/>'
            )
    if len(ys) > 1:
        for i in range(len(ys) - 1):
            y = round(ys[i] - 2 + frame_h + (row_pitch - frame_h) / 2, 1)
            lines.append(
                f'<line class="layer-divider" x1="{margin}" y1="{y}" x2="{board_w - margin}" y2="{y}"/>'
            )
    lines.append("</g>")

    # Place dividers just after page background so they sit under labels but
    # still read as clear separators across the board.
    svg = svg.replace(
        '<rect id="page-bg" width="100%" height="100%" fill="#ffffff"/>',
        '<rect id="page-bg" width="100%" height="100%" fill="#ffffff"/>\n' + "\n".join(lines),
        1,
    )
    return svg


def main() -> None:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "keymap-drawer/keymap.svg")
    path.write_text(postprocess(path.read_text(encoding="utf-8")), encoding="utf-8")


if __name__ == "__main__":
    main()
