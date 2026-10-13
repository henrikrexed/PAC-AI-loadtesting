#!/usr/bin/env python3
"""kl_signal_render.py — render the LOAD-SIGNAL deliverables (ISI-5779 r3.2)."""
import os
from PIL import Image, ImageDraw
import kl_brand as k
import kl_signal as s

OUT = os.path.join(os.path.dirname(__file__), "png")
IMG = os.path.join(os.path.dirname(__file__), "images")
os.makedirs(OUT, exist_ok=True); os.makedirs(IMG, exist_ok=True)

CYAN, AMBER, SILVER = k.CYAN, k.AMBER, k.SILVER
INDIGO0, INDIGO1, INDIGO2 = k.INDIGO0, k.INDIGO1, k.INDIGO2

DIRS = [
    ("1", "Signal Circle", s.sig_circle,
     "K glowing in a night roundel · halo + slim rising signal shaft.", False),
    ("2", "Signal Diamond", s.sig_diamond,
     "K knocked out of a glowing lozenge — projector beam, plot-point & badge in one.", True),
    ("3", "Signal Minimal", s.sig_minimal,
     "Circle + K, thin stroke, monochrome. The signal reduced to essence — 16px-proof.", False),
    ("4", "Signal K-Ray", s.sig_kray,
     "The K's ascending arm fires off as a beam escaping the lozenge — load curve + signal.", False),
]


def _wrap(d, text, xy, maxw, fnt, color):
    x, y = xy; words = text.split(); line = ""
    for w in words:
        t = (line + " " + w).strip()
        if d.textlength(t, font=fnt) > maxw and line:
            d.text((x, y), line, font=fnt, fill=color + (255,)); y += fnt.size + 7; line = w
        else:
            line = t
    if line:
        d.text((x, y), line, font=fnt, fill=color + (255,))
    return y


