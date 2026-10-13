#!/usr/bin/env python3
"""
kl_render.py — render the Knightload brand deliverables (ISI-5779).

Stage 1 (this run) = CONCEPT PRESENTATION for the board pick:
  * one concept-board sheet (A/B/C side by side, on-dark, with wordmark + descriptor)
  * per-concept icon marks: on-dark panel, transparent, monochrome, reversed
  * per-concept horizontal wordmark lockup
  * shared app-icon monogram tiles + palette swatches

Font note: production wordmark is Space Grotesk / Sora. Not installed on this
host (no cairo/resvg either — same constraint as ISI-5724). DejaVu Sans Bold is
used as a faithful stand-in and every wordmark render is flagged in the spec.
Icon marks are pure geometry -> production-true; SVG twins live in ../svg/.
"""
import os
from PIL import Image, ImageDraw
import kl_brand as k

OUT = os.path.join(os.path.dirname(__file__), "png")
os.makedirs(OUT, exist_ok=True)

SILVER, CYAN, AMBER = k.SILVER, k.CYAN, k.AMBER
INDIGO0, INDIGO1, INDIGO2 = k.INDIGO0, k.INDIGO1, k.INDIGO2
WHITE = (255, 255, 255)

CONCEPTS = [
    ("A", "Visor Gauge",            k.mark_helm,
     "Great-helm in profile · visor slits = ascending load bars · crescent moon in the dome"),
    ("B", "Chess Knight Sparkline", k.mark_knight,
     "Chess-knight head · mane doubles as a throughput sparkline · the L-move nods to Load"),
    ("C", "Shield Load-Bar",        k.mark_shield,
     "Heater shield · filling load bar + ascending ramp · crescent-moon plume at the crest"),
]


# ------------------------------------------------------------------ wordmark
def wordmark(d, xy, px, color, tracking_frac=0.06, text="Knightload"):
    """Draw the Knightload wordmark. Returns total advance width (px)."""
    fnt = k.font(px, bold=True)
    # 'Knight' full weight, 'load' same weight but accent-tinted handled by caller
    return k.tracked_text(d, xy, text, fnt, color + (255,),
                          tracking=px * tracking_frac)


