#!/usr/bin/env python3
"""
kl_k.py — Knightload K-letterform directions (ISI-5779 round 3.1).

Board feedback (Henrik, 2026-10-13): "j'aime le K mais le reste n'était pas top."
=> KEEP the K monogram; DROP the knight/helm/shield illustrations. Evolve the LETTER.

Four geometric K directions, each built to survive the guardrails:
  - legible as a favicon at 16 px (no story that needs explaining),
  - mandatory monochrome variant,
  - no literal horse/knight/shield — any strategy nod is pure geometry.

K1 Ramp-K     — K whose upper diagonal thickens into an ascending throughput ramp.
K2 Signal-K   — K drawn as line-chart strokes with data-point nodes (flat stem, 2 rising arms).
K3 Facet-K    — K folded from 3 angular planes; the diagonals carry a faint knight/strategy
                subtext as geometry only (two-tone).
K4 Nightfall-K— solid geometric K, deep-night gradient fill, one accent stroke on the ramp edge.

Pure-Pillow + DejaVu, 4x supersample. Reuses the kl_brand palette/helpers.
"""
import math
from PIL import Image, ImageDraw
import kl_brand as kl

SS = kl.SS
INDIGO0, INDIGO1, INDIGO2 = kl.INDIGO0, kl.INDIGO1, kl.INDIGO2
SILVER, SILVER_HI, SILVER_DIM = kl.SILVER, kl.SILVER_HI, kl.SILVER_DIM
CYAN, AMBER, INK = kl.CYAN, kl.AMBER, kl.INK
NIGHT = (11, 14, 26)  # near-black night end of the gradient

def _tile(size):
    W = size * SS
    img = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img), W

def _pts(W, seq):
    return [(x * W, y * W) for (x, y) in seq]


# ---------------------------------------------------------------- K1 Ramp-K
def k_ramp(size, mono=False, accent=CYAN, silh=SILVER):
    img, d, W = _tile(size)
    stem = silh
    ramp = silh if mono else accent
    # stem
    d.rounded_rectangle(_pts(W, [(0.17, 0.13), (0.30, 0.87)])[0] + _pts(W, [(0.17, 0.13), (0.30, 0.87)])[1],
                        radius=0.03 * W, fill=stem + (255,))
    # leg (lower arm) — constant-width diagonal
    d.polygon(_pts(W, [(0.30, 0.52), (0.72, 0.87), (0.85, 0.87), (0.43, 0.49)]), fill=stem + (255,))
    # upper arm — wedge thickening toward the top-right (the ramp)
    d.polygon(_pts(W, [(0.30, 0.45), (0.86, 0.09), (0.60, 0.27), (0.41, 0.55)]), fill=ramp + (255,))
    return img.resize((size, size), Image.LANCZOS)


# ---------------------------------------------------------------- K2 Signal-K
def k_signal(size, mono=False, accent=CYAN, silh=SILVER):
    img, d, W = _tile(size)
    node = silh if mono else accent
    lw = int(0.085 * W)
    def line(seq):
        p = _pts(W, seq)
        d.line(p, fill=silh + (255,), width=lw, joint="curve")
        for (x, y) in [p[0], p[-1]]:
            d.ellipse([x - lw / 2, y - lw / 2, x + lw / 2, y + lw / 2], fill=silh + (255,))
    # flat stem baseline
    line([(0.24, 0.14), (0.24, 0.86)])
    # two ascending arms as rising line-chart segments
    line([(0.24, 0.50), (0.45, 0.40), (0.63, 0.29), (0.84, 0.13)])
    line([(0.24, 0.50), (0.50, 0.65), (0.84, 0.87)])
    # data-point nodes on the ascending arms (accent)
    nr = int(0.052 * W)
    for (x, y) in _pts(W, [(0.45, 0.40), (0.63, 0.29), (0.84, 0.13), (0.50, 0.65), (0.84, 0.87)]):
        d.ellipse([x - nr, y - nr, x + nr, y + nr], fill=node + (255,))
        d.ellipse([x - nr * 0.42, y - nr * 0.42, x + nr * 0.42, y + nr * 0.42], fill=INDIGO0 + (255,))
    # junction node
    jx, jy = _pts(W, [(0.24, 0.50)])[0]
    d.ellipse([jx - nr, jy - nr, jx + nr, jy + nr], fill=silh + (255,))
    return img.resize((size, size), Image.LANCZOS)


