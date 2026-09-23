#!/usr/bin/env python3
"""Post-process keymap-drawer SVG: white page + H/V layer dividers."""

from __future__ import annotations

import re
import sys
from collections import defaultdict
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

_LAYER_RE = re.compile(
    r'<g transform="translate\(([\d.]+),\s*([\d.]+)\)" class="layer-([^"]+)">'
)
_KEY_RE = re.compile(
    r'transform="translate\(([\d.-]+),\s*([\d.-]+)\)" class="key keypos-(\d+)"[^>]*>\s*'
    r'<rect[^>]*x="([^"]+)"[^>]*y="([^"]+)"[^>]*width="([^"]+)"[^>]*height="([^"]+)"',
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


def _layer_chunks(svg: str) -> list[tuple[str, float, float, str]]:
    """Return (name, x, y, inner_svg) for each layer group."""
    starts = list(_LAYER_RE.finditer(svg))
    out: list[tuple[str, float, float, str]] = []
    for i, m in enumerate(starts):
        end = starts[i + 1].start() if i + 1 < len(starts) else len(svg)
        out.append((m.group(3), float(m.group(1)), float(m.group(2)), svg[m.end() : end]))
    return out


def _key_bounds(chunk: str) -> list[dict[str, float]]:
    keys: list[dict[str, float]] = []
    for m in _KEY_RE.finditer(chunk):
        kx, ky, pos, rx, ry, rw, rh = m.groups()
        kx, ky, rx, ry, rw, rh = map(float, (kx, ky, rx, ry, rw, rh))
        keys.append(
            {
                "pos": float(pos),
                "left": kx + rx,
                "right": kx + rx + rw,
                "top": ky + ry,
                "bottom": ky + ry + rh,
            }
        )
    return keys


def _divider_lines(svg: str, board_w: float, board_h: float) -> list[str]:
    """H gutters between layer rows; V through each keyboard's L/R half-gap."""
    margin = 24.0
    layers = _layer_chunks(svg)
    if not layers:
        return []

    # Per layer: absolute content bottom + relative L/R half-gap midpoint.
    row_bottoms: dict[float, float] = defaultdict(float)
    col_gap_x: dict[float, float] = {}
    for _name, lx, ly, chunk in layers:
        keys = _key_bounds(chunk)
        if not keys:
            continue
        bottom = max(k["bottom"] for k in keys)
        row_bottoms[ly] = max(row_bottoms[ly], ly + bottom)

        left = [k for k in keys if int(k["pos"]) % 2 == 0]
        right = [k for k in keys if int(k["pos"]) % 2 == 1]
        if left and right:
            gap_mid = (max(k["right"] for k in left) + min(k["left"] for k in right)) / 2
            col_gap_x[lx] = lx + gap_mid

    ys = sorted(row_bottoms)
    layer_ys = sorted({ly for _n, _x, ly, _c in layers})

    lines = [
        '<g id="layer-dividers" fill="none" stroke="#8b949e" '
        'stroke-width="2" stroke-linecap="butt">'
    ]

    # Horizontal: midpoint of the gutter between one row's keys and the next row.
    if len(layer_ys) >= 2:
        for i in range(len(layer_ys) - 1):
            y_top = layer_ys[i]
            y_next = layer_ys[i + 1]
            content_bottom = row_bottoms.get(y_top, y_top)
            y = round((content_bottom + y_next) / 2, 1)
            lines.append(
                f'<line class="layer-divider-h" x1="{margin}" y1="{y}" '
                f'x2="{board_w - margin}" y2="{y}"/>'
            )

    # Vertical: one line per layer column, through that keyboard's half-gap
    # (not the page-column midpoint, which cuts through keys).
    for x in sorted(col_gap_x.values()):
        x = round(x, 1)
        lines.append(
            f'<line class="layer-divider-v" x1="{x}" y1="{margin}" '
            f'x2="{x}" y2="{board_h - margin}"/>'
        )

    lines.append("</g>")
    return lines


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

    size = re.search(r'<svg[^>]*width="([\d.]+)"[^>]*height="([\d.]+)"', svg)
    board_w = float(size.group(1)) if size else 1000.0
    board_h = float(size.group(2)) if size else 1000.0

    dividers = _divider_lines(svg, board_w, board_h)
    if not dividers:
        return svg

    return svg.replace(
        '<rect id="page-bg" width="100%" height="100%" fill="#ffffff"/>',
        '<rect id="page-bg" width="100%" height="100%" fill="#ffffff"/>\n'
        + "\n".join(dividers),
        1,
    )


def main() -> None:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "keymap-drawer/keymap.svg")
    path.write_text(postprocess(path.read_text(encoding="utf-8")), encoding="utf-8")


if __name__ == "__main__":
    main()
