#!/usr/bin/env python3
"""
kl_brand.py — Knightload brand toolkit (ISI-5779).

Backend note (same constraint as the Matrix deck, ISI-5724): this host has no
libcairo / resvg / inkscape / imagemagick, so PNGs are rasterized directly with
Pillow + the DejaVu TTFs that ship inside matplotlib's mpl-data. The production
wordmark font is Space Grotesk / Sora (geometric modern sans) — not installed
here — so every rasterized wordmark uses DejaVu Sans Bold as a FAITHFUL STAND-IN
and the spec flags the swap. The icon marks are pure vector geometry (no font),
so they are production-true; hand-authored SVG twins live in ../svg/.

Brand essence: Knight (guardian of performance / chess-knight strategy)
             + Night (load tests run through the night — the origin story)
             + Load (throughput/ramp grounded in observed reality — "Stop guessing").

Everything renders at 4x supersample -> LANCZOS downscale for crisp edges, on a
transparent RGBA canvas so marks drop onto any surface.
"""
import os, math
from PIL import Image, ImageDraw, ImageFont

SS = 4  # supersample factor

# ---------------------------------------------------------------- palette
INDIGO0 = (26, 26, 46)     # #1A1A2E  deepest midnight
INDIGO1 = (22, 33, 62)     # #16213E  midnight indigo (primary bg)
INDIGO2 = (33, 46, 80)     # raised panel
SILVER  = (199, 205, 214)  # #C7CDD6  brushed silver (primary mark on dark)
SILVER_HI = (231, 235, 240)
SILVER_DIM = (120, 128, 145)
CYAN    = (46, 230, 214)   # #2EE6D6  electric cyan (primary accent)
CYAN_DIM = (26, 140, 132)
AMBER   = (255, 178, 62)   # #FFB23E  amber (alternate accent)
AMBER_DIM = (150, 104, 36)
INK     = (245, 248, 252)
MUTE    = (150, 160, 178)

# ---------------------------------------------------------------- fonts
_FDIR = None
for cand in [
    "/home/hrexed/.local/lib/python3.12/site-packages/matplotlib/mpl-data/fonts/ttf",
    "/usr/share/fonts/truetype/dejavu",
]:
    if os.path.isdir(cand):
        _FDIR = cand
        break
if _FDIR is None:
    raise SystemExit("no DejaVu font dir found")

# Production display face: Space Grotesk (vendored variable TTF, OFL). When present
# the raster wordmark renders in the real brand font — this IS publish-time item #1
# (install Space Grotesk/Sora + re-run). Falls back to DejaVu Bold stand-in otherwise.
_BRANDDIR = os.path.join(os.path.dirname(__file__), "fonts")
_SG = os.path.join(_BRANDDIR, "SpaceGrotesk-VF.ttf")
_SORA = os.path.join(_BRANDDIR, "Sora-VF.ttf")
_HAS_SG = os.path.isfile(_SG)

_CACHE = {}
def font(size, bold=True, mono=False):
    key = (size, bold, mono)
    if key in _CACHE:
        return _CACHE[key]
    if mono:
        fn = "DejaVuSansMono-Bold.ttf" if bold else "DejaVuSansMono.ttf"
        f = ImageFont.truetype(os.path.join(_FDIR, fn), size)
    elif _HAS_SG:
        # Space Grotesk variable font: default axis weight is Light (300) — set the
        # named instance explicitly so bold reads as Bold, regular as Regular.
        f = ImageFont.truetype(_SG, size)
        try:
            f.set_variation_by_name("Bold" if bold else "Regular")
        except Exception:
            pass
    else:
        fn = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
        f = ImageFont.truetype(os.path.join(_FDIR, fn), size)
    _CACHE[key] = f
    return f

# ---------------------------------------------------------------- helpers
def tile(size):
    """Return (Image, Draw) RGBA transparent at supersampled resolution."""
    W = size * SS
    img = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)

def finish(img, size):
    return img.resize((size, size), Image.LANCZOS)

def _arc_pts(cx, cy, rx, ry, a0, a1, n=48):
    pts = []
    for i in range(n + 1):
        a = math.radians(a0 + (a1 - a0) * i / n)
        pts.append((cx + rx * math.cos(a), cy + ry * math.sin(a)))
    return pts

def tracked_text(d, xy, text, fnt, fill, tracking=0, anchor_mid=False):
    """Draw text with manual letter-spacing (tracking px at the given scale)."""
    x, y = xy
    widths = []
    for ch in text:
        bb = d.textbbox((0, 0), ch, font=fnt)
        widths.append(bb[2] - bb[0])
    adv = [d.textlength(ch, font=fnt) for ch in text]
    total = sum(adv) + tracking * (len(text) - 1)
    if anchor_mid:
        x = x - total / 2
    for ch, a in zip(text, adv):
        d.text((x, y), ch, font=fnt, fill=fill)
        x += a + tracking
    return total

