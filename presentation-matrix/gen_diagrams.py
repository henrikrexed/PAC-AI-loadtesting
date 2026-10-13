#!/usr/bin/env python3
"""
gen_diagrams.py — the five technical-core diagram redraws for the PAC deck (ISI-5724 / B).
Each is exported as a transparent-background PNG so it drops onto any slide master, plus a
dark-baked variant for standalone review. Content validated against ISI-5722 slide copy and
ISI-5723 tech-accuracy review.

  D1  the loop          SCOPE->VALIDATE->SYNTHESIZE->EXECUTE->ANALYZE  (VALIDATE = the Oracle)
  D2  the Construct     adapter -> engine -> renderers (3-layer, deterministic)
  D3  dual-source       traces->spans ; RUM->user.sessions+user.events ; DQL ; dt.rum.session.id
  D4  many worlds       one workload-model.json -> k6 / JMeter / Locust / Gatling
  D5  the stack         Astroshop->Collector->Grail->agent/skill/engine->renderers (wired)
"""
import os, math
import mtx_theme as T
from mtx_theme import (canvas, save, font, text_c, text_l, text_r, measure, para, wrap,
                       panel, chip, rrect, arrow, elbow, dashed_line, glow_rect, code_rain,
                       pill, lock, badge, place)

OUT = os.path.join(os.path.dirname(__file__), "images")
os.makedirs(OUT, exist_ok=True)