def lockup_horizontal(concept_key, fn, size=(1200, 400), bg=INDIGO1,
                      silh=SILVER, accent=CYAN, two_tone=True):
    """Icon on the left, 'Knightload' wordmark on the right, baseline-aligned."""
    W, H = size
    img = Image.new("RGBA", (W, H), bg + (255,) if bg else (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # icon
    ic = 236
    mark = fn(ic, silh=silh, accent=accent) if fn is not k.mark_knight \
        else fn(ic, silh=silh, accent=accent)
    iy = (H - ic) // 2
    ix = 70
    img.alpha_composite(mark, (ix, iy))
    # wordmark — draw 'Knight' in silver and 'load' in accent (two-tone)
    px = 150
    fnt = k.font(px, bold=True)
    tx = ix + ic + 60
    ty = H // 2 - px * 0.62
    if two_tone:
        w1 = k.tracked_text(d, (tx, ty), "Knight", fnt, silh + (255,), tracking=px * 0.03)
        k.tracked_text(d, (tx + w1 + px * 0.03, ty), "load", fnt, accent + (255,), tracking=px * 0.03)
    else:
        k.tracked_text(d, (tx, ty), "Knightload", fnt, silh + (255,), tracking=px * 0.03)
    # tagline
    tfnt = k.font(34, bold=False)
    d.text((tx + 4, ty + px + 18), "Stop guessing. Load with proof.",
           font=tfnt, fill=k.MUTE + (255,))
    return img


def lockup_stacked(fn, size=(640, 760), bg=None, silh=SILVER, accent=CYAN):
    W, H = size
    img = Image.new("RGBA", (W, H), bg + (255,) if bg else (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    ic = 380
    img.alpha_composite(fn(ic, silh=silh, accent=accent), ((W - ic) // 2, 40))
    px = 112
    fnt = k.font(px, bold=True)
    # centre the two-tone wordmark
    w_k = sum(d.textlength(c, font=fnt) for c in "Knight") + px * 0.03 * 5
    w_l = sum(d.textlength(c, font=fnt) for c in "load") + px * 0.03 * 3
    total = w_k + px * 0.03 + w_l
    sx = (W - total) / 2
    ty = 40 + ic + 30
    w1 = k.tracked_text(d, (sx, ty), "Knight", fnt, silh + (255,), tracking=px * 0.03)
    k.tracked_text(d, (sx + w1 + px * 0.03, ty), "load", fnt, accent + (255,), tracking=px * 0.03)
    tfnt = k.font(26, bold=False)
    k.tracked_text(d, (W / 2, ty + px + 20), "STOP  GUESSING", tfnt, k.MUTE + (255,),
                   tracking=8, anchor_mid=True)
    return img


# ------------------------------------------------------------------ app icon
def app_tile(fn, size=512, bg=INDIGO1, silh=SILVER, accent=CYAN, radius=0.22):
    W = size
    img = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, W - 1, W - 1], radius=int(radius * W), fill=bg + (255,))
    inner = int(W * 0.78)
    off = (W - inner) // 2
    img.alpha_composite(fn(inner, silh=silh, accent=accent), (off, off))
    return img


# ------------------------------------------------------------------ swatches
def palette_strip(size=(1200, 150)):
    W, H = size
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    chips = [("#1A1A2E", INDIGO0), ("#16213E", INDIGO1), ("#C7CDD6", SILVER),
             ("#2EE6D6", CYAN), ("#FFB23E", AMBER)]
    cw = W // len(chips)
    for i, (hx, rgb) in enumerate(chips):
        x = i * cw
        d.rectangle([x, 0, x + cw - 10, H - 40], fill=rgb + (255,))
        fnt = k.font(26, bold=True, mono=True)
        col = INDIGO0 if rgb in (SILVER, CYAN, AMBER) else SILVER
        d.text((x + 14, 24), hx, font=fnt, fill=col + (255,))
        lab = {"#1A1A2E": "midnight", "#16213E": "indigo", "#C7CDD6": "silver",
               "#2EE6D6": "cyan", "#FFB23E": "amber"}[hx]
        d.text((x + 14, H - 36), lab, font=k.font(24, bold=False), fill=k.MUTE + (255,))
    return img


# ------------------------------------------------------------------ board
def concept_board():
    W, H = 1600, 1200
    img = Image.new("RGBA", (W, H), INDIGO0 + (255,))
    d = ImageDraw.Draw(img)
    # header
    d.text((60, 46), "KNIGHTLOAD", font=k.font(60, bold=True), fill=SILVER + (255,))
    k.tracked_text(d, (62, 120), "LOGO  CONCEPT  DIRECTIONS  ·  ISI-5779  ·  pick one",
                   k.font(26, bold=True), CYAN + (255,), tracking=4)
    d.line([60, 170, W - 60, 170], fill=INDIGO2 + (255,), width=3)
    # three columns
    colw = (W - 120) // 3
    y0 = 210
    for i, (key, name, fn, desc) in enumerate(CONCEPTS):
        cx = 60 + i * colw
        panel = [cx + 10, y0, cx + colw - 10, y0 + 470]
        d.rounded_rectangle(panel, radius=22, fill=INDIGO1 + (255,))
        # label
        d.text((cx + 34, y0 + 26), f"Concept {key}", font=k.font(34, bold=True), fill=CYAN + (255,))
        d.text((cx + 34, y0 + 70), name, font=k.font(30, bold=True), fill=SILVER_hi() + (255,))
        # icon centred
        ic = 260
        img.alpha_composite(fn(ic, silh=SILVER, accent=CYAN),
                            (cx + (colw - ic) // 2, y0 + 120))
        # descriptor wrapped
        _wrap(d, desc, (cx + 34, y0 + 398), colw - 68, k.font(22, bold=False), k.MUTE)
    # lockup row (concept-neutral: show the chosen-style wordmark with each icon small)
    ly = y0 + 500
    d.text((60, ly), "HORIZONTAL  LOCKUP  (two-tone wordmark, Knight silver · load cyan)",
           font=k.font(24, bold=True), fill=SILVER + (255,))
    for i, (key, name, fn, desc) in enumerate(CONCEPTS):
        cx = 60 + i * colw
        lk = lockup_horizontal(key, fn, size=(colw - 20, 150), bg=INDIGO1)
        img.alpha_composite(lk, (cx + 10, ly + 40))
    # palette + app tiles
    py = ly + 210
    img.alpha_composite(palette_strip((760, 150)), (60, py + 36))
    d.text((60, py), "PALETTE", font=k.font(24, bold=True), fill=SILVER + (255,))
    d.text((900, py), "APP  ICON  (monogram K)", font=k.font(24, bold=True), fill=SILVER + (255,))
    tiles = [(app_tile(k.mark_monogram_wrap, 150, bg=INDIGO1), 900),
             (app_tile(k.mark_monogram_wrap, 150, bg=INDIGO0, accent=AMBER), 1070),
             (mono_tile(150), 1240)]
    for t, x in tiles:
        img.alpha_composite(t, (x, py + 36))
    # footer note
    d.text((60, H - 46), "Fonts shown = DejaVu stand-in for Space Grotesk/Sora · icons are production-true vector (SVG twins shipped)",
           font=k.font(20, bold=False), fill=k.SILVER_DIM + (255,))
    return img


def mono_tile(size):
    """Monochrome reversed monogram tile (silver on indigo, no accent)."""
    return app_tile(k.mark_monogram_wrap, size, bg=INDIGO2, silh=SILVER, accent=SILVER)


def SILVER_hi():
    return k.SILVER_HI


def _wrap(d, text, xy, maxw, fnt, color):
    x, y = xy
    words, line = text.split(), ""
    for w in words:
        test = (line + " " + w).strip()
        if d.textlength(test, font=fnt) > maxw and line:
            d.text((x, y), line, font=fnt, fill=color + (255,)); y += fnt.size + 8
            line = w
        else:
            line = test
    if line:
        d.text((x, y), line, font=fnt, fill=color + (255,))


# monogram wrapper so app_tile's (silh,accent) signature matches
def _mono_wrap(size, silh=SILVER, accent=CYAN):
    return k.mark_monogram(size, silh=silh, accent=accent, tile_bg=None)
k.mark_monogram_wrap = _mono_wrap


# ------------------------------------------------------------------ main
def save(img, name):
    p = os.path.join(OUT, name)
    img.convert("RGBA").save(p)
    print("  ", name, img.size)


def main():
    print("concept board...")
    save(concept_board(), "knightload-concept-board.png")

    print("per-concept marks + lockups...")
    for key, name, fn, desc in CONCEPTS:
        # icon on dark panel
        panel = Image.new("RGBA", (512, 512), INDIGO1 + (255,))
        panel.alpha_composite(fn(400, silh=SILVER, accent=CYAN), (56, 56))
        save(panel, f"mark-{key}-ondark.png")
        # transparent
        save(fn(512, silh=SILVER, accent=CYAN), f"mark-{key}-transparent.png")
        # monochrome (silver, no accent)
        save(fn(512, silh=SILVER, accent=SILVER), f"mark-{key}-mono.png")
        # reversed (indigo mark on silver field)
        rev = Image.new("RGBA", (512, 512), SILVER + (255,))
        rev.alpha_composite(fn(400, silh=INDIGO1, accent=CYAN), (56, 56))
        save(rev, f"mark-{key}-reversed.png")
        # horizontal lockup
        save(lockup_horizontal(key, fn), f"lockup-{key}-horizontal.png")
        # stacked lockup on transparent
        save(lockup_stacked(fn), f"lockup-{key}-stacked.png")

    print("monogram / app tiles...")
    save(app_tile(_mono_wrap, 512, bg=INDIGO1), "appicon-indigo.png")
    save(app_tile(_mono_wrap, 512, bg=INDIGO0, accent=AMBER), "appicon-amber.png")
    save(_mono_wrap(512), "monogram-transparent.png")
    for fav in (32, 64, 180):
        save(app_tile(_mono_wrap, fav, bg=INDIGO1), f"favicon-{fav}.png")

    print("palette...")
    save(palette_strip(), "palette.png")
    print("done ->", OUT)


if __name__ == "__main__":
    main()