# ================================================================ MARKS
# Each mark fills a `size`x`size` tile. `silh` = silhouette colour,
# `accent` = accent colour. Returns a down-sampled RGBA image.

def mark_helm(size, silh=SILVER, accent=CYAN, moon=True):
    """Concept A — 'Visor Gauge': knight great-helm, visor slits = ascending
    load bars, crescent moon carved from the dome in negative space."""
    img, d = tile(size)
    W = size * SS
    def P(nx, ny): return (nx * W, ny * W)

    # ---- helm body as a closed path (frontal great-helm) ----
    body = []
    # dome: left-top arc over to right-top
    body += _arc_pts(*P(0.50, 0.335), 0.265 * W, 0.235 * W, 180, 360, 40)
    # right side down with slight inward taper
    body += [P(0.765, 0.34), P(0.74, 0.62), P(0.715, 0.86)]
    # bottom rounded corners -> flat base
    body += _arc_pts(*P(0.655, 0.86), 0.06 * W, 0.06 * W, 0, 90, 10)
    body += [P(0.345, 0.92)]
    body += _arc_pts(*P(0.345, 0.86), 0.06 * W, 0.06 * W, 90, 180, 10)
    # left side up
    body += [P(0.285, 0.86), P(0.26, 0.62), P(0.235, 0.34)]

    layer = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    ld.polygon(body, fill=silh + (255,))

    # ---- crescent moon carved from upper-left dome (negative space) ----
    # A thin waxing crescent: base disc minus a near-equal disc nudged right,
    # so only a clean vertical sliver remains (reads unmistakably as a moon).
    if moon:
        hole = Image.new("L", (W, W), 0)
        hd = ImageDraw.Draw(hole)
        mcx, mcy, mr = 0.385, 0.255, 0.093
        hd.ellipse([P(mcx - mr, mcy - mr)[0], P(mcx - mr, mcy - mr)[1],
                    P(mcx + mr, mcy + mr)[0], P(mcx + mr, mcy + mr)[1]], fill=255)
        # subtract a near-equal disc offset mostly in +x -> thin crescent, cusps up/down
        ox, oy, orr = mcx + 0.058, mcy - 0.006, 0.090
        hd.ellipse([P(ox - orr, oy - orr)[0], P(ox - orr, oy - orr)[1],
                    P(ox + orr, oy + orr)[0], P(ox + orr, oy + orr)[1]], fill=0)
        # punch the crescent out of the helm: wherever hole==255, alpha -> 0
        empty = Image.new("RGBA", (W, W), (0, 0, 0, 0))
        layer = Image.composite(empty, layer, hole)

    img.alpha_composite(layer)

    # ---- central ridge ----
    d.line([P(0.50, 0.11), P(0.50, 0.30)], fill=silh + (255,), width=int(0.012 * W))

    # ---- visor slot (dark negative band) with ascending load bars ----
    vx0, vx1, vy0, vy1 = 0.285, 0.715, 0.40, 0.50
    # cut the slot by punching a rounded-rect hole, then fill with bars
    slot = Image.new("L", (W, W), 0)
    sd = ImageDraw.Draw(slot)
    sd.rounded_rectangle([P(vx0, vy0)[0], P(vx0, vy0)[1], P(vx1, vy1)[0], P(vx1, vy1)[1]],
                         radius=0.02 * W, fill=255)
    empty = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    img2 = Image.composite(empty, img, slot)
    img = img2
    d = ImageDraw.Draw(img)
    # ascending load bars inside the slot (throughput waveform)
    n = 7
    pad = 0.012
    bw = (vx1 - vx0 - pad * 2) / (n * 1.6)
    gap = bw * 0.6
    heights = [0.22, 0.35, 0.5, 0.68, 0.55, 0.82, 1.0]
    bx = vx0 + pad
    for i in range(n):
        h = heights[i] * (vy1 - vy0 - 0.012)
        y1 = vy1 - 0.006
        y0 = y1 - h
        d.rounded_rectangle([P(bx, y0)[0], P(bx, y0)[1], P(bx + bw, y1)[0], P(bx + bw, y1)[1]],
                            radius=0.004 * W, fill=accent + (255,))
        bx += bw + gap

    # ---- breathing holes: ascending dot chevron below visor ----
    dots = [(0.40, 0.66), (0.455, 0.69), (0.50, 0.705), (0.545, 0.69), (0.60, 0.66)]
    for (nx, ny) in dots:
        r = 0.013
        d.ellipse([P(nx - r, ny - r)[0], P(nx - r, ny - r)[1],
                   P(nx + r, ny + r)[0], P(nx + r, ny + r)[1]], fill=accent + (255,))
    return finish(img, size)


