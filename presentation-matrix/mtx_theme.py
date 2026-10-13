#!/usr/bin/env python3
"""
mtx_theme.py — Matrix-themed visual toolkit for the PAC deck (ISI-5724, workstream B).

Backend note: this host has no libcairo / resvg / rsvg / inkscape / imagemagick, so we
rasterize directly with Pillow + the DejaVu TTFs that ship inside matplotlib's mpl-data.
DejaVuSansMono is the signature face (terminal / "code" feel); DejaVuSans(-Bold) for titles.

Everything is drawn on an RGBA canvas at 2x so it stays crisp when dropped into Keynote/
Google Slides/PowerPoint at 1920x1080. Diagrams are exported with a transparent background
so they can sit on any slide master; slide masters bake the dark base in.

Palette rationale (taste-skill compliant):
  - ONE ambient/structural accent = Matrix GREEN (telemetry / the real world / the signal).
  - The red/blue pill pair is a *semantic* duality used only where guess-vs-truth is the point
    (RED = observed truth / the human gate ; BLUE = guessing / synthetic / folklore).
  - AMBER is reserved for honesty beats: the dashed "unavailable" edge (the empty logs leg
    on this tenant) & caveats. (Note: user.events is NOT amber — the scope was granted, so it
    renders as a solid live feed; see ISI-5719/ISI-5726.)
  - Neutral near-black base (faint green cast), single corner-radius scale, hairline borders.
"""
import os, math, random
from PIL import Image, ImageDraw, ImageFont, ImageFilter

random.seed(42)  # deterministic rain / glitch

# ---------------------------------------------------------------- palette
BG0   = (7, 10, 8)        # deepest base (near-black, faint green)
BG1   = (12, 18, 14)      # panel base
BG2   = (18, 26, 21)      # raised panel
BG3   = (24, 34, 28)      # chip fill
LINE  = (32, 46, 38)      # hairline border
LINE2 = (46, 64, 53)      # stronger border

GREEN   = (57, 217, 138)  # primary accent: telemetry / truth-signal / the Matrix
GREEN_HI= (120, 245, 180) # bright green (rain heads, glow)
GREEN_DIM=(28, 122, 78)   # dim green
RAIN    = (18, 64, 42)    # faint rain glyphs

RED   = (255, 77, 94)     # red pill = observed truth / the human gate
RED_DIM=(120, 40, 50)
BLUE  = (92, 141, 239)    # blue pill = guessing / synthetic / folklore
BLUE_DIM=(48, 70, 120)
AMBER = (246, 178, 60)    # caution / dashed-unavailable edge (empty logs leg)
AMBER_DIM=(120, 88, 32)

INK   = (234, 243, 236)   # primary text
MUTE  = (141, 162, 150)   # secondary text
FAINT = (92, 110, 100)    # tertiary text
WHITE = (245, 250, 246)

RADIUS = 18               # single corner-radius scale (x2 canvas -> ~9px at 1x)

# ---------------------------------------------------------------- fonts
_FDIR = None
for cand in [
    "/home/hrexed/.local/lib/python3.12/site-packages/matplotlib/mpl-data/fonts/ttf",
    os.path.join(os.path.dirname(__file__), "fonts"),
]:
    if os.path.isdir(cand):
        _FDIR = cand
        break
if _FDIR is None:
    raise SystemExit("no DejaVu font dir found")

def _f(name):
    return os.path.join(_FDIR, name)

_CACHE = {}
def font(kind="sans", size=32, bold=False, italic=False):
    key = (kind, size, bold, italic)
    if key in _CACHE:
        return _CACHE[key]
    if kind == "mono":
        fn = "DejaVuSansMono.ttf"
        if bold:   fn = "DejaVuSansMono-Bold.ttf"
    else:
        fn = "DejaVuSans.ttf"
        if bold:   fn = "DejaVuSans-Bold.ttf"
    f = ImageFont.truetype(_f(fn), size)
    _CACHE[key] = f
    return f

# ---------------------------------------------------------------- canvas
def canvas(w, h, bg=None):
    img = Image.new("RGBA", (w, h), (bg if bg else (0, 0, 0, 0)))
    return img, ImageDraw.Draw(img)

