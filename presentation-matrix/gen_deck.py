#!/usr/bin/env python3
"""
gen_deck.py — the FINAL 21-slide PAC deck (ISI-5794 assembly).

Composes workstream A's approved Part-4 copy (narrative-and-slide-copy.md rev4)
onto workstream B's board-accepted Matrix visual system (mtx_theme + the d1-d5
diagrams), slide-by-slide, at 2560x1440 (16:9). One reproducible source of truth
for every slide in the deck.

Honesty flags carried into the visuals (DESIGN-SYSTEM.md §5 — do NOT remove):
  * slide 6 is the ONLY glitch-treatment slide (the sampling trap).
  * slide 10 owns the x1.27 *coverage* reveal (spans un-sampled, ratio 1.0) —
    kept distinct from the sampling trap.
  * slide 13 (d5): logs leg DASHED (empty on this tenant); user.events edge SOLID
    (live, scope granted ISI-5719). Baked into the d5 diagram already.
  * G1: QR / repo links on slides 13 + 21 are REAL (public mirror ISI-5659 is live
    — verified HTTP 200). Scannable, via qr_util/segno.

Run:  python3 gen_diagrams.py && python3 gen_system.py && python3 gen_deck.py
Out:  images/slide-01-title.png … images/slide-21-close.png   (overwrites exemplars)
"""
import os, math, random
import mtx_theme as T
from mtx_theme import (font, text_c, text_l, text_r, measure, wrap, panel, chip,
                       rrect, arrow, dashed_line, pill, lock, badge)
from gen_system import slide_bg, chrome, kicker_title, bullet, fit_place, W, H, OUT
from qr_util import draw_qr, REPO_URL
from PIL import Image, ImageDraw, ImageFilter

TOTAL = 21

# ---------------------------------------------------------------- small helpers
def _d(img):
    return ImageDraw.Draw(img)

def save_slide(img, name):
    img.convert("RGBA").save(os.path.join(OUT, name), "PNG")
    print(f"  wrote {name}")

def footer_note(d, s, fill=T.FAINT):
    text_l(d, (90, H-108), s, font("mono", 22), fill=fill)

def arrival_curves(d, box, flat_col=T.BLUE, real_col=T.RED):
    """two overlaid arrival curves: flat synthetic ramp vs jagged real traffic."""
    x0, y0, x1, y1 = box
    base = y1 - 70
    top = y0 + 70
    # flat synthetic ramp
    pts = []
    for i in range(70):
        xx = x0 + 40 + i * ((x1 - x0 - 80) / 69)
        yy = base - (i / 69) * (base - top) * 0.78
        pts.append((xx, yy))
    d.line(pts, fill=flat_col, width=5)
    # jagged real curve (seeded, deterministic)
    rr = random.Random(4)
    pts = []
    for i in range(90):
        xx = x0 + 40 + i * ((x1 - x0 - 80) / 89)
        yy = base - (base - top) * 0.55 - 90 * math.sin(i / 6.5) - (i / 89) * 40 + rr.randint(-42, 42)
        pts.append((xx, yy))
    d.line(pts, fill=real_col, width=5)

def glitch_text(img, xy, s, fnt, fill=T.INK, shift=6):
    """RGB-split glitch — RESERVED for slide 6 only."""
    d = _d(img)
    text_l(d, (xy[0] - shift, xy[1]), s, fnt, fill=(255, 77, 94, 150))   # red ghost
    text_l(d, (xy[0] + shift, xy[1]), s, fnt, fill=(92, 141, 239, 150))  # blue ghost
    text_l(d, xy, s, fnt, fill=fill)

def card(d, box, title, body_lines, accent=T.GREEN, tag=None):
    x0, y0, x1, y1 = box
    panel(d, box, fill=T.BG1, outline=T.LINE2)
    d.rectangle([x0, y0, x1, y0 + 6], fill=accent)  # top rail
    yy = y0 + 34
    if tag:
        badge(d, (x0 + 28, yy), tag, font("mono", 22, bold=True), fg=accent)
        yy += 56
    text_l(d, (x0 + 28, yy), title, font("sans", 36, bold=True), fill=T.INK)
    yy += 58
    for ln in body_lines:
        for wl in wrap(d, ln, font("sans", 30), x1 - x0 - 56):
            text_l(d, (x0 + 28, yy), wl, font("sans", 30), fill=T.MUTE)
            yy += 42
        yy += 6

