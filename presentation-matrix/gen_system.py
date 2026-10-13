#!/usr/bin/env python3
"""
gen_system.py — the themed visual system + slide masters + exemplar slides for the PAC deck
(ISI-5724 / workstream B). Slides are 2560x1440 (16:9) PNGs with the dark Matrix base baked in.

Outputs (images/):
  00-visual-system.png      palette · type scale · motifs · do/don't
  master-title.png          title layout
  master-section.png        section-divider layout
  master-content.png        content (bullets + visual) layout
  master-demo.png           live-terminal layout
  master-discussion.png     💬 discussion-beat layout
  slide-01-title.png        exemplars applying the masters to A's real copy
  slide-02-bluepill.png
  slide-08-dual.png         (content master hosting diagram d3)
  slide-10-discussion.png
  slide-15-demo.png
  slide-19-loop.png         (content master hosting diagram d1)
"""
import os
import mtx_theme as T
from mtx_theme import (canvas, save, font, text_c, text_l, text_r, measure, para, wrap,
                       panel, chip, rrect, arrow, dashed_line, glow_rect, code_rain,
                       rain_backdrop, pill, lock, badge, place)
from PIL import Image

OUT = os.path.join(os.path.dirname(__file__), "images")
W, H = 2560, 1440
TALK = "There is no spoon · PAC 2026 · IsItObservable"

# ---------------------------------------------------------------- slide chrome
def slide_bg(rain=True, rain_density=0.22, rain_seed=7, rain_region=None):
    img, d = canvas(W, H, bg=T.BG0)
    if rain:
        reg = rain_region or (0, 0, W, H)
        code_rain(img, reg, density=rain_density, color=T.RAIN, head=(40, 110, 72),
                  size=26, seed=rain_seed)
        d = __import__("PIL.ImageDraw", fromlist=["ImageDraw"]).Draw(img)
    # top hairline accent
    d.rectangle([0, 0, W, 6], fill=T.GREEN)
    return img, d

def chrome(d, section, num, total=21):
    # footer rule + metadata
    d.line([90, H-78, W-90, H-78], fill=T.LINE, width=2)
    text_l(d, (90, H-58), TALK, font("mono", 22), fill=T.FAINT)
    text_r(d, W-90, H-58, f"{section}", font("mono", 22, bold=True), fill=T.GREEN_DIM)
    text_r(d, W-90, H-30, f"{num:02d} / {total}", font("mono", 22), fill=T.FAINT)

def kicker_title(d, kicker, title, y=120, accent=T.GREEN, tsize=84, max_w=2200):
    text_l(d, (90, y), kicker, font("mono", 28, bold=True), fill=accent)
    yy = y + 44
    for ln in wrap(d, title, font("sans", tsize, bold=True), max_w):
        text_l(d, (90, yy), ln, font("sans", tsize, bold=True), fill=T.INK)
        yy += int(tsize * 1.12)
    return yy

def bullet(d, x, y, s, fnt, fill=T.INK, mark=T.GREEN, max_w=1100, lh=1.42):
    d.ellipse([x, y+fnt.size*0.38, x+14, y+fnt.size*0.38+14], fill=mark)
    yy = y
    for i, ln in enumerate(wrap(d, s, fnt, max_w)):
        text_l(d, (x+36, yy), ln, fnt, fill=fill)
        yy += int(fnt.size*lh)
    return yy + 10