def mark_knight(size, silh=SILVER, accent=CYAN):
    """Concept B — 'Chess Knight Sparkline': chess-knight head facing left; the
    mane along the back of the neck is a row of ascending bars (a sparkline)."""
    img, d = tile(size)
    W = size * SS
    def P(nx, ny): return (nx * W, ny * W)

    # chess-knight head + neck silhouette, facing LEFT (face = left edge)
    knight = [
        P(0.545, 0.115),  # poll / top of head
        P(0.455, 0.175),  # forehead
        P(0.375, 0.255),  # brow ridge
        P(0.305, 0.315),  # bridge
        P(0.235, 0.360),  # forelock dip
        P(0.195, 0.420),  # nose / muzzle tip (left-most)
        P(0.225, 0.470),  # nostril
        P(0.300, 0.495),  # mouth / lip
        P(0.355, 0.520),  # jaw
        P(0.395, 0.600),  # throat
        P(0.420, 0.700),  # front of neck
        P(0.415, 0.800),  # neck base front
        P(0.360, 0.800),  # base shoulder L
        P(0.330, 0.885),  # base foot L
        P(0.690, 0.885),  # base foot R
        P(0.660, 0.800),  # base shoulder R
        P(0.585, 0.800),  # neck base back
        P(0.600, 0.560),  # back of neck (mane edge, kept smooth)
        P(0.590, 0.300),  # crest behind head
        P(0.600, 0.175),  # ear base back
        P(0.560, 0.095),  # ear tip
    ]
    d.polygon(knight, fill=silh + (255,))

    # ---- mane = ascending bars running up the back of the neck ----
    # anchored along the line from (0.585,0.80) up to (0.575,0.21), bars grow outward (+x)
    n = 6
    t0, t1 = 0.80, 0.235
    base_x = 0.585
    heights = [0.045, 0.065, 0.085, 0.105, 0.085, 0.060]
    bar_h = (t0 - t1) / n
    for i in range(n):
        ny0 = t0 - (i + 1) * bar_h + bar_h * 0.12
        ny1 = t0 - i * bar_h - bar_h * 0.12
        hx = heights[i]
        d.rounded_rectangle([P(base_x, ny0)[0], P(base_x, ny0)[1],
                             P(base_x + hx, ny1)[0], P(base_x + hx, ny1)[1]],
                            radius=0.006 * W, fill=accent + (255,))

    # eye (negative dot)
    ex, ey, er = 0.360, 0.330, 0.020
    d.ellipse([P(ex - er, ey - er)[0], P(ex - er, ey - er)[1],
               P(ex + er, ey + er)[0], P(ex + er, ey + er)[1]], fill=INDIGO0 + (255,))
    return finish(img, size)


def mark_shield(size, silh=SILVER, accent=CYAN, moon=True):
    """Concept C — 'Shield Load-Bar': heater shield with a filling load bar and
    a crescent-moon plume at the crest."""
    img, d = tile(size)
    W = size * SS
    def P(nx, ny): return (nx * W, ny * W)

    # heater shield outline
    shield = [P(0.26, 0.195), P(0.74, 0.195)]
    # right side: straight-ish down then curve to the point
    shield += [P(0.745, 0.42)]
    shield += _arc_pts(*P(0.50, 0.42), 0.245 * W, 0.47 * W, 0, 90, 28)  # right lobe to point
    # left lobe to point (mirror)
    shield += _arc_pts(*P(0.50, 0.42), 0.245 * W, 0.47 * W, 90, 180, 28)
    shield += [P(0.255, 0.42)]
    d.polygon(shield, fill=silh + (255,))

    # inner bevel (darker inset) for depth
    d.line(shield + [shield[0]], fill=INDIGO1 + (0,), width=1)

    # ---- load bar track + fill ----
    tx0, tx1, ty0, ty1 = 0.335, 0.665, 0.455, 0.525
    d.rounded_rectangle([P(tx0, ty0)[0], P(tx0, ty0)[1], P(tx1, ty1)[0], P(tx1, ty1)[1]],
                        radius=0.03 * W, fill=INDIGO0 + (255,))
    fillfrac = 0.64
    fx1 = tx0 + (tx1 - tx0) * fillfrac
    d.rounded_rectangle([P(tx0 + 0.006, ty0 + 0.006)[0], P(tx0 + 0.006, ty0 + 0.006)[1],
                         P(fx1, ty1 - 0.006)[0], P(fx1, ty1 - 0.006)[1]],
                        radius=0.025 * W, fill=accent + (255,))
    # ascending ramp staircase above the bar (monotonic rise, all accent) ----
    # sits on a shared baseline just above the load-bar track so it reads as a
    # throughput ramp, not a pair of eyes.
    ramp_base = 0.415
    bars_x = [0.345, 0.418, 0.491, 0.564, 0.637]
    bw2 = 0.052
    for i, nx in enumerate(bars_x):
        h = 0.045 + i * 0.038
        d.rounded_rectangle([P(nx, ramp_base - h)[0], P(nx, ramp_base - h)[1],
                             P(nx + bw2, ramp_base)[0], P(nx + bw2, ramp_base)[1]],
                            radius=0.006 * W, fill=accent + (255,))

    # ---- crescent-moon plume at the crest ----
    if moon:
        layer = Image.new("RGBA", (W, W), (0, 0, 0, 0))
        ld = ImageDraw.Draw(layer)
        mcx, mcy, mr = 0.50, 0.135, 0.058
        ld.ellipse([P(mcx - mr, mcy - mr)[0], P(mcx - mr, mcy - mr)[1],
                    P(mcx + mr, mcy + mr)[0], P(mcx + mr, mcy + mr)[1]], fill=accent + (255,))
        hole = Image.new("L", (W, W), 0)
        hd = ImageDraw.Draw(hole)
        ox, oy, orr = mcx + 0.028, mcy - 0.018, 0.052
        hd.ellipse([P(ox - orr, oy - orr)[0], P(ox - orr, oy - orr)[1],
                    P(ox + orr, oy + orr)[0], P(ox + orr, oy + orr)[1]], fill=255)
        empty = Image.new("RGBA", (W, W), (0, 0, 0, 0))
        layer = Image.composite(empty, layer, hole)
        img.alpha_composite(layer)
    return finish(img, size)