# ---------------------------------------------------------------- K3 Facet-K
def k_facet(size, mono=False, accent=CYAN, silh=SILVER):
    img, d, W = _tile(size)
    dim = silh if mono else SILVER_DIM
    edge = silh if mono else accent
    # stem plane (slightly tapered — the "neck")
    d.polygon(_pts(W, [(0.18, 0.15), (0.31, 0.13), (0.33, 0.86), (0.20, 0.88)]), fill=silh + (255,))
    # upper plane A (the "head/ear" rising) — dim facet
    d.polygon(_pts(W, [(0.31, 0.46), (0.84, 0.10), (0.68, 0.11), (0.37, 0.40)]), fill=dim + (255,))
    # upper plane B (under-facet, brighter) — gives the fold
    d.polygon(_pts(W, [(0.31, 0.52), (0.68, 0.11), (0.56, 0.27), (0.40, 0.49)]), fill=silh + (255,))
    # leg plane (the "muzzle/jaw")
    d.polygon(_pts(W, [(0.33, 0.54), (0.83, 0.88), (0.70, 0.90), (0.39, 0.56)]), fill=dim + (255,))
    # accent fold edge along the ramp
    if not mono:
        d.line(_pts(W, [(0.40, 0.49), (0.84, 0.10)]), fill=edge + (255,), width=int(0.028 * W))
    return img.resize((size, size), Image.LANCZOS)


# ---------------------------------------------------------------- K4 Nightfall-K
def _vgrad(W, top, bot):
    g = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    px = g.load()
    for y in range(W):
        t = y / (W - 1)
        r = int(top[0] + (bot[0] - top[0]) * t)
        gg = int(top[1] + (bot[1] - top[1]) * t)
        b = int(top[2] + (bot[2] - top[2]) * t)
        for x in range(W):
            px[x, y] = (r, gg, b, 255)
    return g

def k_nightfall(size, mono=False, accent=CYAN, silh=SILVER):
    img, d, W = _tile(size)
    # K shape mask (solid geometric K: stem + straight upper arm + straight leg)
    mask = Image.new("L", (W, W), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle(_pts(W, [(0.17, 0.13), (0.30, 0.87)])[0] + _pts(W, [(0.17, 0.13), (0.30, 0.87)])[1],
                         radius=0.03 * W, fill=255)
    md.polygon(_pts(W, [(0.30, 0.50), (0.74, 0.13), (0.86, 0.13), (0.42, 0.50)]), fill=255)   # upper arm
    md.polygon(_pts(W, [(0.30, 0.50), (0.74, 0.87), (0.86, 0.87), (0.42, 0.50)]), fill=255)   # leg
    if mono:
        fill = Image.new("RGBA", (W, W), silh + (255,))
    else:
        fill = _vgrad(W, INDIGO1, NIGHT)
    img = Image.composite(fill, img, mask)
    d = ImageDraw.Draw(img)
    # silver keyline so the night K reads on dark, + accent stroke on the ramp edge
    if not mono:
        # accent stroke on the ramp edge + a faint silver keyline so the night K reads on dark
        d.line(_pts(W, [(0.30, 0.50), (0.80, 0.13)]), fill=accent + (255,), width=int(0.045 * W))
        d.line(_pts(W, [(0.235, 0.13), (0.235, 0.87)]), fill=SILVER_DIM + (255,), width=int(0.012 * W))
    return img.resize((size, size), Image.LANCZOS)


K_DIRS = [
    ("K1", "Ramp-K", "Upper diagonal thickens into an ascending throughput ramp.", k_ramp),
    ("K2", "Signal-K", "K drawn as line-chart strokes with data-point nodes.", k_signal),
    ("K3", "Facet-K", "K folded from angular planes; faint strategy subtext, pure geometry.", k_facet),
    ("K4", "Nightfall-K", "Solid K, deep-night gradient, one accent stroke on the ramp.", k_nightfall),
]
