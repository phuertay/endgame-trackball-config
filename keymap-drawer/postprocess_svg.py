#!/usr/bin/env python3
"""Post-process keymap-drawer SVG: white page + H/V layer dividers + glyph fix."""

from __future__ import annotations

import re
import sys
from pathlib import Path

# Extra vertical space between layer rows so H-dividers clear encoders.
# keymap-drawer packs rows flush (key bottoms ≈ next layer top).
_ROW_GAP = 40.0

_LAYER_RE = re.compile(
    r'<g transform="translate\(([\d.]+),\s*([\d.]+)\)" class="layer-([^"]+)">'
)
_KEY_RE = re.compile(
    r'transform="translate\(([\d.-]+),\s*([\d.-]+)\)" class="key keypos-(\d+)"[^>]*>\s*'
    r'<rect[^>]*x="([^"]+)"[^>]*y="([^"]+)"[^>]*width="([^"]+)"[^>]*height="([^"]+)"',
)
# keymap-drawer wraps keys in <g transform="translate(0, label_h)"> after the title.
_INNER_SHIFT_RE = re.compile(
    r'<g transform="translate\(([\d.-]+),\s*([\d.-]+)\)">\s*'
    r'<g transform="translate\([^)]+\)" class="key keypos-'
)
# Nested <svg> glyph defs from keymap-drawer do not paint under rsvg-convert.
_NESTED_GLYPH_RE = re.compile(
    r'<svg id="([^"]+)">\s*<svg\b[^>]*viewBox="([^"]*)"[^>]*>(.*?)</svg>\s*</svg>\s*',
    re.DOTALL,
)


def _fix_glyphs(svg: str) -> str:
    """Flatten nested glyph <svg> defs into paintable <symbol>s with fill."""

    def repl(m: re.Match[str]) -> str:
        gid, viewbox, inner = m.group(1), m.group(2), m.group(3)
        # Ensure paths paint under rsvg (MDI SVGs rely on currentColor).
        inner = re.sub(
            r"<path\b(?![^>]*\bfill=)",
            '<path fill="#1a1d21"',
            inner,
        )
        return f'<symbol id="{gid}" viewBox="{viewbox}">{inner}</symbol>\n'

    svg = _NESTED_GLYPH_RE.sub(repl, svg)
    # Drop stray closers left by older bad replaces.
    svg = re.sub(r"(/\* start glyphs \*/\s*)\n?</svg>\s*", r"\1\n", svg)
    return svg


def _layer_chunks(svg: str) -> list[tuple[str, float, float, str]]:
    starts = list(_LAYER_RE.finditer(svg))
    out: list[tuple[str, float, float, str]] = []
    for i, m in enumerate(starts):
        end = starts[i + 1].start() if i + 1 < len(starts) else len(svg)
        out.append((m.group(3), float(m.group(1)), float(m.group(2)), svg[m.end() : end]))
    return out


def _key_bounds(chunk: str) -> list[dict[str, float]]:
    """Key rects in layer-local coords (includes label→keys inner translate)."""
    inner_x = inner_y = 0.0
    if m := _INNER_SHIFT_RE.search(chunk):
        inner_x, inner_y = float(m.group(1)), float(m.group(2))

    keys: list[dict[str, float]] = []
    for m in _KEY_RE.finditer(chunk):
        kx, ky, _pos, rx, ry, rw, rh = m.groups()
        kx, ky, rx, ry, rw, rh = map(float, (kx, ky, rx, ry, rw, rh))
        keys.append(
            {
                "left": inner_x + kx + rx,
                "right": inner_x + kx + rx + rw,
                "top": inner_y + ky + ry,
                "bottom": inner_y + ky + ry + rh,
            }
        )
    return keys


