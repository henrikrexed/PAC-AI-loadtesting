#!/usr/bin/env python3
"""
gen_concepts.py — render the Knightload concept-pick deliverables (ISI-5779 round 1).

Outputs (images/):
  knightload-concepts-overview.png   <- the board-pick sheet (all 3 + monogram + palette)
  knightload-concept-A-visor-gauge.png
  knightload-concept-B-knight-sparkline.png
  knightload-concept-C-shield-loadbar.png
  knightload-visual-system.png
"""
import os
from PIL import Image, ImageDraw
import kl_brand as kl

OUT = os.path.join(os.path.dirname(__file__), "images")
os.makedirs(OUT, exist_ok=True)

WORDMARK = "Knightload"
TAGLINE = "Stop guessing. Load from reality."


def canvas(w, h, bg=kl.INDIGO1):
    img = Image.new("RGBA", (w, h), bg + (255,))
    return img, ImageDraw.Draw(img)


def paste_center(dst, mark_img, cx, cy):
    dst.alpha_composite(mark_img, (int(cx - mark_img.width / 2), int(cy - mark_img.height / 2)))


def lockup(dst, d, x, y, icon_h, markfn, accent=kl.CYAN, silh=kl.SILVER,
           word_fill=kl.SILVER, tagline=False, tag_fill=kl.MUTE):
    """Horizontal lockup: icon + wordmark, baseline-centred. Returns right edge x."""
    ic = markfn(icon_h, silh=silh, accent=accent)
    dst.alpha_composite(ic, (int(x), int(y)))
    wx = x + icon_h + int(icon_h * 0.14)
    fs = int(icon_h * 0.40)
    fnt = kl.font(fs, bold=True)
    tr = fs * 0.02
    # vertical centring of wordmark against icon
    asc, desc = fnt.getmetrics()
    th = asc + desc
    wy = y + icon_h * 0.50 - th * 0.52
    total = kl.tracked_text(d, (wx, wy), WORDMARK, fnt, word_fill + (255,), tracking=tr)
    if tagline:
        tf = kl.font(int(icon_h * 0.135), bold=False)
        d.text((wx + 2, wy + th * 0.98), TAGLINE, font=tf, fill=tag_fill + (255,))
    return wx + total


def variant_row(dst, d, y, markfn, size, label_fs=22):
    """Row of 4 swatches: on-dark, on-light, monochrome, reversed-accent."""
    specs = [
        ("on dark",    kl.INDIGO0, dict(silh=kl.SILVER, accent=kl.CYAN)),
        ("on light",   (238, 240, 244), dict(silh=kl.INDIGO1, accent=kl.CYAN_DIM)),
        ("monochrome", kl.INDIGO0, dict(silh=kl.SILVER, accent=kl.SILVER)),
        ("amber alt",  kl.INDIGO0, dict(silh=kl.SILVER, accent=kl.AMBER)),
    ]
    sw = size + 70
    x = 90
    for (lab, bg, kw) in specs:
        d.rounded_rectangle([x, y, x + sw, y + sw], radius=26, fill=bg + (255,),
                            outline=kl.INDIGO2 + (255,), width=2)
        m = markfn(size, **kw)
        dst.alpha_composite(m, (int(x + (sw - size) / 2), int(y + (sw - size) / 2)))
        lf = kl.font(label_fs, bold=False)
        d.text((x + sw / 2, y + sw + 14), lab, font=lf, fill=kl.MUTE + (255,), anchor="ma")
        x += sw + 48
    return x


# ----------------------------------------------------------------- per concept board
def concept_board(letter, name, markfn, rationale):
    W, H = 1800, 1120
    img, d = canvas(W, H, kl.INDIGO1)
    # header
    d.rectangle([0, 0, W, 8], fill=kl.CYAN + (255,))
    d.text((90, 70), f"CONCEPT {letter}", font=kl.font(34, bold=True), fill=kl.CYAN + (255,))
    d.text((90, 118), name, font=kl.font(76, bold=True), fill=kl.INK + (255,))
    d.text((90, 214), rationale, font=kl.font(28, bold=False), fill=kl.MUTE + (255,))

    # hero icon on a dark disc
    disc = 520
    dcx, dcy = 360, 560
    d.ellipse([dcx - disc / 2, dcy - disc / 2, dcx + disc / 2, dcy + disc / 2],
              fill=kl.INDIGO0 + (255,), outline=kl.INDIGO2 + (255,), width=3)
    hero = markfn(430, silh=kl.SILVER, accent=kl.CYAN)
    paste_center(img, hero, dcx, dcy)
    d.text((dcx, dcy + disc / 2 + 26), "primary mark", font=kl.font(24, bold=False),
           fill=kl.MUTE + (255,), anchor="ma")

    # variants (right of hero)
    d.text((720, 330), "VARIANTS", font=kl.font(26, bold=True), fill=kl.SILVER_DIM + (255,))
    specs = [
        ("on dark",    kl.INDIGO0, dict(silh=kl.SILVER, accent=kl.CYAN)),
        ("on light",   (238, 240, 244), dict(silh=kl.INDIGO1, accent=kl.CYAN_DIM)),
        ("monochrome", kl.INDIGO0, dict(silh=kl.SILVER, accent=kl.SILVER)),
        ("amber alt",  kl.INDIGO0, dict(silh=kl.SILVER, accent=kl.AMBER)),
    ]
    size = 190
    sw = size + 66
    x0, y0 = 720, 380
    for i, (lab, bg, kw) in enumerate(specs):
        col, rown = i % 2, i // 2
        x = x0 + col * (sw + 60)
        y = y0 + rown * (sw + 64)
        d.rounded_rectangle([x, y, x + sw, y + sw], radius=24, fill=bg + (255,),
                            outline=kl.INDIGO2 + (255,), width=2)
        m = markfn(size, **kw)
        img.alpha_composite(m, (int(x + (sw - size) / 2), int(y + (sw - size) / 2)))
        d.text((x + sw / 2, y + sw + 12), lab, font=kl.font(22, bold=False),
               fill=kl.MUTE + (255,), anchor="ma")

    # horizontal lockup at the bottom
    ly = 940
    d.line([90, ly - 28, W - 90, ly - 28], fill=kl.INDIGO2 + (255,), width=2)
    d.text((90, ly - 20), "HORIZONTAL LOCKUP", font=kl.font(22, bold=True), fill=kl.SILVER_DIM + (255,))
    lockup(img, d, 90, ly + 20, 140, markfn, tagline=True)
    img.convert("RGB").save(os.path.join(OUT, f"knightload-concept-{letter}-{name.split()[0].lower()}.png"))
    print("wrote concept", letter)


