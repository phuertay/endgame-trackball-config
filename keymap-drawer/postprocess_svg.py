#!/usr/bin/env python3
"""Post-process keymap-drawer SVG: white page + H/V layer dividers + glyph fix."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Extra vertical space between layer rows so H-dividers clear encoders.
# keymap-drawer packs rows flush (key bottoms ≈ next layer top).
_ROW_GAP = 40.0

# US Letter usable aspect (width/height) after make_letter_pdf margins.
_LETTER_MARGIN_IN = 0.35
_LETTER_PORTRAIT_ASPECT = (8.5 - 2 * _LETTER_MARGIN_IN) / (
    11.0 - 2 * _LETTER_MARGIN_IN
)
_LETTER_LANDSCAPE_ASPECT = (11.0 - 2 * _LETTER_MARGIN_IN) / (
    8.5 - 2 * _LETTER_MARGIN_IN
)

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


def _svg_size(svg: str) -> tuple[float, float]:
    m = re.search(r'<svg[^>]*\bwidth="([\d.]+)"[^>]*\bheight="([\d.]+)"', svg)
    if not m:
        raise ValueError("svg missing width/height")
    return float(m.group(1)), float(m.group(2))


def _grow_svg_size(svg: str, new_w: float | None = None, new_h: float | None = None) -> str:
    def grow(m: re.Match[str]) -> str:
        tag = m.group(0)
        if new_w is not None:
            tag = re.sub(
                r'\bwidth="([\d.]+)"',
                f'width="{new_w:g}"',
                tag,
                count=1,
            )
        if new_h is not None:
            tag = re.sub(
                r'\bheight="([\d.]+)"',
                f'height="{new_h:g}"',
                tag,
                count=1,
            )

        def vb(mm: re.Match[str]) -> str:
            x, y, w, h = mm.groups()
            w2 = f"{new_w:g}" if new_w is not None else w
            h2 = f"{new_h:g}" if new_h is not None else h
            return f'viewBox="{x} {y} {w2} {h2}"'

        tag = re.sub(
            r'\bviewBox="([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)"',
            vb,
            tag,
            count=1,
        )
        return tag

    return re.sub(r"<svg\b[^>]*>", grow, svg, count=1)


def _center_orphan_row(svg: str) -> str:
    """Center a final single-layer row under a two-column row above it."""
    board_w, _board_h = _svg_size(svg)
    matches = list(_LAYER_RE.finditer(svg))
    if len(matches) < 3:
        return svg

    by_y: dict[float, list[re.Match[str]]] = {}
    for m in matches:
        by_y.setdefault(float(m.group(2)), []).append(m)
    ys = sorted(by_y)
    if len(ys) < 2 or len(by_y[ys[-1]]) != 1:
        return svg
    if len(by_y[ys[-2]]) < 2:
        return svg

    xs = sorted({float(m.group(1)) for m in by_y[ys[-2]]})
    pitch = xs[1] - xs[0]
    new_x = (board_w - pitch) / 2
    orphan = by_y[ys[-1]][0]
    old = orphan.group(0)
    repl = (
        f'<g transform="translate({new_x:g}, {orphan.group(2)})" '
        f'class="layer-{orphan.group(3)}">'
    )
    return svg.replace(old, repl, 1)


def _fit_letter_aspect(
    svg: str, aspect: float = _LETTER_PORTRAIT_ASPECT
) -> str:
    """Pad row gaps / sides so the canvas matches US Letter usable aspect."""
    svg = _center_orphan_row(svg)
    board_w, board_h = _svg_size(svg)
    if board_w <= 0 or board_h <= 0:
        return svg

    current = board_w / board_h
    ys = sorted({float(m.group(2)) for m in _LAYER_RE.finditer(svg)})
    y_to_row = {y: i for i, y in enumerate(ys)}

    if current > aspect + 0.005:
        # Too wide for the target Letter orientation — grow height.
        target_h = board_w / aspect
        extra = target_h - board_h
        n_gaps = max(len(ys) - 1, 0)
        # Full rectangular grids (e.g. 3×2 page 1): breathe between rows.
        # Orphan pyramids (page 2): keep the pair tight and pad top/bottom.
        by_y: dict[float, int] = {}
        for m in _LAYER_RE.finditer(svg):
            by_y[float(m.group(2))] = by_y.get(float(m.group(2)), 0) + 1
        row_counts = [by_y[y] for y in ys]
        full_grid = bool(row_counts) and len(set(row_counts)) == 1 and row_counts[0] >= 2
        # Cap per-row gutter growth — dumping most of a Letter-aspect pad into
        # a single 2-row gap makes the page look hollow.
        _MAX_EXTRA_GAP = 100.0
        if n_gaps and full_grid:
            gap_extra = min(extra * 0.55, _MAX_EXTRA_GAP * n_gaps)
            pad_extra = extra - gap_extra
            per_gap = gap_extra / n_gaps
        else:
            per_gap = 0.0
            pad_extra = extra
        top_pad = pad_extra / 2

        def shift_layer(m: re.Match[str]) -> str:
            x, y, name = m.group(1), float(m.group(2)), m.group(3)
            new_y = y + top_pad + per_gap * y_to_row[y]
            return f'<g transform="translate({x}, {new_y:g})" class="layer-{name}">'

        svg = _LAYER_RE.sub(shift_layer, svg)
        svg = _grow_svg_size(svg, new_h=target_h)

        def shift_footer(m: re.Match[str]) -> str:
            x, y = m.group(1), float(m.group(2))
            # Keep footer near the content block, not the page bottom.
            content_shift = top_pad + per_gap * max(len(ys) - 1, 0)
            return f'<text x="{x}" y="{y + content_shift:g}" class="footer">'

        svg = re.sub(
            r'<text x="([^"]+)" y="([\d.]+)" class="footer">',
            shift_footer,
            svg,
            count=1,
        )
        return svg

    # Too-narrow canvases (e.g. a 1-column page) are left alone so
    # make_letter_pdf can scale them up to Letter height — padding here
    # would only shrink the boards on the printed page.
    return svg


def _divider_lines(svg: str, board_w: float, board_h: float) -> list[str]:
    """H/V lines in gutters between layer cards — never through keycaps."""
    margin = 24.0
    layers = _layer_chunks(svg)
    if not layers:
        return []

    ys = sorted({ly for _n, _lx, ly, _c in layers})

    content_right: dict[float, float] = {}
    content_bottom: dict[float, float] = {y: y for y in ys}
    rows: dict[float, list[tuple[str, float, str]]] = {y: [] for y in ys}
    for name, lx, ly, chunk in layers:
        rows[ly].append((name, lx, chunk))
        keys = _key_bounds(chunk)
        if not keys:
            continue
        content_right[lx] = max(
            content_right.get(lx, lx), lx + max(k["right"] for k in keys)
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

    # Vertical: only through rows that actually have two columns.
    # Ignore centered orphan x positions so the gutter stays between col 0/1.
    two_col_ys = [y for y in ys if len({lx for _n, lx, _c in rows[y]}) >= 2]
    if two_col_ys:
        col_xs = sorted({lx for y in two_col_ys for _n, lx, _c in rows[y]})
        if len(col_xs) >= 2:
            x = round(
                (content_right.get(col_xs[0], col_xs[0]) + col_xs[1]) / 2, 1
            )
            y0 = min(two_col_ys)
            y1 = max(two_col_ys)
            top = max(margin, y0)
            bottom = min(board_h - margin, content_bottom[y1])
            if bottom > top:
                lines.append(
                    f'<line class="layer-divider-v" x1="{x}" y1="{top}" '
                    f'x2="{x}" y2="{bottom}"/>'
                )

    lines.append("</g>")
    return lines


# PrtSc is landscape; keep <use> at glyph_tap_size (no extra boost).
# Was 1.5 (84×42 from base 56×28); still read too large on the key.
_PRTSC_USE_SCALE = 1.0
_PRTSC_USE_RE = re.compile(
    r'(<use href="#prtsc-sign" xlink:href="#prtsc-sign" )'
    r'x="[^"]*" y="[^"]*" height="([^"]*)" width="([^"]*)"'
)

# BT clear sits on a wide top key, so keymap-drawer parks the right-side ✕
# at the far edge (x≈24) while BT stays centered — looks detached. Nudge
# it to the same offset as BT+arrow on the narrower side keys (x=7).
_BT_CLOSE_X = 7
_BT_CLOSE_RE = re.compile(
    r'(<use href="#mdi:bluetooth" xlink:href="#mdi:bluetooth"[^/]*/>\s*'
    r'<use href="#mdi:close" xlink:href="#mdi:close" )'
    r'x="[^"]*"'
)


def _scale_prtsc_uses(svg: str, scale: float = _PRTSC_USE_SCALE) -> str:
    def repl(m: re.Match[str]) -> str:
        h, w = float(m.group(2)), float(m.group(3))
        nh, nw = h * scale, w * scale
        return f'{m.group(1)}x="{-nw / 2}" y="{-nh / 2}" height="{nh:g}" width="{nw:g}"'

    return _PRTSC_USE_RE.sub(repl, svg)


def _nudge_bt_close(svg: str, x: float = _BT_CLOSE_X) -> str:
    return _BT_CLOSE_RE.sub(rf'\1x="{x:g}"', svg)


def postprocess(
    svg: str,
    *,
    letter: bool = False,
    letter_landscape: bool = False,
    center_orphan: bool = False,
) -> str:
    # Strip leftover frames/dividers so re-runs stay idempotent.
    svg = re.sub(r'\n?<rect class="layer-frame"[^/]*/>', "", svg)
    svg = re.sub(
        r'\n?<g id="layer-dividers\b[^"]*"[^>]*>.*?</g>',
        "",
        svg,
        flags=re.DOTALL,
    )
    svg = re.sub(r'\n?<rect id="page-bg"[^/]*/>', "", svg)
    svg = _fix_glyphs(svg)
    svg = _scale_prtsc_uses(svg)
    svg = _nudge_bt_close(svg)

    # Undo a previous row-gap expand if re-run on already-processed SVG:
    # (layers already shifted — detect via gap vs content). Always expand from
    # keymap-drawer output which packs rows flush; idempotent re-run needs the
    # raw draw output. Callers regenerate SVG before postprocess.

    svg, _added = _expand_row_gaps(svg)
    if letter_landscape:
        svg = _fit_letter_aspect(svg, aspect=_LETTER_LANDSCAPE_ASPECT)
    elif letter:
        svg = _fit_letter_aspect(svg, aspect=_LETTER_PORTRAIT_ASPECT)
    elif center_orphan:
        svg = _center_orphan_row(svg)

    svg = re.sub(
        r"(<svg\b[^>]*>)",
        r'\1\n<rect id="page-bg" width="100%" height="100%" fill="#ffffff"/>',
        svg,
        count=1,
    )

    board_w, board_h = _svg_size(svg)
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
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("svg", nargs="?", default="keymap-drawer/keymap.svg")
    ap.add_argument(
        "--letter",
        action="store_true",
        help="pad canvas to portrait US Letter usable aspect",
    )
    ap.add_argument(
        "--letter-landscape",
        action="store_true",
        help="pad canvas to landscape US Letter usable aspect",
    )
    ap.add_argument(
        "--center-orphan",
        action="store_true",
        help="center a final single-layer row under a two-column row",
    )
    args = ap.parse_args()
    path = Path(args.svg)
    path.write_text(
        postprocess(
            path.read_text(encoding="utf-8"),
            letter=args.letter,
            letter_landscape=args.letter_landscape,
            center_orphan=args.center_orphan,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
