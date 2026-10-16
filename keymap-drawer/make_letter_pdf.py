#!/usr/bin/env python3
"""Fit one or more keymap SVGs onto US Letter pages and merge into a PDF."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

LETTER_W_IN = 8.5
LETTER_H_IN = 11.0
MARGIN_IN = 0.4


def _svg_size(svg: Path) -> tuple[float, float]:
    text = svg.read_text(encoding="utf-8")
    m = re.search(r'\bwidth="([\d.]+)"[^>]*\bheight="([\d.]+)"', text)
    if not m:
        sys.exit(f"no width/height on {svg}")
    return float(m.group(1)), float(m.group(2))


def _fit_letter(w_px: float, h_px: float) -> tuple[float, float, float, float]:
    """Return image width/height and left/top offsets in inches."""
    usable_w = LETTER_W_IN - 2 * MARGIN_IN
    usable_h = LETTER_H_IN - 2 * MARGIN_IN
    img_w = usable_w
    img_h = usable_w * (h_px / w_px)
    if img_h > usable_h:
        img_h = usable_h
        img_w = usable_h * (w_px / h_px)
    left = (LETTER_W_IN - img_w) / 2
    top = (LETTER_H_IN - img_h) / 2
    return img_w, img_h, left, top


def svg_to_letter_pdf(svg: Path, pdf: Path) -> None:
    w_px, h_px = _svg_size(svg)
    img_w, img_h, left, top = _fit_letter(w_px, h_px)
    subprocess.check_call(
        [
            "rsvg-convert",
            "-f",
            "pdf",
            "-b",
            "white",
            "--page-width",
            f"{LETTER_W_IN}in",
            "--page-height",
            f"{LETTER_H_IN}in",
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


def merge_pdfs(pages: list[Path], out: Path) -> None:
    if len(pages) == 1:
        out.write_bytes(pages[0].read_bytes())
        return
    subprocess.check_call(["pdfunite", *[str(p) for p in pages], str(out)])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("svgs", nargs="+", type=Path, help="SVG page(s) in order")
    ap.add_argument("-o", "--output", type=Path, required=True)
    args = ap.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        page_pdfs: list[Path] = []
        for i, svg in enumerate(args.svgs, start=1):
            pdf = tmp_path / f"page{i}.pdf"
            svg_to_letter_pdf(svg, pdf)
            page_pdfs.append(pdf)
        merge_pdfs(page_pdfs, args.output)
    print(f"wrote {args.output} ({len(args.svgs)} letter page(s))")


if __name__ == "__main__":
    main()