def terminal(d, box, lines, title="run-demo-live.sh"):
    x0, y0, x1, y1 = box
    panel(d, box, fill=(6, 9, 7), outline=T.LINE2, width=2, radius=16)
    d.rounded_rectangle([x0, y0, x1, y0 + 54], radius=16, fill=T.BG2)
    d.rectangle([x0, y0 + 38, x1, y0 + 54], fill=T.BG2)
    for i, c in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        d.ellipse([x0 + 26 + i * 32, y0 + 18, x0 + 26 + i * 32 + 17, y0 + 35], fill=c)
    text_c(d, (x0 + x1) // 2, y0 + 26, title, font("mono", 22), fill=T.MUTE)
    tf = font("mono", 29)
    yy = y0 + 92
    for s, col in lines:
        text_l(d, (x0 + 36, yy), s, tf, fill=col)
        yy += 46
    return yy

def quote_caption(d, x, y, s, fill=T.GREEN_HI):
    text_l(d, (x, y), s, font("sans", 34, italic=True), fill=fill)

def discussion_tag(d, xy, label):
    """Red speech-bubble chip + label (DejaVu has no emoji glyph, so '💬' tofu's —
    we draw the bubble instead)."""
    x, y = xy
    d.rounded_rectangle([x, y + 2, x + 38, y + 32], radius=9, fill=T.RED)
    d.polygon([(x + 9, y + 32), (x + 9, y + 44), (x + 23, y + 32)], fill=T.RED)
    text_l(d, (x + 58, y), label, font("mono", 30, bold=True), fill=T.RED)

# ---------------------------------------------------------------- diagram slides
def diagram_slide(num, section, diagram, qr=False):
    # No rain: the d1-d5 PNGs are transparent + busy, so rain bleeds through the
    # gaps and collides with diagram content/labels. Diagrams are self-contained.
    img, d = slide_bg(rain=False)
    fit_place(img, os.path.join(OUT, diagram), [70, 40, W - 70, H - 120], pad=0)
    d = _d(img)
    d.rectangle([0, 0, W, 6], fill=T.GREEN)
    # NOTE: slide 13 does NOT overlay a QR here — the d5-stack diagram already carries a
    # real, scannable repo QR baked in (bottom-right), regenerated once the mirror went live.
    chrome(d, section, num)
    return img, d

# ================================================================ SLIDES
def s01_title():
    img, _ = slide_bg(rain=True, rain_density=0.5, rain_seed=11)
    band = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    _d(band).rectangle([0, 430, W, 1010], fill=(7, 10, 8, 150))
    img.alpha_composite(band)
    d = _d(img)
    d.rectangle([0, 0, W, 6], fill=T.GREEN)
    text_c(d, W // 2, 560, "There is no spoon", font("sans", 150, bold=True), fill=T.WHITE)
    text_c(d, W // 2, 700, "Load-testing the real world", font("sans", 56), fill=T.GREEN_HI)
    text_c(d, W // 2, 810, "Henrik Rexed · IsItObservable · PAC 2026", font("mono", 38), fill=T.MUTE)
    pill(d, (W // 2 - 70, 920), 110, 56, T.RED, fnt=None)
    pill(d, (W // 2 + 70, 920), 110, 56, T.BLUE, fnt=None)
    text_c(d, W // 2, 1000, "take the red pill — stop guessing, load the real world",
           font("sans", 30, italic=True), fill=T.FAINT)
    chrome(d, "title", 1)
    save_slide(img, "slide-01-title.png")

def s02_bluepill():
    img, d = slide_bg(rain=True, rain_density=0.14, rain_seed=9, rain_region=(W - 420, 0, W, H))
    kicker_title(d, "SLIDE 2 · THE CHOICE EVERY ENGINEER MAKES", "The blue pill load test", y=120, tsize=84)
    y = 430
    y = bullet(d, 100, y, "Blue pill: run the test you always run. Dashboard green. Believe what you want.",
               font("sans", 40), max_w=1200, mark=T.BLUE)
    y = bullet(d, 100, y + 18, "Red pill: look at what production actually does.",
               font("sans", 40), max_w=1200, mark=T.RED)
    y = bullet(d, 100, y + 18, "“…how deep the rabbit hole goes.”",
               font("sans", 40), fill=T.GREEN_HI, max_w=1200, mark=T.GREEN)
    y = bullet(d, 100, y + 18, "This talk is the red pill.",
               font("sans", 44, bold=True), max_w=1200, mark=T.RED)
    vb = [1500, 400, W - 90, 1120]
    panel(d, vb, fill=T.BG1, outline=T.LINE2)
    midx = (vb[0] + vb[2]) // 2
    d.line([midx, vb[1] + 40, midx, vb[3] - 40], fill=T.LINE2, width=2)
    text_c(d, (vb[0] + midx) // 2, vb[1] + 50, "BLUE PILL", font("mono", 26, bold=True), fill=T.BLUE)
    text_c(d, (midx + vb[2]) // 2, vb[1] + 50, "RED PILL", font("mono", 26, bold=True), fill=T.RED)
    # blue = flat ramp + green-check; red = jagged
    arrival_curves(d, [vb[0] + 20, vb[1] + 90, midx - 20, vb[3] - 110], flat_col=T.BLUE, real_col=T.BG1)
    text_c(d, (vb[0] + midx) // 2, vb[3] - 70, "flat synthetic ramp ✓", font("mono", 22), fill=T.FAINT)
    arrival_curves(d, [midx + 20, vb[1] + 90, vb[2] - 20, vb[3] - 110], flat_col=T.BG1, real_col=T.RED)
    text_c(d, (midx + vb[2]) // 2, vb[3] - 70, "jagged real traffic", font("mono", 22), fill=T.FAINT)
    chrome(d, "§ · the choice", 2)
    save_slide(img, "slide-02-bluepill.png")

def s03_basics():
    img, d = slide_bg(rain=True, rain_density=0.14, rain_seed=9, rain_region=(W - 420, 0, W, H))
    kicker_title(d, "SLIDE 3 · WHERE WE AGREE", "A load test must reflect real life", y=120, tsize=80)
    y = 430
    for s in ["Volume — “10× peak”? peak of what?",
              "Mix — 3 endpoints vs 40 in prod",
              "Pacing — thread-group defaults",
              "Payloads — 3 hardcoded blobs"]:
        y = bullet(d, 100, y, s, font("sans", 40), max_w=1200, mark=T.BLUE)
        y += 14
    y = bullet(d, 100, y + 10, "Shape mismatch = the test tests your imagination",
               font("sans", 42, bold=True), max_w=1200, mark=T.RED)
    # right: two arrival curves + four "source: ???" chips
    vb = [1500, 400, W - 90, 820]
    panel(d, vb, fill=T.BG1, outline=T.LINE2)
    text_c(d, (vb[0] + vb[2]) // 2, vb[1] + 34, "same average, different reality", font("mono", 24), fill=T.MUTE)
    arrival_curves(d, [vb[0] + 20, vb[1] + 70, vb[2] - 20, vb[3] - 20])
    text_l(d, (vb[0] + 36, vb[3] - 56), "— flat synthetic", font("mono", 22), fill=T.BLUE)
    text_r(d, vb[2] - 36, vb[3] - 56, "jagged production —", font("mono", 22), fill=T.RED)
    cy = 880
    labels = ["Volume", "Mix", "Pacing", "Payloads"]
    cw = (W - 90 - 1500 - 3 * 24) // 4
    for i, lab in enumerate(labels):
        cx = 1500 + i * (cw + 24)
        chip(d, [cx, cy, cx + cw, cy + 180])
        text_c(d, cx + cw // 2, cy + 56, lab, font("sans", 30, bold=True), fill=T.INK)
        text_c(d, cx + cw // 2, cy + 120, "source: ???", font("mono", 24, bold=True), fill=T.AMBER)
    chrome(d, "§ · the basics", 3)
    save_slide(img, "slide-03-basics.png")

def s04_discussion1():
    img, d = slide_bg(rain=True, rain_density=0.5, rain_seed=21, rain_region=(W - 320, 0, W, H))
    discussion_tag(d, (90, 148), "DISCUSSION #1")
    yy = 500
    for ln in wrap(d, "Where do your numbers come from?", font("sans", 100, bold=True), W - 240):
        text_l(d, (90, yy), ln, font("sans", 100, bold=True), fill=T.INK); yy += 122
    text_l(d, (90, yy + 30), "Who chose your RPS — and what was it based on?",
           font("sans", 40, italic=True), fill=T.MUTE)
    text_l(d, (90, H - 230), "> _", font("mono", 64, bold=True), fill=T.GREEN)
    chrome(d, "§ · discussion #1", 4)
    save_slide(img, "slide-04-discussion.png")

def s05_otel():
    img, d = slide_bg(rain=True, rain_density=0.14, rain_seed=9, rain_region=(W - 420, 0, W, H))
    kicker_title(d, "SLIDE 5 · THE RED PILL EXISTS NOW", "The evolution with OTel", y=120, tsize=84)
    y = 440
    for s, m in [("Metrics — the what", T.MUTE),
                 ("Traces — the why + the path", T.GREEN),
                 ("Logs — the detail", T.MUTE)]:
        y = bullet(d, 100, y, s, font("sans", 40), max_w=1180, mark=m); y += 14
    y = bullet(d, 100, y + 12, "For load tests, traces = journeys + fan-out + arrival curve",
               font("sans", 40), max_w=1180, mark=T.GREEN)
    y = bullet(d, 100, y + 18, "But the red pill shows reality through a sample",
               font("sans", 40, bold=True), fill=T.AMBER, max_w=1180, mark=T.AMBER)
    # right: three correlated-signal panels, traces highlighted
    vb = [1500, 400, W - 90, 1120]
    labels = [("METRICS", "the what", T.LINE2),
              ("TRACES", "the why + the path", T.GREEN),
              ("LOGS", "the detail", T.LINE2)]
    ph = (vb[3] - vb[1] - 2 * 30) // 3
    for i, (lab, sub, ac) in enumerate(labels):
        py = vb[1] + i * (ph + 30)
        panel(d, [vb[0], py, vb[2], py + ph], fill=T.BG1, outline=ac, width=3 if ac == T.GREEN else 2)
        d.rectangle([vb[0], py, vb[0] + 8, py + ph], fill=ac)
        text_l(d, (vb[0] + 36, py + 34), lab, font("mono", 34, bold=True),
               fill=(T.GREEN if ac == T.GREEN else T.INK))
        text_l(d, (vb[0] + 36, py + 86), sub, font("sans", 30), fill=T.MUTE)
    chrome(d, "§ · OTel", 5)
    save_slide(img, "slide-05-otel.png")

def s06_sampling():
    img, d = slide_bg(rain=True, rain_density=0.18, rain_seed=6, rain_region=(W - 420, 0, W, H))
    # kicker + GLITCH title (the ONLY glitch slide)
    text_l(d, (90, 120), "SLIDE 6 · THE GLITCH IN THE MATRIX", font("mono", 28, bold=True), fill=T.AMBER)
    glitch_text(img, (90, 164), "The sampling trap", font("sans", 84, bold=True), fill=T.INK, shift=6)
    d = _d(img)
    y = 440
    for s, m, col in [("Déjà vu = a glitch in the Matrix", T.AMBER, T.AMBER),
                      ("Naive: count × 1/rate — only valid for head sampling", T.INK, T.INK),
                      ("Head: adjusted count = 1 / probability (OTel spec)", T.GREEN, T.INK),
                      ("Tail: reweighting thrown away — you cannot extrapolate counts", T.RED, T.INK),
                      ("Fix: compare rates, normalize each dataset's ratio", T.GREEN, T.GREEN_HI)]:
        y = bullet(d, 100, y, s, font("sans", 38), fill=col, max_w=1180, mark=m); y += 16
    # right: head vs tail split
    vb = [1500, 400, W - 90, 1060]
    midy = (vb[1] + vb[3]) // 2
    panel(d, [vb[0], vb[1], vb[2], midy - 12], fill=T.BG1, outline=T.GREEN, width=3)
    text_l(d, (vb[0] + 30, vb[1] + 26), "HEAD SAMPLING", font("mono", 28, bold=True), fill=T.GREEN)
    text_l(d, (vb[0] + 30, vb[1] + 74), "decision up front · probability propagated", font("sans", 28), fill=T.MUTE)
    text_l(d, (vb[0] + 30, vb[1] + 126), "✓ clean reweight — counts recoverable", font("sans", 30, bold=True), fill=T.GREEN_HI)
    panel(d, [vb[0], midy + 12, vb[2], vb[3]], fill=T.BG1, outline=T.RED, width=3)
    text_l(d, (vb[0] + 30, midy + 38), "TAIL SAMPLING", font("mono", 28, bold=True), fill=T.RED)
    text_l(d, (vb[0] + 30, midy + 86), "decision after the trace · outcome-biased", font("sans", 28), fill=T.MUTE)
    text_l(d, (vb[0] + 30, midy + 138), "✗ cannot recover counts/rates", font("sans", 30, bold=True), fill=T.RED)
    footer_note(d, "samplingFactor recorded in shape-diff.json", fill=T.FAINT)
    chrome(d, "§ · the sampling trap", 6)
    save_slide(img, "slide-06-sampling.png")

def s07_rum():
    img, d = slide_bg(rain=True, rain_density=0.14, rain_seed=9, rain_region=(W - 420, 0, W, H))
    kicker_title(d, "SLIDE 7 · THE EDGE TRUTH", "State of RUM", y=120, tsize=84)
    y = 440
    y = bullet(d, 100, y, "RUM = real journeys, real arrival curve, real device/geo/network",
               font("sans", 38), max_w=1180, mark=T.GREEN); y += 16
    y = bullet(d, 100, y, "Google ranks on field CrUX @ 75th pct — not Lighthouse (lab)",
               font("sans", 38), max_w=1180, mark=T.GREEN); y += 16
    y = bullet(d, 100, y, "OTel browser SDK + session semconv = Development, not stable",
               font("sans", 38), fill=T.AMBER, max_w=1180, mark=T.AMBER); y += 16
    y = bullet(d, 100, y, "Vendor OTel-RUM = technical preview",
               font("sans", 38), max_w=1180, mark=T.AMBER); y += 16
    y = bullet(d, 100, y, "Production RUM truth today = your backend's user.sessions",
               font("sans", 38, bold=True), max_w=1180, mark=T.GREEN)
    # right: lab vs field split
    vb = [1500, 400, W - 90, 1060]
    midx = (vb[0] + vb[2]) // 2
    panel(d, [vb[0], vb[1], midx - 12, vb[3]], fill=T.BG1, outline=T.LINE2)
    text_c(d, (vb[0] + midx) // 2, vb[1] + 34, "LAB (Lighthouse)", font("mono", 24, bold=True), fill=T.BLUE)
    # gauge
    gcx, gcy = (vb[0] + midx) // 2, (vb[1] + vb[3]) // 2
    d.arc([gcx - 120, gcy - 120, gcx + 120, gcy + 120], start=135, end=405, fill=T.LINE2, width=18)
    d.arc([gcx - 120, gcy - 120, gcx + 120, gcy + 120], start=135, end=320, fill=T.BLUE, width=18)
    text_c(d, gcx, gcy, "synthetic", font("mono", 22), fill=T.FAINT)
    panel(d, [midx + 12, vb[1], vb[2], vb[3]], fill=T.BG1, outline=T.GREEN, width=3)
    text_c(d, (midx + vb[2]) // 2, vb[1] + 34, "FIELD (CrUX p75)", font("mono", 24, bold=True), fill=T.GREEN)
    # histogram
    rr = random.Random(7)
    hx0, hx1 = midx + 48, vb[2] - 48
    bw = (hx1 - hx0) // 10
    for i in range(10):
        bh = 60 + rr.randint(40, 230)
        bx = hx0 + i * bw
        d.rectangle([bx, vb[3] - 80 - bh, bx + bw - 10, vb[3] - 80], fill=T.GREEN if i in (6, 7) else T.GREEN_DIM)
    text_c(d, (midx + vb[2]) // 2, vb[3] - 48, "real sessions", font("mono", 22), fill=T.FAINT)
    badge(d, (vb[0] + 30, vb[3] - 46), "OTel browser = Development", font("mono", 20, bold=True), fg=T.AMBER)
    chrome(d, "§ · state of RUM", 7)
    save_slide(img, "slide-07-rum.png")

def s08_dual():
    img, d = diagram_slide(8, "§ · where truth lives", "d3-dual-source.png")
    save_slide(img, "slide-08-dual.png")

def s09_dql():
    img, d = slide_bg(rain=False)
    d.rectangle([0, 0, W, 6], fill=T.GREEN)
    kicker_title(d, "SLIDE 9 · ONE LANGUAGE, BOTH WORLDS", "DQL: querying both worlds", y=96, tsize=72)
    tb = [120, 320, W - 120, 1020]
    lines = [
        ("# service-side shape", T.FAINT),
        ("> fetch spans | summarize spans=count(), by:{service.name}", T.GREEN_HI),
        ("", T.INK),
        ("# the real session population  —  live, accessible now", T.FAINT),
        ("> fetch user.sessions | summarize sessions=count()", T.GREEN_HI),
        ("    35,679 sessions / 24h · 5 apps (web + mobile)        ● LIVE", T.GREEN),
        ("", T.INK),
        ("# the ordered journey + exact think-times", T.FAINT),
        ("> fetch user.events | filter dt.rum.session.id == <id> | sort timestamp asc", T.GREEN_HI),
        ("    scope granted (ISI-5719) → returns rows                ● LIVE", T.GREEN),
        ("    18,773 sessions → 16 ordered journey templates", T.MUTE),
    ]
    terminal(d, tb, lines, title="dtctl · DQL")
    footer_note(d, "volume merge + the ×1.27 factor need only user.sessions + spans — user.events is the bonus (degrade-safe)")
    chrome(d, "§ · DQL", 9)
    save_slide(img, "slide-09-dql.png")

def s10_discussion2():
    img, d = slide_bg(rain=True, rain_density=0.28, rain_seed=21, rain_region=(W - 200, 0, W, H))
    discussion_tag(d, (90, 148), "DISCUSSION #2")
    q = "Do you trust a single source to size a load test?"
    yy = 430
    for ln in wrap(d, q, font("sans", 86, bold=True), W - 420):
        text_l(d, (90, yy), ln, font("sans", 86, bold=True), fill=T.INK); yy += 104
    # the x1.27 reveal — two bars
    by = yy + 70
    bx0 = 90
    maxw = 1500
    # RUM bar (79%)
    d.rectangle([bx0, by, bx0 + int(maxw * 0.79), by + 70], fill=T.GREEN_DIM)
    text_l(d, (bx0 + 20, by + 18), "RUM  user.sessions   25.94 req/s", font("mono", 32, bold=True), fill=T.INK)
    # spans bar (100%)
    d.rectangle([bx0, by + 100, bx0 + maxw, by + 170], fill=T.GREEN)
    text_l(d, (bx0 + 20, by + 118), "spans  (un-sampled, ratio 1.0)   33.03 req/s", font("mono", 32, bold=True), fill=T.BG0)
    # x1.27 bridge
    text_l(d, (bx0 + maxw + 40, by + 44), "×1.27", font("sans", 72, bold=True), fill=T.RED)
    text_l(d, (bx0 + maxw + 40, by + 128), "coverage gap — not sampling", font("mono", 24), fill=T.AMBER)
    text_l(d, (90, by + 220), "Size off one source → under-load by 21%, call it a pass.",
           font("sans", 38, bold=True), fill=T.INK)
    text_l(d, (90, by + 278), "Reconcile sources, record the factor. Same cure as sampling — different disease.",
           font("sans", 32), fill=T.MUTE)
    text_l(d, (90, H - 150), "> _", font("mono", 52, bold=True), fill=T.GREEN)
    chrome(d, "§ · discussion #2", 10)
    save_slide(img, "slide-10-discussion.png")

def s11_skill():
    img, d = slide_bg(rain=True, rain_density=0.14, rain_seed=9, rain_region=(W - 420, 0, W, H))
    kicker_title(d, "SLIDE 11 · MAKE IT REPEATABLE", "Let's use a skill", y=120, tsize=84)
    y = 450
    y = bullet(d, 100, y, "A skill = versioned, deterministic capability", font("sans", 40), max_w=1180); y += 16
    y = bullet(d, 100, y, "Reads telemetry → proposes a workload model", font("sans", 40), max_w=1180); y += 16
    y = bullet(d, 100, y, "Inside a scope contract: read-only inputs, hard caps, human gate",
               font("sans", 40), max_w=1180); y += 16
    y = bullet(d, 100, y, "The agent proposes; it does not decide",
               font("sans", 46, bold=True), fill=T.RED, max_w=1180, mark=T.RED)
    # right: scope-contract card
    vb = [1500, 400, W - 90, 1120]
    panel(d, vb, fill=T.BG1, outline=T.LINE2)
    d.rectangle([vb[0], vb[1], vb[2], vb[1] + 6], fill=T.GREEN)
    text_c(d, (vb[0] + vb[2]) // 2, vb[1] + 44, "SCOPE CONTRACT", font("mono", 30, bold=True), fill=T.GREEN)
    rows = [("inputs", "read-only telemetry", T.GREEN),
            ("boundaries", "hard caps · non-prod", T.AMBER),
            ("gate", "human approval (V1)", T.RED)]
    ry = vb[1] + 120
    for lab, val, ac in rows:
        chip(d, [vb[0] + 40, ry, vb[2] - 40, ry + 120])
        text_l(d, (vb[0] + 70, ry + 22), lab, font("mono", 26, bold=True), fill=ac)
        text_l(d, (vb[0] + 70, ry + 66), val, font("sans", 30), fill=T.INK)
        ry += 150
    lock(d, (vb[0] + 70, ry + 20), size=44, color=T.RED)
    text_l(d, (vb[0] + 120, ry), "agent executes · human decides", font("sans", 30, bold=True), fill=T.INK)
    chrome(d, "§ · the skill", 11)
    save_slide(img, "slide-11-skill.png")

def s12_engine():
    img, d = diagram_slide(12, "§ · the engine", "d2-construct.png")
    save_slide(img, "slide-12-engine.png")

def s13_architecture():
    # d5-stack carries the real repo QR baked in (bottom-right) — no overlay needed (G1).
    img, d = diagram_slide(13, "§ · architecture", "d5-stack.png", qr=False)
    save_slide(img, "slide-13-architecture.png")

def s14_worlds():
    img, d = diagram_slide(14, "§ · many worlds", "d4-many-worlds.png")
    save_slide(img, "slide-14-worlds.png")

def demo_slide(num, kicker, title, lines, caption, highlight=None, fallback=True):
    img, d = slide_bg(rain=False)
    d.rectangle([0, 0, W, 6], fill=T.GREEN)
    kicker_title(d, kicker, title, y=90, tsize=66)
    badge(d, (W - 470, 110), "● LIVE — DQL vs Astroshop", font("mono", 24, bold=True), fg=T.RED)
    tb = [120, 300, W - 120, 1020]
    terminal(d, tb, lines)
    if caption:
        quote_caption(d, 140, 1050, caption)
    if fallback:
        footer_note(d, "fallback: run-demo.sh (rehearsed recorded run — narrate identically, say once it's the recording)")
    chrome(d, "§ · the demo", num)
    return img

def s15_demo():
    lines = [
        ("$ ./run-demo-live.sh", T.INK),
        ("", T.INK),
        ("[1/4] fetch spans            → service shape (live DQL)", T.GREEN_HI),
        ("      root traces ≈ 321k · browser 99% · buyer 1%", T.MUTE),
        ("[1/4] fetch user.sessions    → real journeys (live)", T.GREEN_HI),
        ("      samplingRatio 1.0   (this tenant is un-sampled)", T.MUTE),
        ("", T.INK),
        ("      G0 gate … 12 / 12  ✓    ← re-derived live, not constants", T.GREEN),
        ("", T.INK),
        ("      no pre-baked model — materialized from what it sees now", T.FAINT),
    ]
    img = demo_slide(15, "SLIDE 15 · STEP 1 — TELEMETRY → MODEL", "Load the program — LIVE",
                     lines, "“I know kung fu.”")
    save_slide(img, "slide-15-demo.png")

def s16_demo_wall():
    lines = [
        ("      fetch user.events …", T.INK),
        ("        403 not authorized          (until this week — storage scope)", T.FAINT),
        ("        ↳ scope granted (ISI-5719)  → returns rows  ← the wall came down", T.GREEN),
        ("        18,773 sessions → 16 ordered journey templates + think-times", T.GREEN_HI),
        ("", T.INK),
        ("      note: model sized from spans + user.sessions", T.MUTE),
        ("            user.events = bonus · degrades cleanly if ever gone", T.FAINT),
        ("", T.INK),
        ("[gate] approve model revision <hash>?  (human)  ▸ y", T.RED),
        ("       the engine will not synthesize a request until I approve", T.MUTE),
    ]
    img = demo_slide(16, "SLIDE 16 · THE WALL CAME DOWN + THE V1 GATE", "user.events returns rows — then the Oracle",
                     lines, "Trust the trace, not the demo.")
    # lock on the gate line
    save_slide(img, "slide-16-demo-wall.png")

def s17_demo_render():
    lines = [
        ("[2/4] model → k6", T.GREEN_HI),
        ("      ramping-arrival-rate · stages scaled off weights", T.MUTE),
        ("      synthetic=true in baggage on every request", T.MUTE),
        ("      V2a checks … ✓", T.GREEN),
        ("", T.INK),
        ("[3/4] model → JMeter", T.GREEN_HI),
        ("      Concurrency Thread Group · Throughput Shaping Timer", T.MUTE),
        ("      CSV data sets (cache-busting)", T.MUTE),
        ("      J1–J7 static checks … ✓", T.GREEN),
    ]
    img = demo_slide(17, "SLIDE 17 · STEP 2–3 — ONE MODEL → TWO TOOLS", "Render k6 · JMeter",
                     lines, "“Show me.”  One approved model → two guns, zero hand-authoring.")
    save_slide(img, "slide-17-demo-render.png")

def s18_demo_diff():
    img, d = slide_bg(rain=False)
    d.rectangle([0, 0, W, 6], fill=T.GREEN)
    kicker_title(d, "SLIDE 18 · STEP 4 — DIFF: SAME SHAPE, TWO ENGINES", "Guns. Lots of guns.", y=90, tsize=66)
    badge(d, (W - 470, 110), "● LIVE — DQL vs Astroshop", font("mono", 24, bold=True), fg=T.RED)
    rows = ["journeys", "weights", "arrival envelope", "synthetic baggage"]
    vb = [160, 330, W - 160, 940]
    panel(d, vb, fill=T.BG1, outline=T.LINE2)
    cols = [vb[0] + 520, vb[0] + 900, vb[0] + 1280]
    text_l(d, (vb[0] + 40, vb[1] + 34), "property", font("mono", 28, bold=True), fill=T.MUTE)
    text_c(d, cols[0], vb[1] + 48, "k6", font("mono", 30, bold=True), fill=T.GREEN)
    text_c(d, cols[1], vb[1] + 48, "JMeter", font("mono", 30, bold=True), fill=T.GREEN)
    text_c(d, cols[2], vb[1] + 48, "match", font("mono", 30, bold=True), fill=T.GREEN)
    ry = vb[1] + 120
    for r in rows:
        d.line([vb[0] + 40, ry - 12, vb[2] - 40, ry - 12], fill=T.LINE, width=2)
        text_l(d, (vb[0] + 40, ry + 10), r, font("sans", 34), fill=T.INK)
        text_c(d, cols[0], ry + 26, "●", font("sans", 30), fill=T.GREEN)
        text_c(d, cols[1], ry + 26, "●", font("sans", 30), fill=T.GREEN)
        text_c(d, cols[2], ry + 26, "✓", font("sans", 34, bold=True), fill=T.GREEN_HI)
        ry += 118
    quote_caption(d, 160, 980, "The model is the program; the renderer is just the compiler back-end.")
    footer_note(d, "fallback: run-demo.sh (recorded) — if time is short, narrate steps 1, 2, 4 and drop JMeter detail")
    chrome(d, "§ · the demo", 18)
    save_slide(img, "slide-18-demo-diff.png")

def s19_loop():
    img, d = diagram_slide(19, "§ · the loop", "d1-loop.png")
    save_slide(img, "slide-19-loop.png")

def s20_limits():
    img, d = slide_bg(rain=True, rain_density=0.14, rain_seed=9, rain_region=(W - 420, 0, W, H))
    kicker_title(d, "SLIDE 20 · THE CAVEATS AN EXPERT ROOM DESERVES",
                 "Honest limits: glitches in the Matrix", y=110, tsize=72)
    cards = [
        ("R5", "Circular ground truth", ["Extract + validate from the same telemetry.",
                                         "Cross-check ≥1 run against infra metrics."], T.AMBER),
        ("R2", "Mean ≠ peak", ["We model mean arrival today.",
                               "A peak-envelope profile is on the backlog."], T.AMBER),
        ("RUM", "Ordered journeys", ["storage:user.events:read now granted (ISI-5719).",
                                     "Folding them into the rendered model is next."], T.GREEN),
    ]
    cw = (W - 180 - 2 * 40) // 3
    cx = 90
    for tag, title, body, ac in cards:
        card(d, [cx, 420, cx + cw, 980], title, body, accent=ac, tag=tag)
        cx += cw + 40
    text_c(d, W // 2, 1080, "There is no spoon — don't tune the test green; bend it to reality.",
           font("sans", 44, bold=True), fill=T.GREEN_HI)
    chrome(d, "§ · honest limits", 20)
    save_slide(img, "slide-20-limits.png")

def s21_close():
    img, _ = slide_bg(rain=True, rain_density=0.5, rain_seed=11)
    band = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    _d(band).rectangle([0, 150, W, 1180], fill=(7, 10, 8, 140))
    img.alpha_composite(band)
    d = _d(img)
    d.rectangle([0, 0, W, 6], fill=T.GREEN)
    discussion_tag(d, (90, 178), "DISCUSSION #3 + CLOSE")
    yy = 320
    for ln in wrap(d, "What would you red-pill first?", font("sans", 96, bold=True), W - 760):
        text_l(d, (90, yy), ln, font("sans", 96, bold=True), fill=T.WHITE); yy += 116
    text_l(d, (90, yy + 20), "One service you already observe — and the one number you can't justify.",
           font("sans", 38), fill=T.MUTE)
    text_l(d, (90, yy + 100), "telemetry proposes → you validate → render → run scoped → diff",
           font("mono", 32), fill=T.GREEN_HI)
    pill(d, (150, yy + 230), 150, 64, T.RED, fnt=None)
    text_l(d, (250, yy + 200), "Stop guessing. Load the real world.", font("sans", 52, bold=True), fill=T.INK)
    # repo + real QR (public mirror live — ISI-5659)
    qbox = 300
    qx, qy = W - qbox - 150, 360
    panel(d, [qx - 24, qy - 24, qx + qbox + 24, qy + qbox + 90], fill=T.BG1, outline=T.GREEN, width=2)
    draw_qr(d, (qx, qy), qbox, url=REPO_URL, dark=T.INK)
    text_c(d, qx + qbox // 2, qy + qbox + 32, "github.com/henrikrexed/", font("mono", 24), fill=T.GREEN_HI)
    text_c(d, qx + qbox // 2, qy + qbox + 62, "AI-Performance-Testing", font("mono", 24, bold=True), fill=T.GREEN_HI)
    text_l(d, (90, 1160), "It's all open — methodology · engine · renderers · this demo",
           font("sans", 30, italic=True), fill=T.FAINT)
    chrome(d, "§ · discussion #3 · close", 21)
    save_slide(img, "slide-21-close.png")

SLIDES = [s01_title, s02_bluepill, s03_basics, s04_discussion1, s05_otel, s06_sampling,
          s07_rum, s08_dual, s09_dql, s10_discussion2, s11_skill, s12_engine,
          s13_architecture, s14_worlds, s15_demo, s16_demo_wall, s17_demo_render,
          s18_demo_diff, s19_loop, s20_limits, s21_close]

if __name__ == "__main__":
    print(f"generating the {TOTAL}-slide deck -> {OUT}")
    for fn in SLIDES:
        fn()
    print("done.")
