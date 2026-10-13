#!/usr/bin/env python3
"""
qr_util.py — real (scannable) QR rendering for the PAC deck, themed to match mtx_theme.

The public mirror github.com/henrikrexed/AI-Performance-Testing went live (ISI-5659), so the
slide-13 + slide-21 QR codes are now REAL, not placeholders. Uses segno (pure-python, offline)
to encode, then paints the module matrix with Pillow so it inherits the deck's dark/green look.

Keep QR contrast high: light modules on a dark quiet-zone read fine for phone cameras as long
as the module pixel size is generous. On stage, prefer the large slide-21 QR for actual scanning.
"""
import segno
from PIL import ImageDraw

REPO_URL = "https://github.com/henrikrexed/AI-Performance-Testing"

def qr_matrix(url=REPO_URL, error="m"):
    """Return (matrix rows of 0/1, size) for the smallest QR encoding `url`."""
    qr = segno.make(url, error=error)
    rows = [list(r) for r in qr.matrix]  # each cell 0/1
    return rows, len(rows)

def draw_qr(draw: ImageDraw.ImageDraw, top_left, box_px, url=REPO_URL,
            dark=(234, 243, 236), light=None, quiet=2, error="m"):
    """Paint a real QR into a box_px square at top_left.
    dark  = color of the 'on' modules (default INK, so it reads light-on-dark);
    light = color of the 'off' modules / quiet zone (None -> leave transparent).
    Returns the actual pixel size drawn (square)."""
    rows, n = qr_matrix(url, error=error)
    total = n + quiet * 2
    cell = max(1, box_px // total)
    size = cell * total
    x0, y0 = top_left
    if light is not None:
        draw.rectangle([x0, y0, x0 + size, y0 + size], fill=light)
    for yi, row in enumerate(rows):
        for xi, v in enumerate(row):
            if v:
                px = x0 + (xi + quiet) * cell
                py = y0 + (yi + quiet) * cell
                draw.rectangle([px, py, px + cell - 1, py + cell - 1], fill=dark)
    return size

if __name__ == "__main__":
    rows, n = qr_matrix()
    print(f"qr_util OK · {REPO_URL} -> {n}x{n} modules")
