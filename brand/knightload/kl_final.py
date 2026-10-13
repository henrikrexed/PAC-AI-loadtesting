#!/usr/bin/env python3
"""
kl_final.py — Knightload FINAL brand suite (ISI-5779).

Board pick: **Direction 2 — Signal Diamond** (Henrik, interaction r3.2c accepted
dir-2-diamond). The load-signal: a night lozenge with a glowing edge housing the
Ramp-K whose ascending ramp-up is a glowing graph-bar chart.

Produces the locked family -> final/ :
  icon-only, horizontal lockup, stacked lockup, monochrome (dark+light/reversed),
  favicon set incl. a simplified 3-bar 16/32px variant, social/OG card, and
  Knightload Engine / Knightload Skills lockups. Transparent PNG.

Wordmark uses DejaVu Sans Bold as the production stand-in for Space Grotesk/Sora
(host has neither; same constraint as ISI-5724) — swap at publish.
"""
import os
from PIL import Image, ImageDraw
import kl_brand as k
import kl_signal as s

FINAL = os.path.join(os.path.dirname(__file__), "final")
os.makedirs(FINAL, exist_ok=True)

CYAN, AMBER, SILVER = k.CYAN, k.AMBER, k.SILVER
INDIGO0, INDIGO1, INDIGO2 = k.INDIGO0, k.INDIGO1, k.INDIGO2
MUTE, SILVER_DIM = k.MUTE, k.SILVER_DIM
ICON = s.sig_diamond  # the chosen mark


def _tt_width(d, fnt, trk):
    w_k = sum(d.textlength(c, font=fnt) for c in "Knight") + trk * 5
    w_l = sum(d.textlength(c, font=fnt) for c in "load") + trk * 3
    return w_k, w_l, w_k + trk + w_l


def _wordmark_width(d, px, sub=None):
    fnt = k.font(px, bold=True)
    trk = px * 0.02
    _, _, total = _tt_width(d, fnt, trk)
    if sub:
        sfnt = k.font(int(px * 0.92), bold=False)
        total += px * 0.26 + d.textlength(sub, font=sfnt)
    return total


def _fit_px(d, px, avail, sub=None):
    while px > 10 and _wordmark_width(d, px, sub) > avail:
        px -= 2
    return px


def _wordmark(d, xy, px, silver, accent, sub=None):
    """Draw 'Knight'(silver)+'load'(accent) at point xy (top-left). Optional
    sub-brand word ('Engine'/'Skills') trailing in muted silver. Returns width."""
    fnt = k.font(px, bold=True)
    trk = px * 0.02
    x, y = xy
    w1 = k.tracked_text(d, (x, y), "Knight", fnt, silver + (255,), tracking=trk)
    w2 = k.tracked_text(d, (x + w1 + trk, y), "load", fnt, accent + (255,), tracking=trk)
    total = w1 + trk + w2
    if sub:
        sfnt = k.font(int(px * 0.92), bold=False)
        gap = px * 0.26
        k.tracked_text(d, (x + total + gap, y + px * 0.04), sub, sfnt, SILVER_DIM + (255,), tracking=px * 0.02)
        total += gap + d.textlength(sub, font=sfnt)
    return total


