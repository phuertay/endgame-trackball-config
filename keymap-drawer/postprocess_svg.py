#!/usr/bin/env python3
"""Post-process keymap-drawer SVG: white page + H/V layer dividers."""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Nested <svg> glyph defs from keymap-drawer do not paint under rsvg-convert.
# Flatten to a <symbol> with an explicit fill so PDF/PNG previews show icons.
_BT_PATH = (
    "M17.71,7.71L12,2H11V9.58L6.41,5L5,6.41L10.59,12L5,17.58L6.41,19"
    "L11,14.41V22H12L17.71,16.29L13.41,12L17.71,7.71M13,5.83L14.88,7.71"
    "L13,9.58V5.83M14.88,16.29L13,18.17V14.41L14.88,16.29Z"
)
_BT_SYMBOL = (
    f'<symbol id="mdi:bluetooth" viewBox="0 0 24 24">'
    f'<path fill="#1a1d21" d="{_BT_PATH}"/></symbol>'
)


def _fix_bluetooth_glyphs(svg: str) -> str:
    """Replace keymap-drawer nested bluetooth <svg> defs with a paintable <symbol>."""
    # Full nested def: <svg id="mdi:bluetooth"><svg ...>...</svg></svg>
    # Non-greedy .*?</svg> would stop at the inner close and leave a stray </svg>.
    svg = re.sub(
        r'<svg id="mdi:bluetooth">\s*<svg\b[^>]*>.*?</svg>\s*</svg>\s*',
        "",
        svg,
        flags=re.DOTALL,
    )
    svg = re.sub(
        r'<symbol id="mdi:bluetooth"[^>]*>.*?</symbol>\s*',
        "",
        svg,
        flags=re.DOTALL,
    )
    # Drop a leftover stray closer if a previous bad replace left one.
    svg = re.sub(
        r'(/\* start glyphs \*/\s*)\n?</svg>\s*',
        r"\1\n",
        svg,
    )
    if "glyph mdi:bluetooth" in svg or "mdi:bluetooth" in svg:
        if "/* start glyphs */" in svg:
            svg = svg.replace(
                "/* start glyphs */",
                f"/* start glyphs */\n{_BT_SYMBOL}\n",
                1,
            )
        elif "<defs>" in svg:
            svg = svg.replace("<defs>", f"<defs>\n{_BT_SYMBOL}\n", 1)
    return svg


def postprocess(svg: str) -> str:
    # Strip leftover frames/dividers so re-runs stay idempotent.
    svg = re.sub(r'\n?<rect class="layer-frame"[^/]*/>', "", svg)
    svg = re.sub(
        r'\n?<g id="layer-dividers\b[^"]*"[^>]*>.*?</g>',
        "",
        svg,
        flags=re.DOTALL,
    )
    svg = _fix_bluetooth_glyphs(svg)

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

    xs = sorted({float(m.group(1)) for m in layers})
    ys = sorted({float(m.group(2)) for m in layers})

    size = re.search(r'<svg[^>]*width="([\d.]+)"[^>]*height="([\d.]+)"', svg)
    board_w = float(size.group(1)) if size else 1000.0
    board_h = float(size.group(2)) if size else 1000.0
    margin = 24.0

    lines = [
        '<g id="layer-dividers" fill="none" stroke="#8b949e" '
        'stroke-width="2" stroke-linecap="butt">'
    ]

    # Horizontal gutters between stacked layer rows.
    if len(ys) >= 2:
        for i in range(len(ys) - 1):
            y = round(ys[i + 1] - 10, 1)
            lines.append(
                f'<line class="layer-divider-h" x1="{margin}" y1="{y}" '
                f'x2="{board_w - margin}" y2="{y}"/>'
            )

    # Vertical gutter between the two columns.
    if len(xs) >= 2:
        x = round((xs[0] + xs[1]) / 2, 1)
        lines.append(
            f'<line class="layer-divider-v" x1="{x}" y1="{margin}" '
            f'x2="{x}" y2="{board_h - margin}"/>'
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