def _expand_row_gaps(svg: str) -> tuple[str, float]:
    """Shift layer rows apart and grow the viewBox/height. Returns (svg, extra_h)."""
    ys = sorted({float(m.group(2)) for m in _LAYER_RE.finditer(svg)})
    if len(ys) < 2:
        return svg, 0.0

    # Map original y -> y + ROW_GAP * row_index
    y_to_row = {y: i for i, y in enumerate(ys)}
    added = _ROW_GAP * (len(ys) - 1)

    def shift_layer(m: re.Match[str]) -> str:
        x, y, name = m.group(1), float(m.group(2)), m.group(3)
        new_y = y + _ROW_GAP * y_to_row[y]
        return f'<g transform="translate({x}, {new_y})" class="layer-{name}">'

    svg = _LAYER_RE.sub(shift_layer, svg)

    # Grow svg height / viewBox.
    def grow_svg(m: re.Match[str]) -> str:
        tag = m.group(0)
        # height="N"
        tag = re.sub(
            r'\bheight="([\d.]+)"',
            lambda mm: f'height="{float(mm.group(1)) + added}"',
            tag,
            count=1,
        )
        # viewBox="0 0 W H"
        tag = re.sub(
            r'\bviewBox="([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)"',
            lambda mm: (
                f'viewBox="{mm.group(1)} {mm.group(2)} {mm.group(3)} '
                f'{float(mm.group(4)) + added}"'
            ),
            tag,
            count=1,
        )
        return tag

    svg = re.sub(r"<svg\b[^>]*>", grow_svg, svg, count=1)

    # Footer sits near the old bottom — nudge it down with the last row gap.
    def shift_footer(m: re.Match[str]) -> str:
        x, y = m.group(1), float(m.group(2))
        return f'<text x="{x}" y="{y + added}" class="footer">'

    svg = re.sub(
        r'<text x="([^"]+)" y="([\d.]+)" class="footer">',
        shift_footer,
        svg,
        count=1,
    )
    return svg, added


def _divider_lines(svg: str, board_w: float, board_h: float) -> list[str]:
    """H/V lines in gutters between layer cards — never through keycaps."""
    margin = 24.0
    layers = _layer_chunks(svg)
    if not layers:
        return []

    xs = sorted({lx for _n, lx, _ly, _c in layers})
    ys = sorted({ly for _n, _lx, ly, _c in layers})

    content_right: dict[float, float] = {x: x for x in xs}
    content_bottom: dict[float, float] = {y: y for y in ys}
    for _name, lx, ly, chunk in layers:
        keys = _key_bounds(chunk)
        if not keys:
            continue
        content_right[lx] = max(
            content_right[lx], lx + max(k["right"] for k in keys)
        )
        content_bottom[ly] = max(
            content_bottom[ly], ly + max(k["bottom"] for k in keys)
        )

    lines = [
        '<g id="layer-dividers" fill="none" stroke="#8b949e" '
        'stroke-width="2" stroke-linecap="butt">'
    ]

    # Horizontal: midpoint of the free gutter below encoders / above next row.
    if len(ys) >= 2:
        for i in range(len(ys) - 1):
            bottom = content_bottom[ys[i]]
            next_top = ys[i + 1]
            y = round((bottom + next_top) / 2, 1)
            lines.append(
                f'<line class="layer-divider-h" x1="{margin}" y1="{y}" '
                f'x2="{board_w - margin}" y2="{y}"/>'
            )

    # Vertical: midpoint of gutter between left-column content and right column.
    if len(xs) >= 2:
        x = round((content_right[xs[0]] + xs[1]) / 2, 1)
        lines.append(
            f'<line class="layer-divider-v" x1="{x}" y1="{margin}" '
            f'x2="{x}" y2="{board_h - margin}"/>'
        )

    lines.append("</g>")
    return lines


# PrtSc is landscape and reads tiny at glyph_tap_size; multiply <use> box.
_PRTSC_USE_SCALE = 2.0
_PRTSC_USE_RE = re.compile(
    r'(<use href="#prtsc-sign" xlink:href="#prtsc-sign" )'
    r'x="[^"]*" y="[^"]*" height="([^"]*)" width="([^"]*)"'
)


def _scale_prtsc_uses(svg: str, scale: float = _PRTSC_USE_SCALE) -> str:
    def repl(m: re.Match[str]) -> str:
        h, w = float(m.group(2)), float(m.group(3))
        nh, nw = h * scale, w * scale
        return f'{m.group(1)}x="{-nw / 2}" y="{-nh / 2}" height="{nh:g}" width="{nw:g}"'

    return _PRTSC_USE_RE.sub(repl, svg)


def postprocess(svg: str) -> str:
    # Strip leftover frames/dividers so re-runs stay idempotent.
    svg = re.sub(r'\n?<rect class="layer-frame"[^/]*/>', "", svg)
    svg = re.sub(
        r'\n?<g id="layer-dividers\b[^"]*"[^>]*>.*?</g>',
        "",
        svg,
        flags=re.DOTALL,
    )
    svg = _fix_glyphs(svg)
    svg = _scale_prtsc_uses(svg)

    # Undo a previous row-gap expand if re-run on already-processed SVG:
    # (layers already shifted — detect via gap vs content). Always expand from
    # keymap-drawer output which packs rows flush; idempotent re-run needs the
    # raw draw output. Callers regenerate SVG before postprocess.

    svg, _added = _expand_row_gaps(svg)

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