def mark_monogram(size, silh=SILVER, accent=CYAN, tile_bg=None):
    """App-icon monogram: a 'K' whose arms are ascending bars; crescent-moon
    counter in the negative space of the K's junction."""
    img, d = tile(size)
    W = size * SS
    def P(nx, ny): return (nx * W, ny * W)

    if tile_bg is not None:
        # rounded-square app tile
        d.rounded_rectangle([P(0.04, 0.04)[0], P(0.04, 0.04)[1], P(0.96, 0.96)[0], P(0.96, 0.96)[1]],
                            radius=0.20 * W, fill=tile_bg + (255,))

    # vertical stem of the K
    sx0, sx1, sy0, sy1 = 0.255, 0.355, 0.20, 0.80
    d.rounded_rectangle([P(sx0, sy0)[0], P(sx0, sy0)[1], P(sx1, sy1)[0], P(sx1, sy1)[1]],
                        radius=0.02 * W, fill=silh + (255,))

    # upper arm = ascending bars going up-right (short->tall)
    junction = (0.37, 0.50)
    # three ascending bars for the top arm
    topbars = [(0.44, 0.40, 0.085), (0.545, 0.30, 0.115), (0.655, 0.185, 0.145)]
    for (bx, by, bh) in topbars:
        d.rounded_rectangle([P(bx, by)[0], P(bx, by)[1], P(bx + 0.085, by + bh + 0.14)[0], P(bx + 0.085, by + bh + 0.14)[1]],
                            radius=0.014 * W, fill=accent + (255,))
    # lower arm = solid descending leg (silver) rooted on the stem, balances the K
    lower = [P(0.355, 0.47), P(0.455, 0.49), P(0.725, 0.80),
             P(0.585, 0.80), P(0.355, 0.565)]
    d.polygon(lower, fill=silh + (255,))

    # crescent-moon counter in the junction negative space
    layer = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    mcx, mcy, mr = 0.475, 0.49, 0.055
    ld.ellipse([P(mcx - mr, mcy - mr)[0], P(mcx - mr, mcy - mr)[1],
                P(mcx + mr, mcy + mr)[0], P(mcx + mr, mcy + mr)[1]], fill=accent + (255,))
    hole = Image.new("L", (W, W), 0)
    hd = ImageDraw.Draw(hole)
    ox, oy, orr = mcx + 0.030, mcy - 0.014, 0.050
    hd.ellipse([P(ox - orr, oy - orr)[0], P(ox - orr, oy - orr)[1],
                P(ox + orr, oy + orr)[0], P(ox + orr, oy + orr)[1]], fill=255)
    empty = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    layer = Image.composite(empty, layer, hole)
    img.alpha_composite(layer)
    return finish(img, size)


MARKS = {
    "A": ("Visor Gauge", mark_helm),
    "B": ("Chess Knight Sparkline", mark_knight),
    "C": ("Shield Load-Bar", mark_shield),
}