def horizontal(accent=CYAN, bg=None, sub=None, size=(1400, 440), tagline=True,
               silver=SILVER):
    W, H = size
    img = Image.new("RGBA", (W, H), bg + (255,) if bg else (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    ic = int(H * 0.68)
    ix = int(H * 0.14)
    img.alpha_composite(ICON(ic, accent=accent), (ix, (H - ic) // 2))
    tx = ix + ic + int(H * 0.13)
    avail = W - tx - int(H * 0.12)
    px = _fit_px(d, int(H * 0.33), avail, sub=sub)
    ty = (H - px) // 2 - int(px * 0.14)
    _wordmark(d, (tx, ty), px, silver, accent, sub=sub)
    if tagline and not sub:
        d.text((tx + 4, ty + px + int(H * 0.03)), "Stop guessing. The signal shows the load.",
               font=k.font(max(18, int(px * 0.2)), bold=False), fill=MUTE + (255,))
    return img


def stacked(accent=CYAN, bg=None, size=(760, 860), silver=SILVER):
    W, H = size
    img = Image.new("RGBA", (W, H), bg + (255,) if bg else (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    ic = int(W * 0.56)
    img.alpha_composite(ICON(ic, accent=accent), ((W - ic) // 2, 60))
    px = _fit_px(d, 128, W - 100)
    total = _wordmark_width(d, px)
    sx = (W - total) / 2
    ty = 60 + ic + 46
    _wordmark(d, (sx, ty), px, silver, accent)
    k.tracked_text(d, (W / 2, ty + px + 26), "STOP  GUESSING", k.font(26, bold=False),
                   MUTE + (255,), tracking=8, anchor_mid=True)
    return img


def og_card(accent=CYAN):
    W, H = 1200, 630
    img = Image.new("RGBA", (W, H), INDIGO0 + (255,))
    d = ImageDraw.Draw(img)
    # large mark on the right (non-overlapping)
    msz = 440
    img.alpha_composite(ICON(msz, accent=accent), (W - msz - 70, (H - msz) // 2))
    # left: wordmark + tagline, auto-fit to the left column
    avail = (W - msz - 70) - 80 - 30
    px = _fit_px(d, 120, avail)
    _wordmark(d, (80, 232), px, SILVER, accent)
    d.text((84, 232 + px + 24), "Stop guessing. Load with proof.", font=k.font(36, bold=False), fill=MUTE + (255,))
    k.tracked_text(d, (84, 232 + px + 78), "THE  LOAD-SIGNAL  ·  KNIGHT · NIGHT · LOAD",
                   k.font(22, bold=True), accent + (255,), tracking=2)
    return img


def favicon_3bar(size, accent=CYAN, mono=False):
    """Simplified 3-bar diamond for crisp small sizes (promised to the board)."""
    orig = s.RK_BARS_N
    s.RK_BARS_N = 3
    try:
        return ICON(size, accent=accent, mono=mono)
    finally:
        s.RK_BARS_N = orig


def save(img, name):
    p = os.path.join(FINAL, name)
    img.convert("RGBA").save(p)
    print("  ", name, img.size)


def main():
    print("icon-only...")
    save(ICON(1024), "knightload-icon.png")
    save(ICON(512, accent=AMBER), "knightload-icon-amber.png")
    save(ICON(512, mono=True), "knightload-icon-mono-dark.png")
    save(ICON(512, mono=True, mono_col=INDIGO0), "knightload-icon-mono-light.png")

    print("lockups...")
    save(horizontal(), "knightload-lockup-horizontal.png")
    save(horizontal(bg=INDIGO1), "knightload-lockup-horizontal-onindigo.png")
    save(horizontal(accent=INDIGO0, silver=INDIGO0, bg=(247, 249, 252), tagline=True),
         "knightload-lockup-horizontal-onlight.png")
    save(stacked(), "knightload-lockup-stacked.png")

    print("sub-brand lockups...")
    save(horizontal(sub="Engine", tagline=False, size=(1600, 420)), "knightload-engine-lockup.png")
    save(horizontal(sub="Skills", tagline=False, size=(1600, 420)), "knightload-skills-lockup.png")

    print("favicons...")
    for sz in (16, 32, 48, 64, 180, 256, 512):
        save(ICON(sz), f"knightload-favicon-{sz}.png")
    save(favicon_3bar(16), "knightload-favicon-16-simple.png")
    save(favicon_3bar(32), "knightload-favicon-32-simple.png")
    save(favicon_3bar(48, mono=True), "knightload-favicon-48-mono.png")

    print("social / OG...")
    save(og_card(), "knightload-og-card.png")

    print("done ->", FINAL)


if __name__ == "__main__":
    main()
