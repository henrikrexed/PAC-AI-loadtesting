#!/usr/bin/env python3
"""
build_pdf.py — assemble the 21 composed slides into PAC-deck-matrix.pdf (ISI-5794).

A single 16:9 PDF is the projector-ready / import-ready export: it mirrors how the v1
'Stop Guessing' deck is consumed on stage, imports cleanly into Keynote / Google Slides /
PowerPoint (one full-bleed image per slide), and prints as speaker handouts. 21 pages.

Slide order is the canonical A-order (narrative-and-slide-copy.md rev4), taken straight from
gen_deck.SLIDES so the PDF can never drift from the generator.
"""
import os
from PIL import Image
import gen_deck

HERE = os.path.dirname(__file__)
IMG = os.path.join(HERE, "images")
OUTPDF = os.path.join(HERE, "PAC-deck-matrix.pdf")

# derive the ordered filename list from each slide fn's save_slide(...) call
import re, inspect
names = []
for fn in gen_deck.SLIDES:
    src = inspect.getsource(fn)
    m = re.search(r'save_slide\(img,\s*"([^"]+\.png)"\)', src)
    assert m, f"no save_slide filename found in {fn.__name__}"
    names.append(m.group(1))

assert len(names) == 21, f"expected 21 slides, derived {len(names)}"
paths = [os.path.join(IMG, n) for n in names]
for p in paths:
    assert os.path.exists(p), f"missing slide: {p}"

imgs = [Image.open(p).convert("RGB") for p in paths]
imgs[0].save(OUTPDF, "PDF", save_all=True, append_images=imgs[1:], resolution=144.0)
print(f"wrote {OUTPDF}  ({len(imgs)} pages, {imgs[0].size[0]}x{imgs[0].size[1]})")
for i, n in enumerate(names, 1):
    print(f"  {i:2d}. {n}")