# ----------------------------------------------------------------- overview (board pick)
def overview():
    W, H = 2400, 1500
    img, d = canvas(W, H, kl.INDIGO1)
    d.rectangle([0, 0, W, 10], fill=kl.CYAN + (255,))
    d.text((80, 70), "Knightload", font=kl.font(82, bold=True), fill=kl.INK + (255,))
    d.text((84, 176), "logo concepts — board pick  ·  Knight + Night + Load",
           font=kl.font(30, bold=False), fill=kl.MUTE + (255,))
    d.text((W - 80, 92), "ISI-5779", font=kl.font(28, bold=True), fill=kl.CYAN + (255,), anchor="ra")

    cols = [
        ("A", "Visor Gauge", kl.mark_helm,
         ["Knight great-helm, frontal.", "Visor slit = ascending load bars.",
          "Crescent moon carved in the dome.", "Primary recommendation."]),
        ("B", "Chess Knight Sparkline", kl.mark_knight,
         ["Chess-knight head silhouette.", "Mane doubles as a bar sparkline.",
          "The knight's L-move nods to Load.", ""]),
        ("C", "Shield Load-Bar", kl.mark_shield,
         ["Heater shield, guardian stance.", "Filling load bar + ramp ticks.",
          "Crescent-moon plume at the crest.", ""]),
    ]
    cw = 740
    x = 80
    for (letter, name, fn, bullets) in cols:
        y = 250
        d.rounded_rectangle([x, y, x + cw, y + 880], radius=28, fill=kl.INDIGO0 + (255,),
                            outline=kl.INDIGO2 + (255,), width=3)
        if letter == "A":
            d.rounded_rectangle([x, y, x + cw, y + 880], radius=28, outline=kl.CYAN + (255,), width=4)
            d.rounded_rectangle([x + cw - 180, y + 24, x + cw - 24, y + 70], radius=18,
                                fill=kl.CYAN + (255,))
            d.text((x + cw - 102, y + 30), "PRIMARY", font=kl.font(24, bold=True),
                   fill=kl.INDIGO0 + (255,), anchor="ma")
        d.text((x + 40, y + 36), f"CONCEPT {letter}", font=kl.font(28, bold=True), fill=kl.CYAN + (255,))
        d.text((x + 40, y + 76), name, font=kl.font(46, bold=True), fill=kl.INK + (255,))
        hero = fn(420, silh=kl.SILVER, accent=kl.CYAN)
        img.alpha_composite(hero, (int(x + (cw - 420) / 2), int(y + 150)))
        by = y + 600
        for b in bullets:
            if b:
                d.text((x + 44, by), "•  " + b, font=kl.font(26, bold=False), fill=kl.MUTE + (255,))
            by += 42
        # mini lockup
        lockup(img, d, x + 40, y + 790, 80, fn)
        x += cw + 40

    # footer: monogram app icon + palette + accent note
    fy = 1180
    d.line([80, fy - 24, W - 80, fy - 24], fill=kl.INDIGO2 + (255,), width=2)
    d.text((80, fy - 14), "APP ICON / MONOGRAM", font=kl.font(24, bold=True), fill=kl.SILVER_DIM + (255,))
    mono = kl.mark_monogram(220, tile_bg=kl.INDIGO0)
    img.alpha_composite(mono, (90, fy + 30))
    mono2 = kl.mark_monogram(220, accent=kl.AMBER, tile_bg=kl.INDIGO0)
    img.alpha_composite(mono2, (330, fy + 30))

    # palette swatches
    d.text((640, fy + 20), "PALETTE", font=kl.font(24, bold=True), fill=kl.SILVER_DIM + (255,))
    sw = [("#1A1A2E", kl.INDIGO0), ("#16213E", kl.INDIGO1), ("#C7CDD6", kl.SILVER),
          ("#2EE6D6", kl.CYAN), ("#FFB23E", kl.AMBER)]
    sx = 640
    for (hexv, col) in sw:
        d.rounded_rectangle([sx, fy + 60, sx + 150, fy + 180], radius=16, fill=col + (255,),
                            outline=kl.INDIGO2 + (255,), width=2)
        tcol = kl.INDIGO0 if sum(col) > 420 else kl.INK
        d.text((sx + 75, fy + 190), hexv, font=kl.font(22, bold=True), fill=kl.MUTE + (255,), anchor="ma")
        sx += 172

    d.text((1560, fy + 20), "TYPE", font=kl.font(24, bold=True), fill=kl.SILVER_DIM + (255,))
    d.text((1560, fy + 58), "Wordmark: Space Grotesk / Sora", font=kl.font(28, bold=True), fill=kl.INK + (255,))
    d.text((1560, fy + 100), "(shown here in DejaVu Bold — production", font=kl.font(22, bold=False), fill=kl.MUTE + (255,))
    d.text((1560, fy + 128), " font swapped at build; icons are font-free vector)", font=kl.font(22, bold=False), fill=kl.MUTE + (255,))
    d.text((1560, fy + 176), "Accent: electric cyan (primary) · amber (alt)", font=kl.font(24, bold=False), fill=kl.CYAN + (255,))

    img.convert("RGB").save(os.path.join(OUT, "knightload-concepts-overview.png"))
    print("wrote overview")


