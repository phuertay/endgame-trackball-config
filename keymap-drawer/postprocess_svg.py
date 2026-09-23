#!/usr/bin/env python3
"""Post-process keymap-drawer SVG: white page + H/V layer dividers + glyph fix."""

from __future__ import annotations

import re
import sys
from pathlib import Path

_LAYER_RE = re.compile(
    r'<g transform="translate\(([\d.]+),\s*([\d.]+)\)" class="layer-([^"]+)">'
)
_KEY_RE = re.compile(
    r'transform="translate\(([\d.-]+),\s*([\d.-]+)\)" class="key keypos-(\d+)"[^>]*>\s*'
    r'<rect[^>]*x="([^"]+)"[^>]*y="([^"]+)"[^>]*width="([^"]+)"[^>]*height="([^"]+)"',
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
    keys: list[dict[str, float]] = []
    for m in _KEY_RE.finditer(chunk):
        kx, ky, _pos, rx, ry, rw, rh = m.groups()
        kx, ky, rx, ry, rw, rh = map(float, (kx, ky, rx, ry, rw, rh))
        keys.append(
            {
                "left": kx + rx,
                "right": kx + rx + rw,
                "top": ky + ry,
                "bottom": ky + ry + rh,
            }
        )
    return keys


def _divider_lines(svg: str, board_w: float, board_h: float) -> list[str]:
    """H/V lines in gutters between layer cards — never through keycaps."""
    margin = 24.0
    layers = _layer_chunks(svg)
    if not layers:
        return []

    xs = sorted({lx for _n, lx, _ly, _c in layers})
    ys = sorted({ly for _n, _lx, ly, _c in layers})

    # Absolute content extents per layer origin.
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

    # Horizontal: sit just above the next layer row, with clear space
    # below the previous row's encoders (mid-gutter overlapped them).
    if len(ys) >= 2:
        for i in range(len(ys) - 1):
            bottom = content_bottom[ys[i]]
            next_top = ys[i + 1]
            gap = next_top - bottom
            # Prefer near the next layer; keep ≥14px clear of encoders.
            y = round(next_top - 12, 1)
            if y < bottom + 14:
                y = round(bottom + max(gap * 0.75, 14), 1)
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