def save(img, path):
    img.save(path, "PNG")
    return path

# ---------------------------------------------------------------- text
def measure(draw, text, fnt):
    b = draw.textbbox((0, 0), text, font=fnt)
    return b[2] - b[0], b[3] - b[1]

def text_l(draw, xy, s, fnt, fill=INK, anchor="la"):
    draw.text(xy, s, font=fnt, fill=fill, anchor=anchor)

def text_c(draw, cx, cy, s, fnt, fill=INK):
    draw.text((cx, cy), s, font=fnt, fill=fill, anchor="mm")

def text_r(draw, x, y, s, fnt, fill=INK):
    draw.text((x, y), s, font=fnt, fill=fill, anchor="ra")

def wrap(draw, s, fnt, max_w):
    words, lines, cur = s.split(), [], ""
    for w in words:
        t = (cur + " " + w).strip()
        if measure(draw, t, fnt)[0] <= max_w:
            cur = t
        else:
            if cur: lines.append(cur)
            cur = w
    if cur: lines.append(cur)
    return lines

def para(draw, xy, s, fnt, fill=INK, max_w=600, leading=1.4):
    x, y = xy
    lh = int(fnt.size * leading)
    for ln in wrap(draw, s, fnt, max_w):
        draw.text((x, y), ln, font=fnt, fill=fill, anchor="la")
        y += lh
    return y

# ---------------------------------------------------------------- shapes
def rrect(draw, box, radius=RADIUS, fill=None, outline=None, width=2):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)

def panel(draw, box, fill=BG1, outline=LINE, width=2, radius=RADIUS):
    rrect(draw, box, radius=radius, fill=fill, outline=outline, width=width)

def chip(draw, box, fill=BG3, outline=LINE2, width=2, radius=10):
    rrect(draw, box, radius=radius, fill=fill, outline=outline, width=width)

def glow_rect(img, box, color, radius=RADIUS, blur=14, alpha=90):
    """soft outer glow behind a node — paste a blurred colored rrect."""
    g = Image.new("RGBA", img.size, (0, 0, 0, 0))
    gd = ImageDraw.Draw(g)
    gd.rounded_rectangle(box, radius=radius, fill=color + (alpha,))
    g = g.filter(ImageFilter.GaussianBlur(blur))
    img.alpha_composite(g)