def fit_place(img, diagram_path, box, pad=0):
    """scale a diagram PNG into box, centered."""
    dg = Image.open(diagram_path).convert("RGBA")
    bx0, by0, bx1, by1 = box
    bw, bh = (bx1-bx0-2*pad), (by1-by0-2*pad)
    scale = min(bw/dg.width, bh/dg.height)
    nw, nh = int(dg.width*scale), int(dg.height*scale)
    dg = dg.resize((nw, nh), Image.LANCZOS)
    img.alpha_composite(dg, (bx0+pad+(bw-nw)//2, by0+pad+(bh-nh)//2))

# ================================================================ VISUAL SYSTEM
def visual_system():
    img, d = slide_bg(rain=True, rain_density=0.5, rain_seed=13, rain_region=(W-300, 0, W, H))
    chrome(d, "visual system", 0)
    kicker_title(d, "THE MATRIX · PROFESSIONAL · A THIN FRAMING LAYER", "Visual system", y=96, tsize=76)

    # ---- palette row
    text_l(d, (90, 300), "PALETTE", font("mono", 26, bold=True), fill=T.MUTE)
    swatches = [
        ("BG0", T.BG0, "base"), ("BG1", T.BG1, "panel"), ("BG2", T.BG2, "raised"),
        ("LINE", T.LINE2, "border"),
        ("GREEN", T.GREEN, "signal / truth"), ("RED", T.RED, "red pill · the gate"),
        ("BLUE", T.BLUE, "blue pill · guess"), ("AMBER", T.AMBER, "caution · unavail"),
        ("INK", T.INK, "text"), ("MUTE", T.MUTE, "text 2"),
    ]
    x = 90
    for name, col, role in swatches:
        rrect(d, [x, 346, x+228, 474], radius=14, fill=col, outline=T.LINE)
        tcol = T.BG0 if name in ("GREEN","INK","MUTE","AMBER","BLUE") else T.INK
        text_l(d, (x+16, 356), name, font("mono", 24, bold=True), fill=tcol)
        r,g,b = col
        text_l(d, (x+16, 440), f"#{r:02X}{g:02X}{b:02X}", font("mono", 18), fill=tcol)
        text_l(d, (x, 486), role, font("mono", 18), fill=T.FAINT)
        x += 244

    # ---- type scale
    text_l(d, (90, 560), "TYPE  ·  DejaVu Sans (titles) + DejaVu Sans Mono (code/labels)",
           font("mono", 26, bold=True), fill=T.MUTE)
    text_l(d, (90, 604), "There is no spoon", font("sans", 84, bold=True), fill=T.INK)
    text_l(d, (90, 712), "Section / slide title — Sans Bold 84/56", font("sans", 40, bold=True), fill=T.INK)
    text_l(d, (90, 772), "Body copy — Sans 40 · ≤6-word bullets where possible", font("sans", 36), fill=T.MUTE)
    text_l(d, (90, 826), "fetch user.sessions | summarize sessions=count()  — Mono 32", font("mono", 32), fill=T.GREEN_HI)

    # ---- motifs (right column)
    mx = 1480
    text_l(d, (mx, 560), "MOTIFS", font("mono", 26, bold=True), fill=T.MUTE)
    # pills + labels directly beneath each
    pill(d, (mx+120, 636), 200, 72, T.RED, "RED", fnt=font("sans", 30, bold=True))
    pill(d, (mx+360, 636), 200, 72, T.BLUE, "BLUE", fnt=font("sans", 30, bold=True))
    text_c(d, mx+120, 696, "observed truth", font("mono", 20), fill=T.RED)
    text_c(d, mx+120, 722, "· the gate", font("mono", 19), fill=T.FAINT)
    text_c(d, mx+360, 696, "guessing", font("mono", 20), fill=T.BLUE)
    text_c(d, mx+360, 722, "· synthetic", font("mono", 19), fill=T.FAINT)
    # lock + badge
    lock(d, (mx+40, 806), size=46, color=T.RED)
    text_l(d, (mx+90, 786), "V1 gate (the Oracle)", font("mono", 24), fill=T.INK)
    badge(d, (mx+90, 826), "logs · unavailable", font("mono", 22, bold=True), fg=T.AMBER)
    # rain sample
    rb = [mx+620, 600, mx+880, 850]
    panel(d, rb, fill=T.BG1, outline=T.LINE)
    code_rain(img, (rb[0]+10, rb[1]+10, rb[2]-10, rb[3]-10), density=0.9,
              color=T.RAIN, head=T.GREEN_HI, size=24, seed=3)
    d2 = __import__("PIL.ImageDraw", fromlist=["ImageDraw"]).Draw(img)
    text_c(d2, (rb[0]+rb[2])//2, rb[3]-26, "code-rain (use sparingly)", font("mono", 18), fill=T.FAINT)

    # ---- discipline note
    d2.line([90, 930, W-90, 930], fill=T.LINE, width=2)
    text_l(d2, (90, 958), "DISCIPLINE", font("mono", 26, bold=True), fill=T.GREEN)
    rules = [
        "Theme = punctuation, not argument. In the technical core, numbers carry the weight.",
        "ONE structural accent (green). Red/blue only where guess-vs-truth is the actual point.",
        "Reserve the glitch treatment for the sampling slide. Dashed+amber = 'unavailable' (logs leg).",
        "Every Matrix line maps to a real technical claim — or it gets cut.",
    ]
    yy = 1004
    for r in rules:
        text_l(d2, (90, yy), "›", font("mono", 32, bold=True), fill=T.GREEN)
        text_l(d2, (128, yy), r, font("sans", 30), fill=T.MUTE)
        yy += 56
    save(img, os.path.join(OUT, "00-visual-system.png"))
    print("  wrote 00-visual-system")

# ================================================================ MASTERS
def master_title(exemplar=False):
    img, d = slide_bg(rain=True, rain_density=0.5, rain_seed=11)
    # darken center band for legibility
    band = Image.new("RGBA", (W, H), (0,0,0,0))
    from PIL import ImageDraw as _ID
    _ID.Draw(band).rectangle([0, 430, W, 1010], fill=(7,10,8,150))
    img.alpha_composite(band)
    d = _ID.Draw(img)
    d.rectangle([0, 0, W, 6], fill=T.GREEN)
    if exemplar:
        text_c(d, W//2, 560, "There is no spoon", font("sans", 150, bold=True), fill=T.WHITE)
        text_c(d, W//2, 700, "Load-testing the real world", font("sans", 56), fill=T.GREEN_HI)
        text_c(d, W//2, 810, "Henrik Rexed · IsItObservable", font("mono", 38), fill=T.MUTE)
        pill(d, (W//2-70, 920), 110, 56, T.RED, fnt=None)
        pill(d, (W//2+70, 920), 110, 56, T.BLUE, fnt=None)
        text_c(d, W//2, 1000, "take the red pill — stop guessing, load the real world", font("sans", 30, italic=True), fill=T.FAINT)
        chrome(d, "title", 1)
        save(img, os.path.join(OUT, "slide-01-title.png")); print("  wrote slide-01-title")
    else:
        text_c(d, W//2, 520, "⟦ TITLE ⟧", font("mono", 34, bold=True), fill=T.GREEN)
        text_c(d, W//2, 600, "Deck title — Sans Bold ~150", font("sans", 72, bold=True), fill=T.INK)
        text_c(d, W//2, 710, "subtitle — Sans 56", font("sans", 48), fill=T.MUTE)
        text_c(d, W//2, 800, "speaker · org — Mono 38", font("mono", 36), fill=T.FAINT)
        pill(d, (W//2-70, 910), 110, 56, T.RED, fnt=None)
        pill(d, (W//2+70, 910), 110, 56, T.BLUE, fnt=None)
        text_c(d, W//2, 1180, "MASTER · full-bleed code-rain · pills introduced · bookended by close slide",
               font("mono", 24), fill=T.FAINT)
        chrome(d, "master · title", 0)
        save(img, os.path.join(OUT, "master-title.png")); print("  wrote master-title")

def master_section():
    img, d = slide_bg(rain=True, rain_density=0.28, rain_seed=5,
                      rain_region=(W-680, 0, W, H))
    d.rectangle([0, 0, W, 6], fill=T.GREEN)
    # big section number
    text_l(d, (90, 420), "§", font("sans", 120, bold=True), fill=T.GREEN_DIM)
    text_l(d, (240, 430), "03", font("mono", 170, bold=True), fill=T.GREEN)
    text_l(d, (90, 760), "SECTION NAME", font("sans", 88, bold=True), fill=T.INK)
    text_l(d, (90, 880), "one-line framing — the film beat for this act", font("sans", 40, italic=True), fill=T.MUTE)
    # pill divider
    pill(d, (W-360, 600), 120, 60, T.RED, fnt=None)
    pill(d, (W-360, 700), 120, 60, T.BLUE, fnt=None)
    text_c(d, W//2, 1180, "MASTER · section divider · large numeral · rain on right third",
           font("mono", 24), fill=T.FAINT)
    chrome(d, "master · section", 0)
    save(img, os.path.join(OUT, "master-section.png")); print("  wrote master-section")

def master_content(exemplar=None):
    img, d = slide_bg(rain=True, rain_density=0.14, rain_seed=9,
                      rain_region=(W-420, 0, W, H))
    d.rectangle([0, 0, W, 6], fill=T.GREEN)
    if exemplar == "bluepill":
        kicker_title(d, "SLIDE 2 · THE CHOICE EVERY ENGINEER MAKES", "The blue pill load test", y=120, tsize=84)
        y = 420
        y = bullet(d, 100, y, "Blue pill: run the test you always run. Dashboard green. Believe what you want.", font("sans", 40), max_w=1180, mark=T.BLUE)
        y = bullet(d, 100, y+18, "Red pill: look at what production actually does.", font("sans", 40), max_w=1180, mark=T.RED)
        y = bullet(d, 100, y+18, "“…how deep the rabbit hole goes.”", font("sans", 40), fill=T.GREEN_HI, max_w=1180, mark=T.GREEN)
        y = bullet(d, 100, y+18, "This talk is the red pill.", font("sans", 44, bold=True), max_w=1180, mark=T.RED)
        # right visual: blue (green-check dash) vs red (messy curve)
        vb = [1500, 400, W-90, 1120]
        panel(d, vb, fill=T.BG1, outline=T.LINE2)
        midx = (vb[0]+vb[2])//2
        d.line([midx, vb[1]+40, midx, vb[3]-40], fill=T.LINE2, width=2)
        text_c(d, (vb[0]+midx)//2, vb[1]+50, "BLUE PILL", font("mono", 26, bold=True), fill=T.BLUE)
        text_c(d, (midx+vb[2])//2, vb[1]+50, "RED PILL", font("mono", 26, bold=True), fill=T.RED)
        # flat synthetic ramp (blue)
        import math
        pts=[]
        for i in range(60):
            xx = vb[0]+40 + i*((midx-vb[0]-80)/59)
            yy = vb[3]-120 - (i/59)*220
            pts.append((xx,yy))
        d.line(pts, fill=T.BLUE, width=4)
        text_c(d, (vb[0]+midx)//2, vb[3]-70, "flat synthetic ramp ✓", font("mono", 22), fill=T.FAINT)
        # jagged real curve (red)
        import random as _r; rr=_r.Random(4); pts=[]
        for i in range(80):
            xx = midx+40 + i*((vb[2]-midx-80)/79)
            base = vb[3]-180 - 120*math.sin(i/7.0) - (i/79)*60
            yy = base + rr.randint(-50,50)
            pts.append((xx,yy))
        d.line(pts, fill=T.RED, width=4)
        text_c(d, (midx+vb[2])//2, vb[3]-70, "jagged real traffic", font("mono", 22), fill=T.FAINT)
        chrome(d, "§2 · the choice", 2)
        save(img, os.path.join(OUT, "slide-02-bluepill.png")); print("  wrote slide-02-bluepill")
    elif exemplar in ("dual","loop"):
        # the diagrams are self-contained full slides (own title + caption) — place full-bleed,
        # no duplicate slide title.
        meta = {"dual": ("d3-dual-source.png", "§2 · where truth lives", 8),
                "loop": ("d1-loop.png", "§3 · the loop", 19)}[exemplar]
        fit_place(img, os.path.join(OUT, meta[0]), [70, 40, W-70, H-116], pad=0)
        d = __import__("PIL.ImageDraw", fromlist=["ImageDraw"]).Draw(img)
        d.rectangle([0,0,W,6], fill=T.GREEN)
        chrome(d, meta[1], meta[2])
        name = {"dual":"slide-08-dual","loop":"slide-19-loop"}[exemplar]
        save(img, os.path.join(OUT, f"{name}.png")); print(f"  wrote {name}")
    else:
        kicker_title(d, "SLIDE N · KICKER (SECTION TAG)", "Content slide title", y=120, tsize=84)
        y = 420
        for s in ["First point — ≤6 words where possible",
                  "Second point — the number, earned",
                  "Third point — honest caveat on the slide",
                  "A Matrix line only if it carries a claim"]:
            y = bullet(d, 100, y, s, font("sans", 40), max_w=1120)
            y += 16
        vb = [1500, 400, W-90, 1120]
        panel(d, vb, fill=T.BG1, outline=T.LINE2)
        text_c(d, (vb[0]+vb[2])//2, (vb[1]+vb[3])//2, "VISUAL / DIAGRAM\nslot", font("mono", 34, bold=True), fill=T.FAINT)
        text_c(d, W//2, 1180, "MASTER · content · bullets left · visual/diagram right (or full-bleed diagram)",
               font("mono", 24), fill=T.FAINT)
        chrome(d, "master · content", 0)
        save(img, os.path.join(OUT, "master-content.png")); print("  wrote master-content")

def master_demo(exemplar=False):
    img, d = slide_bg(rain=False)
    d.rectangle([0, 0, W, 6], fill=T.GREEN)
    kick = "SLIDES 15–18 · LIVE" if exemplar else "SLIDES 15–18 · DEMO"
    kicker_title(d, kick, "Load the program — LIVE", y=96, tsize=72)
    # LIVE badge top-right
    badge(d, (W-430, 120), "● LIVE — DQL vs Astroshop", font("mono", 26, bold=True), fg=T.RED)
    # terminal window
    tb = [120, 300, W-120, H-150]
    panel(d, tb, fill=(6,9,7), outline=T.LINE2, width=2, radius=16)
    # title bar
    d.rounded_rectangle([tb[0], tb[1], tb[2], tb[1]+56], radius=16, fill=T.BG2)
    d.rectangle([tb[0], tb[1]+40, tb[2], tb[1]+56], fill=T.BG2)
    for i,c in enumerate([(255,95,86),(255,189,46),(39,201,63)]):
        d.ellipse([tb[0]+28+i*34, tb[1]+20, tb[0]+28+i*34+18, tb[1]+38], fill=c)
    text_c(d, (tb[0]+tb[2])//2, tb[1]+28, "run-demo-live.sh", font("mono", 24), fill=T.MUTE)
    # terminal content
    tf = font("mono", 30)
    lines = [
        ("$ ./run-demo-live.sh", T.INK),
        ("[1/4] fetch spans + fetch user.sessions  → live DQL …", T.GREEN_HI),
        ("      root traces ≈ 321k · browser 99% · buyer 1% · samplingRatio 1.0", T.MUTE),
        ("      fetch user.events … 18,773 sessions → 16 ordered journeys   ← the wall came down", T.GREEN_HI),
        ("      model sized from spans + user.sessions · user.events = bonus (degrade-safe)", T.FAINT),
        ("      G0 gate … 12/12  ✓", T.GREEN),
        ("", T.INK),
        ("[gate] approve model revision <hash>?  (human)  ▸ y", T.RED),
        ("[2/4] model → k6     ramping-arrival-rate · synthetic=true     V2a ✓", T.GREEN_HI),
        ("[3/4] model → JMeter Concurrency TG · Shaping Timer · CSV      J1–J7 ✓", T.GREEN_HI),
        ("[4/4] diff: same journeys · weights · arrival envelope · 2 engines ▆", T.INK),
    ]
    yy = tb[1]+100
    for s, col in lines:
        text_l(d, (tb[0]+40, yy), s, tf, fill=col)
        yy += 48
    if not exemplar:
        text_c(d, W//2, H-110, "MASTER · demo · terminal chrome · green-on-black · LIVE badge · live user.events + gate highlighted",
               font("mono", 24), fill=T.FAINT)
    chrome(d, ("§3 · the demo" if exemplar else "master · demo"), 15 if exemplar else 0)
    name = "slide-15-demo" if exemplar else "master-demo"
    save(img, os.path.join(OUT, f"{name}.png")); print(f"  wrote {name}")

def master_discussion(exemplar=False):
    img, d = slide_bg(rain=True, rain_density=0.5, rain_seed=21, rain_region=(W-320, 0, W, H))
    d.rectangle([0, 0, W, 6], fill=T.GREEN)
    text_l(d, (90, 150), "💬  DISCUSSION", font("mono", 30, bold=True), fill=T.RED)
    if exemplar:
        q = "Do you trust sampled traces to size a load test?"
        text_l(d, (90, 150), "💬  DISCUSSION #2", font("mono", 30, bold=True), fill=T.RED)
        yy = 470
        for ln in wrap(d, q, font("sans", 92, bold=True), W-200):
            text_l(d, (90, yy), ln, font("sans", 92, bold=True), fill=T.INK); yy += 112
        text_l(d, (90, yy+40), "Astroshop: RUM 25.94/s  vs  spans 33.03/s  →  ×1.27  (RUM saw 79%)",
               font("mono", 38), fill=T.GREEN_HI)
        text_l(d, (90, yy+100), "size off RUM alone → under-load by 21%, call it a pass",
               font("mono", 36), fill=T.AMBER)
        text_l(d, (90, H-210), "> _", font("mono", 60, bold=True), fill=T.GREEN)
        chrome(d, "§ · discussion #2", 10)
        save(img, os.path.join(OUT, "slide-10-discussion.png")); print("  wrote slide-10-discussion")
    else:
        yy = 520
        for ln in wrap(d, "Where do your numbers come from?", font("sans", 100, bold=True), W-200):
            text_l(d, (90, yy), ln, font("sans", 100, bold=True), fill=T.INK); yy += 120
        text_l(d, (90, yy+30), "(a prompt for the room — not bullets to read)", font("sans", 40, italic=True), fill=T.MUTE)
        text_l(d, (90, H-230), "> _", font("mono", 64, bold=True), fill=T.GREEN)
        text_c(d, W//2, H-110, "MASTER · discussion · near-empty · one big question · blinking cursor",
               font("mono", 24), fill=T.FAINT)
        chrome(d, "master · discussion", 0)
        save(img, os.path.join(OUT, "master-discussion.png")); print("  wrote master-discussion")

if __name__ == "__main__":
    print("generating system + masters ->", OUT)
    visual_system()
    master_title(); master_section(); master_content(); master_demo(); master_discussion()
    # exemplars
    master_title(exemplar=True)
    master_content(exemplar="bluepill")
    master_content(exemplar="dual")
    master_content(exemplar="loop")
    master_demo(exemplar=True)
    master_discussion(exemplar=True)
    print("done.")
