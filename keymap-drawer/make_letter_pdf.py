#!/usr/bin/env python3
"""Fit one or more keymap SVGs onto US Letter pages and merge into a PDF."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

# Keep margin in sync with postprocess_svg._LETTER_MARGIN_IN
MARGIN_IN = 0.35
PORTRAIT = (8.5, 11.0)
LANDSCAPE = (11.0, 8.5)


def _svg_size(svg: Path) -> tuple[float, float]:
    text = svg.read_text(encoding="utf-8")
    m = re.search(r'\bwidth="([\d.]+)"[^>]*\bheight="([\d.]+)"', text)
    if not m:
        sys.exit(f"no width/height on {svg}")
    return float(m.group(1)), float(m.group(2))


def _pick_orientation(w_px: float, h_px: float) -> tuple[float, float]:
    """Prefer the Letter orientation that wastes less margin."""
    content = w_px / h_px
    portrait_aspect = PORTRAIT[0] / PORTRAIT[1]
    landscape_aspect = LANDSCAPE[0] / LANDSCAPE[1]
    # Closer aspect ratio → less letterboxing.
    if abs(content - landscape_aspect) < abs(content - portrait_aspect):
        return LANDSCAPE
    return PORTRAIT


def _fit_page(
    w_px: float, h_px: float, page_w: float, page_h: float
) -> tuple[float, float, float, float]:
    """Return image width/height and left/top offsets in inches."""
    usable_w = page_w - 2 * MARGIN_IN
    usable_h = page_h - 2 * MARGIN_IN
    img_w = usable_w
    img_h = usable_w * (h_px / w_px)
    if img_h > usable_h:
        img_h = usable_h
        img_w = usable_h * (w_px / h_px)
    left = (page_w - img_w) / 2
    top = (page_h - img_h) / 2
    return img_w, img_h, left, top


def svg_to_letter_pdf(
    svg: Path, pdf: Path, orientation: str = "auto"
) -> tuple[float, float]:
    w_px, h_px = _svg_size(svg)
    if orientation == "landscape":
        page_w, page_h = LANDSCAPE
    elif orientation == "portrait":
        page_w, page_h = PORTRAIT
    else:
        page_w, page_h = _pick_orientation(w_px, h_px)
    img_w, img_h, left, top = _fit_page(w_px, h_px, page_w, page_h)
    subprocess.check_call(
        [
            "rsvg-convert",
            "-f",
            "pdf",
            "-b",
            "white",
            "--page-width",
            f"{page_w}in",
            "--page-height",
            f"{page_h}in",
            "-w",
            f"{img_w}in",
            "--left",
            f"{left}in",
            "--top",
            f"{top}in",
            str(svg),
            "-o",
            str(pdf),
        ]
    )
    return page_w, page_h


def merge_pdfs(pages: list[Path], out: Path) -> None:
    if len(pages) == 1:
        out.write_bytes(pages[0].read_bytes())
        return
    subprocess.check_call(["pdfunite", *[str(p) for p in pages], str(out)])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("svgs", nargs="+", type=Path, help="SVG page(s) in order")
    ap.add_argument("-o", "--output", type=Path, required=True)
    ap.add_argument(
        "--orientation",
        action="append",
        choices=("auto", "portrait", "landscape"),
        help="per-page orientation (repeat for each SVG; default auto)",
    )
    args = ap.parse_args()
    orients = args.orientation or []
    while len(orients) < len(args.svgs):
        orients.append("auto")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        page_pdfs: list[Path] = []
        for i, (svg, orient) in enumerate(zip(args.svgs, orients), start=1):
            pdf = tmp_path / f"page{i}.pdf"
            page_w, page_h = svg_to_letter_pdf(svg, pdf, orient)
            print(f"  {svg.name}: {page_w:g}×{page_h:g}in ({orient})")
            page_pdfs.append(pdf)
        merge_pdfs(page_pdfs, args.output)
    print(f"wrote {args.output} ({len(args.svgs)} letter page(s))")


if __name__ == "__main__":
    main()