def dashed_line(draw, p0, p1, fill=AMBER, width=3, dash=16, gap=12):
    x0, y0 = p0; x1, y1 = p1
    dist = math.hypot(x1 - x0, y1 - y0)
    if dist == 0: return
    dx, dy = (x1 - x0) / dist, (y1 - y0) / dist
    n = int(dist // (dash + gap)) + 1
    for i in range(n):
        s = i * (dash + gap)
        e = min(s + dash, dist)
        draw.line([(x0 + dx * s, y0 + dy * s), (x0 + dx * e, y0 + dy * e)], fill=fill, width=width)

def _arrowhead(draw, tip, ang, color, size=16):
    a1 = ang + math.radians(150)
    a2 = ang - math.radians(150)
    p1 = (tip[0] + size * math.cos(a1), tip[1] + size * math.sin(a1))
    p2 = (tip[0] + size * math.cos(a2), tip[1] + size * math.sin(a2))
    draw.polygon([tip, p1, p2], fill=color)

def arrow(draw, p0, p1, color=GREEN, width=4, head=17, dashed=False, dash=16, gap=12):
    if dashed:
        dashed_line(draw, p0, p1, fill=color, width=width, dash=dash, gap=gap)
    else:
        draw.line([p0, p1], fill=color, width=width)
    ang = math.atan2(p1[1] - p0[1], p1[0] - p0[0])
    # pull tip back slightly so head sits cleanly
    _arrowhead(draw, p1, ang, color, size=head)

def elbow(draw, p0, p1, color=GREEN, width=4, head=17, via="h", dashed=False):
    """right-angle connector. via='h' -> horizontal then vertical."""
    if via == "h":
        mid = (p1[0], p0[1])
    else:
        mid = (p0[0], p1[1])
    if dashed:
        dashed_line(draw, p0, mid, fill=color, width=width)
        dashed_line(draw, mid, p1, fill=color, width=width)
    else:
        draw.line([p0, mid], fill=color, width=width)
        draw.line([mid, p1], fill=color, width=width)
    ang = math.atan2(p1[1] - mid[1], p1[0] - mid[0])
    _arrowhead(draw, p1, ang, color, size=head)

# ---------------------------------------------------------------- motifs
def code_rain(img, region, density=0.55, color=RAIN, head=GREEN_HI, size=26, seed=7):
    """Faint vertical columns of hex/binary glyphs — the digital-rain backdrop.
    Used sparingly (low alpha) so it never competes with content."""
    rnd = random.Random(seed)
    x0, y0, x1, y1 = region
    d = ImageDraw.Draw(img)
    fnt = font("mono", size, bold=False)
    glyphs = "0123456789ABCDEF░▒│10"
    col_w = int(size * 0.95)
    for cx in range(x0, x1, col_w):
        if rnd.random() > density:
            continue
        n = int((y1 - y0) / (size * 1.25))
        start = rnd.randint(0, max(1, n // 2))
        length = rnd.randint(3, n)
        for i in range(length):
            yy = y0 + (start + i) * int(size * 1.25)
            if yy > y1: break
            g = rnd.choice(glyphs)
            # fade down the trail; brightest at the head
            if i == length - 1:
                a = 150; col = head
            else:
                a = max(14, int(70 * (i + 1) / length))
                col = color
            d.text((cx, yy), g, font=fnt, fill=col + (a,), anchor="la")

def rain_backdrop(w, h, density=0.5, seed=7):
    img, _ = canvas(w, h, bg=None)
    code_rain(img, (0, 0, w, h), density=density, seed=seed)
    return img

def pill(draw, center, w, h, color, label=None, filled=True, fnt=None):
    """a red/blue 'pill' capsule."""
    cx, cy = center
    box = [cx - w // 2, cy - h // 2, cx + w // 2, cy + h // 2]
    r = h // 2
    if filled:
        draw.rounded_rectangle(box, radius=r, fill=color)
        draw.rounded_rectangle(box, radius=r, outline=WHITE + (60,), width=2)
        # specular highlight
        draw.rounded_rectangle([box[0]+8, box[1]+6, box[0]+w//2, box[1]+h//3],
                               radius=r//2, fill=WHITE + (40,))
    else:
        draw.rounded_rectangle(box, radius=r, outline=color, width=3)
    if label and fnt:
        text_c(draw, cx, cy, label, fnt, fill=(WHITE if filled else color))

def lock(draw, center, size=34, color=RED, locked=True):
    """small lock glyph for the V1 gate."""
    cx, cy = center
    body = [cx - size//2, cy - size//6, cx + size//2, cy + size//2]
    draw.rounded_rectangle(body, radius=6, fill=color)
    # shackle
    r = size // 3
    draw.arc([cx - r, cy - size//2, cx + r, cy - size//6 + r//2], start=180, end=360,
             fill=color, width=max(3, size//8))
    # keyhole
    draw.ellipse([cx - 4, cy + 2, cx + 4, cy + 10], fill=BG0)

def badge(draw, xy, label, fnt, fg=AMBER, bg=None, pad=(14, 7)):
    """small status pill badge e.g. 'LIVE · 16 journeys' (green) or 'logs · unavailable' (amber)."""
    w, h = measure(draw, label, fnt)
    x, y = xy
    box = [x, y, x + w + pad[0]*2, y + h + pad[1]*2]
    rrect(draw, box, radius=(h + pad[1]*2)//2,
          fill=(bg if bg else (fg[0]//5, fg[1]//5, fg[2]//5)), outline=fg, width=2)
    draw.text((x + pad[0], y + pad[1]), label, font=fnt, fill=fg, anchor="la")
    return box[2] - box[0]

# ---------------------------------------------------------------- composite helpers
def place(base, overlay, xy):
    base.alpha_composite(overlay, xy)

if __name__ == "__main__":
    print("mtx_theme OK · fonts from", _FDIR)
