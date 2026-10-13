#!/usr/bin/env python3
"""
gen_k.py — Knightload K-letterform round 3.1 board sheet (ISI-5779).

Outputs images/:
  knightload-K-directions.png   <- board-pick sheet: 4 K directions x (hero / mono / 16-24-32-64 proof) + wordmark-first
"""
import os
from PIL import Image, ImageDraw
import kl_brand as kl
import kl_k

OUT = os.path.join(os.path.dirname(__file__), "images")
os.makedirs(OUT, exist_ok=True)


def wordmark_first(dst, d, x, y, h, kfn, accent=kl.CYAN):
    """Hero-K wordmark: K glyph (heavier) + 'nightload' lighter, two-tone."""
    k = kfn(h, accent=accent)
    dst.alpha_composite(k, (int(x), int(y)))
    fs = int(h * 0.52)
    f_hi = kl.font(fs, bold=True)
    f_lo = kl.font(fs, bold=False)
    tx = x + h + int(h * 0.02)
    ty = y + h * 0.5 - fs * 0.62
    # 'Knightload' with K already the mark -> render 'nightload'
    d.text((tx, ty), "nightload", font=f_hi, fill=kl.SILVER + (255,))
    return tx


def board():
    W, H = 2560, 1620
    img = Image.new("RGBA", (W, H), kl.INDIGO1 + (255,))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, 10], fill=kl.CYAN + (255,))
    d.text((80, 64), "Knightload", font=kl.font(76, bold=True), fill=kl.INK + (255,))
    d.text((84, 162), "round 3.1 — the K, evolved  ·  geometric, not illustrative  ·  survives 16 px",
           font=kl.font(28, bold=False), fill=kl.MUTE + (255,))
    d.text((W - 80, 84), "ISI-5779", font=kl.font(26, bold=True), fill=kl.CYAN + (255,), anchor="ra")
    d.text((W - 80, 122), "“j’aime le K” — keep the letter, drop the knight", font=kl.font(22, bold=False),
           fill=kl.MUTE + (255,), anchor="ra")

    row_y = 250
    rh = 300
    hero = 220
    for i, (code, name, desc, fn) in enumerate(kl_k.K_DIRS):
        y = row_y + i * (rh + 14)
        d.rounded_rectangle([80, y, W - 80, y + rh], radius=24, fill=kl.INDIGO0 + (255,),
                            outline=kl.INDIGO2 + (255,), width=2)
        # label block
        d.text((112, y + 30), code, font=kl.font(40, bold=True), fill=kl.CYAN + (255,))
        d.text((112, y + 82), name, font=kl.font(34, bold=True), fill=kl.INK + (255,))
        # wrap desc
        words = desc.split()
        lines, cur = [], ""
        for w in words:
            if len(cur) + len(w) < 30:
                cur = (cur + " " + w).strip()
            else:
                lines.append(cur); cur = w
        lines.append(cur)
        for j, ln in enumerate(lines):
            d.text((112, y + 128 + j * 30), ln, font=kl.font(22, bold=False), fill=kl.MUTE + (255,))

        # hero on dark
        hx = 480
        hcx = hx + hero // 2
        d.text((hcx, y + 18), "mark", font=kl.font(20, bold=False), fill=kl.SILVER_DIM + (255,), anchor="ma")
        img.alpha_composite(fn(hero, accent=kl.CYAN), (hx, y + (rh - hero) // 2 + 14))

        # monochrome
        mx = 760
        d.text((mx + hero // 2, y + 18), "monochrome", font=kl.font(20, bold=False), fill=kl.SILVER_DIM + (255,), anchor="ma")
        img.alpha_composite(fn(hero, mono=True, silh=kl.SILVER), (mx, y + (rh - hero) // 2 + 14))

        # amber line variant (small)
        ax = 1040
        d.text((ax + 120, y + 18), "amber", font=kl.font(20, bold=False), fill=kl.SILVER_DIM + (255,), anchor="ma")
        img.alpha_composite(fn(160, accent=kl.AMBER), (ax, y + (rh - 160) // 2 + 14))

        # size-proof strip: 16 / 24 / 32 / 64 px actual size on a light chip + dark chip
        px0 = 1320
        d.text((px0, y + 18), "favicon proof — 16 · 24 · 32 · 64 px",
               font=kl.font(20, bold=False), fill=kl.SILVER_DIM + (255,))
        cx = px0
        cy = y + 70
        for sz in [16, 24, 32, 64]:
            chip = sz + 26
            # dark chip
            d.rounded_rectangle([cx, cy, cx + chip, cy + chip], radius=8, fill=kl.INDIGO2 + (255,))
            img.alpha_composite(fn(sz, accent=kl.CYAN), (cx + 13, cy + 13))
            # light chip (mono) below
            d.rounded_rectangle([cx, cy + chip + 10, cx + chip, cy + 2 * chip + 10], radius=8, fill=(235, 238, 242, 255))
            img.alpha_composite(fn(sz, mono=True, silh=kl.INDIGO1), (cx + 13, cy + chip + 23))
            d.text((cx + chip // 2, cy + 2 * chip + 16), f"{sz}", font=kl.font(18, bold=False),
                   fill=kl.MUTE + (255,), anchor="ma")
            cx += chip + 22

        # README / banner context (mark + wordmark at mid scale)
        bx = max(cx + 30, 1720)
        d.text((bx, y + 18), "wordmark in context", font=kl.font(20, bold=False), fill=kl.SILVER_DIM + (255,))
        wordmark_first(img, d, bx, y + 86, 92, fn, accent=kl.CYAN)

    # footer note
    fy = H - 70
    d.text((80, fy), "Palette: midnight indigo #1A1A2E/#16213E · brushed silver #C7CDD6 · accent electric cyan #2EE6D6 (amber #FFB23E alt).  "
                     "Wordmark: Space Grotesk / Sora (DejaVu stand-in). All marks pure vector → PNG + SVG.",
           font=kl.font(22, bold=False), fill=kl.MUTE + (255,))

    img.convert("RGB").save(os.path.join(OUT, "knightload-K-directions.png"))
    print("wrote K-directions board")


if __name__ == "__main__":
    board()