# ---------- shared node primitive --------------------------------------------
def node(img, draw, box, title, subs=None, accent=T.GREEN, fill=T.BG2,
         glow=False, title_size=36, sub_size=24, mono_title=False, outline=None):
    if glow:
        glow_rect(img, box, accent, radius=T.RADIUS, blur=22, alpha=70)
    panel(draw, box, fill=fill, outline=(outline or T.LINE2), width=2)
    # accent top rail
    x0, y0, x1, y1 = box
    draw.rounded_rectangle([x0, y0, x1, y0 + 10], radius=5, fill=accent)
    draw.rectangle([x0, y0 + 6, x1, y0 + 11], fill=fill)  # square off bottom of rail
    tf = font("mono" if mono_title else "sans", title_size, bold=True)
    cx = (x0 + x1) // 2
    if subs:
        text_c(draw, cx, y0 + (y1 - y0) * 0.36, title, tf, fill=T.INK)
        sf = font("mono", sub_size)
        yy = y0 + (y1 - y0) * 0.58
        for s in subs:
            text_c(draw, cx, yy, s, sf, fill=T.MUTE)
            yy += int(sub_size * 1.35)
    else:
        text_c(draw, cx, (y0 + y1) // 2, title, tf, fill=T.INK)

def caption(draw, cx, y, quote, attrib=None, w=1600):
    qf = font("sans", 30, italic=True)
    af = font("mono", 22)
    lines = wrap(draw, quote, qf, w)
    for ln in lines:
        text_c(draw, cx, y, ln, qf, fill=T.GREEN_HI)
        y += 40
    if attrib:
        text_c(draw, cx, y + 4, attrib, af, fill=T.FAINT)

def title_block(draw, x, y, kicker, title, accent=T.GREEN):
    text_l(draw, (x, y), kicker, font("mono", 24, bold=True), fill=accent)
    text_l(draw, (x, y + 34), title, font("sans", 52, bold=True), fill=T.INK)

def footer(draw, w, h, s, fill=T.FAINT):
    text_c(draw, w // 2, h - 34, s, font("mono", 22), fill=fill)

def export(img, name):
    # transparent version (for slides)
    save(img, os.path.join(OUT, f"{name}.png"))
    # dark-baked review version
    base, _ = canvas(img.width, img.height, bg=T.BG0)
    base.alpha_composite(img)
    save(base, os.path.join(OUT, f"{name}--onbg.png"))
    print("  wrote", name)

# =============================================================================
# D1 — THE LOOP
# =============================================================================
def d1_loop():
    W, H = 2400, 1560
    img, d = canvas(W, H)
    title_block(d, 90, 70, "SCOPE · VALIDATE · SYNTHESIZE · EXECUTE · ANALYZE", "The loop")

    cx, cy, R = W // 2, 840, 540
    NW, NH = 360, 150
    stages = [
        ("SCOPE",      ["telemetry → model"],                 T.GREEN,  False),
        ("VALIDATE",   ["the human gate", "— the Oracle —"], T.RED, True),
        ("SYNTHESIZE", ["model → test code"],                  T.GREEN,  False),
        ("EXECUTE",    ["scoped run · synthetic=true"],        T.GREEN,  False),
        ("ANALYZE",    ["shape-diff vs prod"],                      T.GREEN,  False),
    ]
    # positions clockwise from top
    pts = []
    for i in range(5):
        a = math.radians(-90 + i * 72)
        pts.append((cx + R * math.cos(a), cy + R * math.sin(a)))

    # edges (arcs approximated by straight arrows between node edges)
    def edge_point(p_from, p_to):
        ang = math.atan2(p_to[1] - p_from[1], p_to[0] - p_from[0])
        return (p_from[0] + (NW/2 + 14) * math.cos(ang),
                p_from[1] + (NH/2 + 14) * math.sin(ang))
    for i in range(5):
        p0, p1 = pts[i], pts[(i + 1) % 5]
        a0 = edge_point(p0, p1)
        a1 = edge_point(p1, p0)
        closing = (i == 4)  # ANALYZE -> SCOPE
        arrow(d, a0, a1, color=(T.AMBER if closing else T.GREEN_DIM), width=6, head=22,
              dashed=closing)
        if closing:
            mx, my = (a0[0] + a1[0]) / 2, (a0[1] + a1[1]) / 2
            badge(d, (mx - 150, my - 18), "iterate ≤ 3 → escalate", font("mono", 22, bold=True), fg=T.AMBER)

    # nodes
    for i, (name, subs, acc, oracle) in enumerate(stages):
        x, y = pts[i]
        box = [x - NW/2, y - NH/2, x + NW/2, y + NH/2]
        node(img, d, box, name, subs=subs, accent=acc, glow=oracle,
             fill=(T.BG2 if not oracle else (26, 14, 17)), outline=(T.RED if oracle else T.LINE2))
        if oracle:
            lock(d, (x + NW/2 - 34, y - NH/2 + 2), size=40, color=T.RED)

    # center medallion
    text_c(d, cx, cy - 30, "delegate", font("sans", 34, bold=True), fill=T.MUTE)
    text_c(d, cx, cy + 10, "EXECUTION", font("mono", 40, bold=True), fill=T.GREEN)
    text_c(d, cx, cy + 54, "not judgment", font("sans", 34, bold=True), fill=T.MUTE)
    text_c(d, cx, cy + 108, "“Temet Nosce” — know thyself", font("sans", 26, italic=True), fill=T.RED)

    footer(d, W, H, "VALIDATE is hash-bound to the model revision · change a field → the gate re-opens · no auto-approval, ever")
    export(img, "d1-loop")

# =============================================================================
# D2 — THE CONSTRUCT (3-layer engine)
# =============================================================================
def d2_construct():
    W, H = 2560, 1400
    img, d = canvas(W, H)
    title_block(d, 90, 70, "ADAPTER → ENGINE → RENDERERS", "The engine: telemetry in, model out")
    caption(d, W//2, 212, "“This is the Construct. It's our loading program. We can load anything…”", "Morpheus", w=1800)

    top, bot = 320, 1210
    # three bands
    ax0, ax1 = 90, 760          # adapter
    ex0, ex1 = 900, 1660        # engine
    rx0, rx1 = 1800, 2470       # renderers

    # ENGINE as the bright "construct" void (lighter center panel)
    glow_rect(img, [ex0, top, ex1, bot], T.GREEN, radius=T.RADIUS, blur=30, alpha=46)
    panel(d, [ex0, top, ex1, bot], fill=(22, 32, 27), outline=T.GREEN, width=3)
    text_c(d, (ex0+ex1)//2, top+54, "ENGINE", font("mono", 46, bold=True), fill=T.GREEN)
    text_c(d, (ex0+ex1)//2, top+104, "backend-agnostic · deterministic · offline-testable",
           font("mono", 24), fill=T.MUTE)
    steps = ["front-end discovery",
             "scenario clustering → ~80% coverage",
             "per-scenario load — Little's Law",
             "ramp shaping",
             "dataset sizing"]
    yy = top + 170
    for s in steps:
        chip(d, [ex0+70, yy, ex1-70, yy+74], fill=T.BG1, outline=T.LINE2)
        text_c(d, (ex0+ex1)//2, yy+37, s, font("mono", 28), fill=T.INK)
        yy += 96
    text_c(d, (ex0+ex1)//2, bot-46, "same telemetry → same model, every time",
           font("sans", 26, bold=True), fill=T.GREEN_HI)

    # ADAPTER
    panel(d, [ax0, top, ax1, bot], fill=T.BG1, outline=T.LINE2, width=2)
    draw_railtop(d, [ax0, top, ax1, bot], T.BLUE)
    text_c(d, (ax0+ax1)//2, top+54, "INPUT ADAPTER", font("mono", 40, bold=True), fill=T.INK)
    text_c(d, (ax0+ax1)//2, top+104, "backend-specific", font("mono", 24), fill=T.MUTE)
    text_c(d, (ax0+ax1)//2, top+168, "raw telemetry → one neutral schema", font("sans", 24, italic=True), fill=T.MUTE)
    srcs = ["DQL  (this build)", "Tempo", "Jaeger", "Envoy logs"]
    yy = top + 240
    for i, s in enumerate(srcs):
        primary = (i == 0)
        chip(d, [ax0+70, yy, ax1-70, yy+78], fill=(T.BG3 if primary else T.BG1),
             outline=(T.BLUE if primary else T.LINE2))
        text_c(d, (ax0+ax1)//2, yy+39, s, font("mono", 28, bold=primary),
               fill=(T.INK if primary else T.MUTE))
        yy += 100

    # RENDERERS
    panel(d, [rx0, top, rx1, bot], fill=T.BG1, outline=T.LINE2, width=2)
    draw_railtop(d, [rx0, top, rx1, bot], T.AMBER)
    text_c(d, (rx0+rx1)//2, top+54, "RENDERERS", font("mono", 40, bold=True), fill=T.INK)
    text_c(d, (rx0+rx1)//2, top+104, "model → runnable world", font("mono", 24), fill=T.MUTE)
    tools = ["k6", "JMeter", "Locust", "Gatling"]
    yy = top + 200
    for s in tools:
        chip(d, [rx0+70, yy, rx1-70, yy+96], fill=T.BG2, outline=T.AMBER_DIM)
        text_l(d, (rx0+108, yy+30), s, font("mono", 34, bold=True), fill=T.INK)
        text_r(d, rx1-100, yy+40, "✓", font("sans", 40, bold=True), fill=T.GREEN)
        yy += 120

    # connectors with labels
    midy = (top + bot) // 2
    arrow(d, (ax1+18, midy), (ex0-18, midy), color=T.GREEN, width=7, head=26)
    text_c(d, (ax1+ex0)//2, midy-34, "neutral", font("mono", 22), fill=T.FAINT)
    text_c(d, (ax1+ex0)//2, midy+34, "telemetry", font("mono", 22), fill=T.FAINT)
    arrow(d, (ex1+18, midy), (rx0-18, midy), color=T.GREEN, width=7, head=26)
    text_c(d, (ex1+rx0)//2, midy-34, "workload-", font("mono", 22), fill=T.FAINT)
    text_c(d, (ex1+rx0)//2, midy+34, "model.json", font("mono", 22), fill=T.GREEN_HI)

    footer(d, W, H, "nothing about Dynatrace or k6 lives inside the engine — that boundary is the point")
    export(img, "d2-construct")

def draw_railtop(d, box, accent):
    x0, y0, x1, y1 = box
    d.rounded_rectangle([x0, y0, x1, y0 + 10], radius=5, fill=accent)
    d.rectangle([x0, y0 + 6, x1, y0 + 11], fill=T.BG1)

# =============================================================================
# D3 — DUAL-SOURCE STORAGE
# =============================================================================
def d3_dual():
    W, H = 2560, 1500
    img, d = canvas(W, H)
    title_block(d, 90, 70, "SPANS + RUM · ONE PROJECTION", "Where the truth is stored")
    caption(d, W//2, 212, "“Residual self image — the mental projection of your digital self.”", "Morpheus", w=1900)

    # faint wireframe projection motif behind the model card
    mcx, mcy = W//2, 1250
    for r in range(40, 230, 34):
        d.ellipse([mcx-r, mcy-int(r*0.5), mcx+r, mcy+int(r*0.5)], outline=(T.GREEN_DIM+(60,)), width=2)

    ltop = 300
    # LEFT: server-side traces -> spans
    lx0, lx1 = 120, 1140
    panel(d, [lx0, ltop, lx1, ltop+470], fill=T.BG1, outline=T.LINE2, width=2)
    draw_railtop(d, [lx0, ltop, lx1, ltop+470], T.GREEN)
    text_c(d, (lx0+lx1)//2, ltop+52, "SERVER-SIDE TRACES", font("mono", 34, bold=True), fill=T.INK)
    text_c(d, (lx0+lx1)//2, ltop+100, "what the services did", font("sans", 24, italic=True), fill=T.MUTE)
    chip(d, [lx0+80, ltop+150, lx1-80, ltop+248], fill=T.BG3, outline=T.GREEN)
    text_c(d, (lx0+lx1)//2, ltop+182, "fetch spans", font("mono", 38, bold=True), fill=T.GREEN_HI)
    text_c(d, (lx0+lx1)//2, ltop+222, "`spans` table", font("mono", 24), fill=T.MUTE)
    for i, s in enumerate(["service graph", "fan-out", "backend latency"]):
        bx0 = lx0+80 + i*320
        chip(d, [bx0, ltop+290, bx0+300, ltop+352], fill=T.BG2, outline=T.LINE2)
        text_c(d, bx0+150, ltop+321, s, font("mono", 23), fill=T.INK)
    text_c(d, (lx0+lx1)//2, ltop+410, "un-sampled on this tenant — samplingRatio 1.0",
           font("mono", 23), fill=T.FAINT)

    # RIGHT: RUM -> user.sessions + user.events
    rx0, rx1 = 1420, 2440
    panel(d, [rx0, ltop, rx1, ltop+470], fill=T.BG1, outline=T.LINE2, width=2)
    draw_railtop(d, [rx0, ltop, rx1, ltop+470], T.RED)
    text_c(d, (rx0+rx1)//2, ltop+52, "REAL USER MONITORING", font("mono", 34, bold=True), fill=T.INK)
    text_c(d, (rx0+rx1)//2, ltop+100, "what the humans did", font("sans", 24, italic=True), fill=T.MUTE)
    # user.sessions (live)
    chip(d, [rx0+70, ltop+150, (rx0+rx1)//2-18, ltop+300], fill=T.BG3, outline=T.GREEN)
    text_c(d, (rx0+(rx0+rx1)//2)//2+18, ltop+186, "fetch user.sessions", font("mono", 26, bold=True), fill=T.GREEN_HI)
    text_c(d, (rx0+(rx0+rx1)//2)//2+18, ltop+228, "1 row / real session", font("mono", 21), fill=T.MUTE)
    badge(d, (rx0+150, ltop+252), "LIVE · 35,679 / 24h", font("mono", 20, bold=True), fg=T.GREEN)
    # user.events (live — scope granted ISI-5719)
    chip(d, [(rx0+rx1)//2+18, ltop+150, rx1-70, ltop+300], fill=T.BG3, outline=T.GREEN)
    text_c(d, (rx1+(rx0+rx1)//2)//2-18, ltop+186, "fetch user.events", font("mono", 26, bold=True), fill=T.GREEN_HI)
    text_c(d, (rx1+(rx0+rx1)//2)//2-18, ltop+228, "ordered actions + think-time", font("mono", 19), fill=T.MUTE)
    badge(d, ((rx0+rx1)//2+110, ltop+252), "LIVE · 16 journeys", font("mono", 20, bold=True), fg=T.GREEN)
    text_c(d, (rx0+rx1)//2, ltop+352, "real journeys · real arrival curve · real device / geo / network",
           font("mono", 22), fill=T.INK)
    text_c(d, (rx0+rx1)//2, ltop+410, "volume merge needs only user.sessions + spans (live today)",
           font("mono", 21), fill=T.FAINT)

    # DQL band across
    dqy = ltop+510
    panel(d, [lx0, dqy, rx1, dqy+90], fill=(10,14,11), outline=T.GREEN_DIM, width=2)
    text_c(d, W//2, dqy+45, "one language  →  DQL  ·  queried from Grail", font("mono", 30, bold=True), fill=T.GREEN)

    # stitch key (the join between the two sources)
    sky = dqy+150
    kb = [W//2-340, sky, W//2+340, sky+92]
    glow_rect(img, kb, T.RED, radius=T.RADIUS, blur=18, alpha=70)
    panel(d, kb, fill=(26,14,17), outline=T.RED, width=3)
    text_c(d, W//2, sky+30, "stitched on", font("mono", 22), fill=T.MUTE)
    text_c(d, W//2, sky+62, "dt.rum.session.id", font("mono", 34, bold=True), fill=T.RED)

    # arrows: both sources -> stitch key -> one model
    arrow(d, ((lx0+lx1)//2, ltop+474), (mcx-250, sky-6), color=T.GREEN_DIM, width=6, head=22)
    arrow(d, ((rx0+rx1)//2, ltop+474), (mcx+250, sky-6), color=T.GREEN_DIM, width=6, head=22)
    arrow(d, (W//2, sky+96), (mcx, mcy-96), color=T.RED, width=6, head=22)

    # model card
    mb = [mcx-300, mcy-90, mcx+300, mcy+90]
    panel(d, mb, fill=T.BG2, outline=T.GREEN, width=3)
    draw_railtop(d, mb, T.GREEN)
    text_c(d, mcx, mcy-18, "one workload model", font("sans", 34, bold=True), fill=T.INK)
    text_c(d, mcx, mcy+30, "only as complete as the data behind it", font("sans", 23, italic=True), fill=T.MUTE)

    footer(d, W, H, "spans = what services did · RUM = what humans did · each is blind where the other sees")
    export(img, "d3-dual-source")

# =============================================================================
# D4 — ONE MODEL, MANY WORLDS
# =============================================================================
def d4_worlds():
    W, H = 2400, 1360
    img, d = canvas(W, H)
    title_block(d, 90, 70, "ONE MODEL · MANY WORLDS", "The renderer registry")
    caption(d, W//2, 205, "“Guns. Lots of guns.”", "Neo", w=1200)

    # source model node (center top)
    mcx, mty = W//2, 390
    mb = [mcx-380, mty-80, mcx+380, mty+80]
    glow_rect(img, mb, T.GREEN, radius=T.RADIUS, blur=24, alpha=70)
    panel(d, mb, fill=T.BG2, outline=T.GREEN, width=3)
    draw_railtop(d, mb, T.GREEN)
    text_c(d, mcx, mty-14, "workload-model.json", font("mono", 38, bold=True), fill=T.GREEN_HI)
    text_c(d, mcx, mty+32, "journeys · weights · arrival · think-time · data", font("mono", 20), fill=T.MUTE)

    # registry bus
    busy = 620
    d.line([mcx, mty+80, mcx, busy], fill=T.GREEN, width=6)
    text_c(d, mcx+180, (mty+80+busy)//2, "renderer registry", font("sans", 24, italic=True), fill=T.MUTE)
    bx0, bx1 = 240, W-240
    d.line([bx0, busy, bx1, busy], fill=T.GREEN, width=6)

    # four render targets (weapon rack)
    tools = [
        ("k6",      "ramping-arrival-rate · open model"),
        ("JMeter",  "Concurrency TG · Shaping Timer"),
        ("Locust",  "LoadTestShape · open-arrival"),
        ("Gatling", "Scala sim · Zipf feeders"),
    ]
    n = len(tools)
    slot = (bx1 - bx0) / n
    cardw = 420
    for i, (name, sub) in enumerate(tools):
        cx = bx0 + slot * (i + 0.5)
        arrow(d, (cx, busy), (cx, busy+118), color=T.GREEN_DIM, width=5, head=18)
        box = [cx-cardw/2, busy+130, cx+cardw/2, busy+470]
        panel(d, box, fill=T.BG2, outline=T.AMBER_DIM, width=2)
        draw_railtop(d, box, T.AMBER)
        text_c(d, cx, busy+205, name, font("mono", 52, bold=True), fill=T.INK)
        for j, ln in enumerate(wrap(d, sub, font("mono", 20), cardw-70)):
            text_c(d, cx, busy+285 + j*30, ln, font("mono", 20), fill=T.MUTE)
        badge(d, (cx-118, busy+375), "✓ acceptance tests", font("mono", 22, bold=True), fg=T.GREEN)

    footer(d, W, H, "the model is the asset · the tool is a render target · all four pass acceptance tests today")
    export(img, "d4-many-worlds")

# =============================================================================
# D5 — THE STACK (cluster architecture)
# =============================================================================
def d5_stack():
    W, H = 3040, 1500
    img, d = canvas(W, H)
    title_block(d, 90, 64, "THE REAL WIRED STACK — NOT SLIDEWARE", "Architecture: the stack in our cluster")

    rowy = 500          # main pipeline row center
    nh = 230
    def nb(x, w): return [x, rowy-nh/2, x+w, rowy+nh/2]

    # 1 Astroshop (SUT)
    b1 = nb(90, 440)
    node(img, d, b1, "Astroshop", subs=["OTel Demo", "frontend + ~15 svcs"], accent=T.BLUE, title_size=40)
    text_c(d, (b1[0]+b1[2])//2, b1[3]+34, "system under test", font("sans", 22, italic=True), fill=T.FAINT)

    # 2 Collector
    b2 = nb(640, 400)
    node(img, d, b2, "OTel Collector", subs=["OTLP in → export"], accent=T.GREEN, title_size=36)

    # 3 Grail (big)
    gx0 = 1150; gw = 620
    gb = [gx0, rowy-300, gx0+gw, rowy+300]
    panel(d, gb, fill=T.BG1, outline=T.GREEN, width=3)
    draw_railtop(d, gb, T.GREEN)
    text_c(d, gx0+gw//2, gb[1]+54, "Dynatrace Grail", font("sans", 40, bold=True), fill=T.INK)
    text_c(d, gx0+gw//2, gb[1]+100, "read via DQL / dtctl", font("mono", 24), fill=T.MUTE)
    chip(d, [gx0+50, gb[1]+140, gx0+gw-50, gb[1]+210], fill=T.BG3, outline=T.GREEN)
    text_c(d, gx0+gw//2, gb[1]+175, "spans  (traces)", font("mono", 30, bold=True), fill=T.GREEN_HI)
    chip(d, [gx0+50, gb[1]+232, gx0+gw-50, gb[1]+302], fill=T.BG3, outline=T.RED)
    text_c(d, gx0+gw//2, gb[1]+267, "RUM · user.sessions", font("mono", 28, bold=True), fill=T.RED)
    chip(d, [gx0+50, gb[1]+324, gx0+gw-50, gb[1]+394], fill=T.BG3, outline=T.RED)
    text_c(d, gx0+gw//2, gb[1]+360, "RUM · user.events", font("mono", 26, bold=True), fill=T.RED)

    # 4 the built part: agent -> skill -> engine (stacked column)
    cx0 = 1930; cw = 340
    labels = [("agent", T.BLUE), ("skill", T.GREEN), ("engine", T.GREEN)]
    chy = rowy-300
    built_boxes = []
    for i,(lab,acc) in enumerate(labels):
        bb = [cx0, chy+i*112, cx0+cw, chy+i*112+94]
        node(img, d, bb, lab, accent=acc, fill=T.BG2, title_size=34)
        built_boxes.append(bb)
    text_c(d, cx0+cw//2, chy+3*112+22, "DQL in → model out", font("mono", 22), fill=T.MUTE)
    text_c(d, cx0+cw//2, chy-36, "the part we built", font("sans", 22, italic=True), fill=T.FAINT)

    # V1 gate lock between engine and renderers (inline on the row)
    gatex = cx0+cw+180
    gy0, gy1 = rowy-80, rowy+90
    glow_rect(img, [gatex-78, gy0, gatex+78, gy1], T.RED, radius=14, blur=18, alpha=80)
    panel(d, [gatex-78, gy0, gatex+78, gy1], fill=(26,14,17), outline=T.RED, width=3)
    lock(d, (gatex, rowy-6), size=50, color=T.RED)
    text_c(d, gatex, rowy+58, "V1 gate", font("mono", 24, bold=True), fill=T.RED)
    text_c(d, gatex, gy1+34, "human approval", font("mono", 19), fill=T.FAINT)
    text_c(d, gatex, gy1+58, "between extract & render", font("mono", 19), fill=T.FAINT)

    # 5 renderers
    rx0 = gatex+240; rw = 320
    rb = [rx0, rowy-175, rx0+rw, rowy+175]
    panel(d, rb, fill=T.BG2, outline=T.AMBER, width=2)
    draw_railtop(d, rb, T.AMBER)
    text_c(d, rx0+rw//2, rb[1]+50, "renderers", font("sans", 32, bold=True), fill=T.INK)
    for i,t in enumerate(["k6","JMeter"]):
        chip(d, [rx0+40, rb[1]+105+i*95, rx0+rw-40, rb[1]+180+i*95], fill=T.BG3, outline=T.AMBER_DIM)
        text_c(d, rx0+rw//2, rb[1]+142+i*95, t, font("mono", 30, bold=True), fill=T.INK)

    # ---- connectors along pipeline
    arrow(d, (b1[2]+14, rowy), (b2[0]-14, rowy), color=T.GREEN, width=6, head=22)
    text_c(d, (b1[2]+b2[0])//2, rowy-30, "OTLP", font("mono", 22), fill=T.FAINT)
    arrow(d, (b2[2]+14, rowy), (gx0-14, rowy), color=T.GREEN, width=6, head=22)
    # logs dashed (unavailable)
    dashed_line(d, (b2[2]+14, rowy+150), (gx0-14, rowy+150), fill=T.AMBER, width=4)
    text_c(d, (b2[2]+gx0)//2, rowy+180, "logs — empty on this tenant", font("mono", 20), fill=T.AMBER)
    # grail -> built column (spans solid; user.events now solid — live, scope granted ISI-5719)
    arrow(d, (gx0+gw+14, rowy-60), (cx0-14, rowy-150), color=T.GREEN, width=6, head=20)
    arrow(d, (gx0+gw+14, rowy+120), (cx0-14, rowy+40), color=T.RED, width=6, head=20)
    text_c(d, (gx0+gw+cx0)//2+10, rowy+150, "user.events → journeys", font("mono", 19), fill=T.RED)
    # engine -> gate -> renderers
    arrow(d, (built_boxes[2][2]+10, rowy), (gatex-80, rowy), color=T.GREEN, width=6, head=20)
    arrow(d, (gatex+80, rowy), (rx0-14, rowy), color=T.RED, width=6, head=20)

    # safety footer band
    by = 1250
    panel(d, [90, by, W-640, by+90], fill=(10,14,11), outline=T.GREEN_DIM, width=2)
    text_c(d, (90+W-640)//2, by+46, "read-only  ·  extraction-only  ·  non-production  ·  tenant-isolated",
           font("mono", 28, bold=True), fill=T.GREEN)

    # repo + REAL QR — public mirror is live (ISI-5659 published; repo resolves 200)
    from qr_util import draw_qr, REPO_URL
    qb = [W-540, by-44, W-150, by+134]
    panel(d, qb, fill=T.BG2, outline=T.LINE2, width=2)
    qsize = draw_qr(d, (qb[2]-168, qb[1]+14), 150, url=REPO_URL,
                    dark=T.INK, light=(6, 9, 7))
    text_l(d, (qb[0]+24, qb[1]+20), "repo", font("mono", 24, bold=True), fill=T.INK)
    text_l(d, (qb[0]+24, qb[1]+56), "github.com/", font("mono", 18), fill=T.MUTE)
    text_l(d, (qb[0]+24, qb[1]+80), "henrikrexed/", font("mono", 18), fill=T.MUTE)
    text_l(d, (qb[0]+24, qb[1]+104), "AI-Performance-", font("mono", 18), fill=T.GREEN)
    text_l(d, (qb[0]+24, qb[1]+128), "Testing", font("mono", 18), fill=T.GREEN)
    text_c(d, (qb[0]+qb[2])//2, qb[3]+24, "scan → live public mirror (ISI-5659)", font("mono", 18), fill=T.GREEN_DIM)

    export(img, "d5-stack")

if __name__ == "__main__":
    print("generating diagrams ->", OUT)
    d1_loop(); d2_construct(); d3_dual(); d4_worlds(); d5_stack()
    print("done.")