# ----------------------------------------------------------------- visual system
def visual_system():
    W, H = 2000, 1200
    img, d = canvas(W, H, kl.INDIGO1)
    d.rectangle([0, 0, W, 8], fill=kl.CYAN + (255,))
    d.text((80, 64), "Knightload — visual system", font=kl.font(64, bold=True), fill=kl.INK + (255,))
    d.text((84, 150), "starting point (refine as the final mark locks)", font=kl.font(28, bold=False), fill=kl.MUTE + (255,))

    # palette
    d.text((80, 250), "COLOUR", font=kl.font(28, bold=True), fill=kl.SILVER_DIM + (255,))
    sw = [("Midnight 1A1A2E", kl.INDIGO0, "deepest base"),
          ("Midnight 16213E", kl.INDIGO1, "primary bg"),
          ("Brushed silver C7CDD6", kl.SILVER, "primary mark"),
          ("Electric cyan 2EE6D6", kl.CYAN, "accent · primary"),
          ("Amber FFB23E", kl.AMBER, "accent · alternate")]
    x = 80
    for (name, col, role) in sw:
        d.rounded_rectangle([x, 300, x + 340, 470], radius=20, fill=col + (255,),
                            outline=kl.INDIGO2 + (255,), width=2)
        tcol = kl.INDIGO0 if sum(col) > 420 else kl.INK
        d.text((x + 24, 420), name, font=kl.font(24, bold=True), fill=tcol + (255,))
        d.text((x + 24, 484), role, font=kl.font(22, bold=False), fill=kl.MUTE + (255,))
        x += 372

    # type
    d.text((80, 580), "TYPE", font=kl.font(28, bold=True), fill=kl.SILVER_DIM + (255,))
    kl.tracked_text(d, (80, 620), "Knightload", kl.font(120, bold=True), kl.SILVER + (255,), tracking=2)
    d.text((80, 770), "Geometric modern sans — Space Grotesk / Sora (DejaVu Bold stand-in here).",
           font=kl.font(26, bold=False), fill=kl.MUTE + (255,))
    d.text((80, 808), "Lockups: Knightload  ·  Knightload Engine  ·  Knightload Skills",
           font=kl.font(26, bold=False), fill=kl.MUTE + (255,))

    # mark trio preview
    d.text((80, 900), "MARKS", font=kl.font(28, bold=True), fill=kl.SILVER_DIM + (255,))
    for i, fn in enumerate([kl.mark_helm, kl.mark_knight, kl.mark_shield]):
        m = fn(200, silh=kl.SILVER, accent=kl.CYAN)
        img.alpha_composite(m, (80 + i * 240, 940))
    mono = kl.mark_monogram(200, tile_bg=kl.INDIGO0)
    img.alpha_composite(mono, (80 + 3 * 240, 940))
    img.convert("RGB").save(os.path.join(OUT, "knightload-visual-system.png"))
    print("wrote visual-system")


if __name__ == "__main__":
    concept_board("A", "Visor Gauge", kl.mark_helm, "Knight great-helm · visor slit becomes a load gauge · crescent moon in negative space.")
    concept_board("B", "Chess Knight Sparkline", kl.mark_knight, "Chess-knight head · mane doubles as a bar sparkline · the L-move nods to 'Load'.")
    concept_board("C", "Shield Load-Bar", kl.mark_shield, "Heater shield · a filling load bar + ramp ticks · crescent-moon plume at the crest.")
    overview()
    visual_system()
    print("done")