def hero_lockup(size=(1280, 440), glyph=s.sig_diamond, accent=CYAN, bg=INDIGO1):
    W, H = size
    img = Image.new("RGBA", (W, H), bg + (255,) if bg else (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    ic = int(H * 0.72)
    ix = int(H * 0.16)
    img.alpha_composite(glyph(ic, accent=accent), (ix, (H - ic) // 2))
    px = int(H * 0.34)
    fnt = k.font(px, bold=True)
    tx = ix + ic + int(H * 0.14)
    trk = px * 0.02
    w_k = sum(d.textlength(c, font=fnt) for c in "Knight") + trk * 5
    ty = (H - px) // 2 - int(px * 0.16)
    w1 = k.tracked_text(d, (tx, ty), "Knight", fnt, SILVER + (255,), tracking=trk)
    k.tracked_text(d, (tx + w1 + trk, ty), "load", fnt, accent + (255,), tracking=trk)
    d.text((tx + 4, ty + px + int(H * 0.02)), "Stop guessing. The signal shows the load.",
           font=k.font(max(18, int(px * 0.2)), bold=False), fill=k.MUTE + (255,))
    return img


def board():
    W, H = 1680, 1120
    img = Image.new("RGBA", (W, H), INDIGO0 + (255,))
    d = ImageDraw.Draw(img)
    d.text((60, 44), "KNIGHTLOAD", font=k.font(58, bold=True), fill=SILVER + (255,))
    k.tracked_text(d, (62, 116),
                   "THE  LOAD-SIGNAL  ·  round 3.2  ·  the signal lights up, the knight answers  ·  pick one",
                   k.font(24, bold=True), CYAN + (255,), tracking=3)
    d.line([60, 162, W - 60, 162], fill=INDIGO2 + (255,), width=3)
    colw = (W - 120) // 4
    y0 = 196
    for i, (key, name, fn, desc, rec) in enumerate(DIRS):
        cx = 60 + i * colw
        panel = [cx + 8, y0, cx + colw - 8, y0 + 560]
        d.rounded_rectangle(panel, radius=20,
                            fill=INDIGO1 + (255,),
                            outline=(CYAN + (255,)) if rec else None,
                            width=4 if rec else 0)
        d.text((cx + 28, y0 + 22), f"Direction {key}", font=k.font(28, bold=True), fill=CYAN + (255,))
        if rec:
            bfnt = k.font(15, bold=True)
            label = "RECOMMENDED"
            tw = d.textlength(label, font=bfnt)
            bx1 = cx + colw - 22
            bx0 = bx1 - (tw + 24)
            d.rounded_rectangle([bx0, y0 + 24, bx1, y0 + 54], radius=15, fill=CYAN + (255,))
            d.text((bx0 + 12, y0 + 30), label, font=bfnt, fill=INDIGO0 + (255,))
        d.text((cx + 28, y0 + 60), name, font=k.font(26, bold=True), fill=k.SILVER_HI + (255,))
        ic = 230
        img.alpha_composite(fn(ic), (cx + (colw - ic) // 2, y0 + 104))
        yend = _wrap(d, desc, (cx + 28, y0 + 352), colw - 56, k.font(20, bold=False), k.MUTE)
        # mini favicon strip
        d.text((cx + 28, yend + 24), "16 · 24 · 32 px", font=k.font(16, bold=True), fill=k.SILVER_DIM + (255,))
        fx = cx + 28; fy = yend + 50
        for sz in (16, 24, 32):
            img.alpha_composite(fn(sz), (fx, fy + (32 - sz))); fx += sz + 14
        # mono mini
        for sz in (16, 24, 32):
            img.alpha_composite(fn(sz, mono=True), (fx + 20, fy + (32 - sz))); fx += sz + 14
    # hero lockup
    ly = y0 + 588
    d.text((60, ly), "HERO  LOCKUP  (signal glyph + wordmark · Knight silver · load accent)",
           font=k.font(22, bold=True), fill=SILVER + (255,))
    img.alpha_composite(hero_lockup((980, 230), glyph=s.sig_diamond, accent=CYAN), (60, ly + 36))
    # accent options + amber alt glyph
    d.text((1080, ly), "ACCENT  GLOW", font=k.font(22, bold=True), fill=SILVER + (255,))
    img.alpha_composite(s.sig_diamond(180, accent=CYAN), (1080, ly + 44))
    img.alpha_composite(s.sig_diamond(180, accent=AMBER), (1290, ly + 44))
    d.text((1095, ly + 230), "teal (default)", font=k.font(18, bold=False), fill=k.MUTE + (255,))
    d.text((1305, ly + 230), "amber (alt)", font=k.font(18, bold=False), fill=k.MUTE + (255,))
    d.text((60, H - 40),
           "Defensibly original: geometric K + abstract signal — no bat silhouette, no DC proximity.   "
           "Wordmark = DejaVu stand-in for Space Grotesk/Sora.   Icons = production-true vector.",
           font=k.font(16, bold=False), fill=k.SILVER_DIM + (255,))
    return img


def save(img, path, name):
    p = os.path.join(path, name); img.convert("RGBA").save(p); print("  ", name, img.size)


def main():
    print("round-3.2 board...")
    save(board(), IMG, "knightload-signal-board.png")
    print("hero lockups...")
    save(hero_lockup(glyph=s.sig_diamond, accent=CYAN), OUT, "signal-lockup-diamond-cyan.png")
    save(hero_lockup(glyph=s.sig_circle, accent=CYAN), OUT, "signal-lockup-circle-cyan.png")
    save(hero_lockup(glyph=s.sig_diamond, accent=AMBER), OUT, "signal-lockup-diamond-amber.png")
    print("per-direction marks...")
    for key, name, fn, desc, rec in DIRS:
        save(fn(512), OUT, f"signal-{key}-ondark.png")  # own bg handled inside
        save(fn(512, mono=True), OUT, f"signal-{key}-mono.png")
        save(fn(512, accent=AMBER), OUT, f"signal-{key}-amber.png")
        # transparent variant = same (marks already transparent outside shape)
    print("favicons (recommended = diamond)...")
    for sz in (16, 32, 48, 180, 512):
        save(s.sig_diamond(sz), OUT, f"signal-favicon-{sz}.png")
    print("done ->", OUT, IMG)


if __name__ == "__main__":
    main()
