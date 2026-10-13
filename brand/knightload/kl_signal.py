#!/usr/bin/env python3
"""
kl_signal.py — Knightload LOAD-SIGNAL marks (ISI-5779 round 3.2).

Board direction (Henrik, 2026-10-13): Knightload was inspired by Batman / The
Dark Knight; "Alfred" (the Paperclip agent) is from the same universe. The
creative key is the **bat-signal reimagined as a LOAD-SIGNAL** — "un K dans un
rond ou losange". At night the signal lights up, the knight answers. One mark
fuses all pillars: Knight (answers) · Night (when it shines) · Load (the signal
IS the ramp/trigger).

Four directions:
  1  signal-circle  — K in a glowing roundel, halo + rising beam.
  2  signal-diamond — K knocked out of a glowing lozenge (projector beam /
                      plot-point / badge). RECOMMENDED.
  3  signal-minimal — thin-stroke circle + K, monochrome, 16px-first.
  4  signal-kray    — the K's ascending arm becomes a projector beam escaping
                      the container (load curve + signal in one gesture).

Defensibly original: geometric K + abstract signal geometry. NO bat silhouette,
no DC-trademark proximity. Dark night palette, ONE accent glow (teal default /
amber alt). Pure Pillow + DejaVu (no cairo/resvg) — same stack as ISI-5724.
"""
import math
from PIL import Image, ImageDraw
import kl_brand as k
import kl_k

SS = 4
KFRAC = 0.60  # Ramp-K glyph height as a fraction of the container tile
# Ramp-K local anchors (from kl_k.k_ramp geometry)
_K_TIP = (0.86, 0.09)       # ramp (upper-arm) tip
_K_JUNCTION = (0.30, 0.49)  # stem/arm junction
CYAN, AMBER, SILVER = k.CYAN, k.AMBER, k.SILVER
INDIGO0, INDIGO1, INDIGO2 = k.INDIGO0, k.INDIGO1, k.INDIGO2
NIGHT_TOP = (20, 22, 42)
NIGHT_BOT = (34, 48, 86)


def _tile(size):
    W = size * SS
    img = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img), W


def _finish(img, size):
    return img.resize((size, size), Image.LANCZOS)


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _vgrad(W, top, bot):
    col = Image.new("RGB", (1, W))
    for y in range(W):
        col.putpixel((0, y), _lerp(top, bot, y / max(1, W - 1)))
    return col.resize((W, W)).convert("RGBA")


def _radial(W, cx, cy, r1, color, a_center, power=1.5, steps=90):
    """Bright center fading to 0 at r1. Drawn large->small so center wins."""
    g = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    gd = ImageDraw.Draw(g)
    for i in range(steps, 0, -1):
        r = r1 * i / steps
        a = int(a_center * (1 - i / steps) ** power)
        gd.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color + (a,))
    return g


def _beam(W, cx, y0, y1, half0, half1, color, a0, a1):
    """A vertical light cone from y0 (apex, half-width half0, alpha a0) to y1
    (half-width half1, alpha a1). Rendered as a gradient-alpha trapezoid."""
    layer = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    strip = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    sd = ImageDraw.Draw(strip)
    n = 120
    lw = max(1, int(abs(y1 - y0) / n) + 1)
    for i in range(n + 1):
        t = i / n
        y = int(y0 + (y1 - y0) * t)
        a = int(a0 + (a1 - a0) * t)
        sd.line([(0, y), (W, y)], fill=color + (max(0, a),), width=lw)
    mask = Image.new("L", (W, W), 0)
    md = ImageDraw.Draw(mask)
    md.polygon([(cx - half0, y0), (cx + half0, y0), (cx + half1, y1), (cx - half1, y1)], fill=255)
    layer = Image.composite(strip, layer, mask)
    return layer


def _diamond(cx, cy, hw, hh):
    return [(cx, cy - hh), (cx + hw, cy), (cx, cy + hh), (cx - hw, cy)]


def _kstamp(W, frac, color, drop_upper=False):
    """Stamp the approved round-3.1 Ramp-K (kl_k.k_ramp) into a WxW canvas,
    centred, at height = frac*W, recoloured to `color`. Returns the RGBA stamp.
    `drop_upper` renders only stem+leg (for the K-Ray beam variant)."""
    ksz = max(8, int(frac * W))
    if drop_upper:
        kimg = _ramp_stem_leg(ksz, color)
    else:
        kimg = kl_k.k_ramp(ksz, mono=True, silh=color)
    st = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    ox, oy = (W - kimg.width) // 2, (W - kimg.height) // 2
    st.alpha_composite(kimg, (ox, oy))
    return st, (ox, oy, ksz)


def _ramp_stem_leg(size, color):
    """Ramp-K minus its upper arm (stem + leg only)."""
    W = size * kl_k.SS
    img = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    p = kl_k._pts
    d.rounded_rectangle(p(W, [(0.17, 0.13), (0.30, 0.87)])[0] + p(W, [(0.17, 0.13), (0.30, 0.87)])[1],
                        radius=0.03 * W, fill=color + (255,))
    d.polygon(p(W, [(0.30, 0.52), (0.72, 0.87), (0.85, 0.87), (0.43, 0.49)]), fill=color + (255,))
    return img.resize((size, size), Image.LANCZOS)


def _anchor(ox, oy, ksz, local):
    return (ox + local[0] * ksz, oy + local[1] * ksz)


# ============================================================ 1 · signal-circle
def sig_circle(size, accent=CYAN, mono=False):
    img, d, W = _tile(size)
    cx = cy = W * 0.5
    R = W * 0.40
    if mono:
        d.ellipse([cx - R, cy - R, cx + R, cy + R], outline=SILVER + (255,), width=int(W * 0.045))
        stamp, _ = _kstamp(W, KFRAC, SILVER)
        img.alpha_composite(stamp)
        return _finish(img, size)
    # slim signal shaft rising behind (projected into the night, not wings)
    img.alpha_composite(_beam(W, cx, cy - R * 0.1, W * 0.04, R * 0.16, R * 0.42, accent, 120, 0))
    # night roundel
    mask = Image.new("L", (W, W), 0)
    ImageDraw.Draw(mask).ellipse([cx - R, cy - R, cx + R, cy + R], fill=255)
    night = _vgrad(W, NIGHT_TOP, NIGHT_BOT); night.putalpha(mask)
    img.alpha_composite(night)
    # rim ring (accent)
    d.ellipse([cx - R, cy - R, cx + R, cy + R], outline=accent + (255,), width=int(W * 0.022))
    # glow behind K + glowing accent Ramp-K
    img.alpha_composite(_radial(W, cx, cy, R * 0.82, accent, 110))
    stamp, _ = _kstamp(W, KFRAC, accent)
    img.alpha_composite(stamp)
    return _finish(img, size)


# =========================================================== 2 · signal-diamond
def sig_diamond(size, accent=CYAN, mono=False):
    img, d, W = _tile(size)
    cx, cy = W * 0.5, W * 0.5
    hw, hh = W * 0.40, W * 0.46
    dia = _diamond(cx, cy, hw, hh)
    if mono:
        d.line(dia + [dia[0]], fill=SILVER + (255,), width=int(W * 0.04), joint="curve")
        stamp, _ = _kstamp(W, KFRAC * 0.92, SILVER)
        img.alpha_composite(stamp)
        return _finish(img, size)
    # glowing diamond: accent radial field inside the diamond
    mask = Image.new("L", (W, W), 0)
    ImageDraw.Draw(mask).polygon(dia, fill=255)
    field = _radial(W, cx, cy * 0.92, hh * 1.15, accent, 255, power=1.1)
    base = Image.new("RGBA", (W, W), INDIGO1 + (255,))
    glow = Image.alpha_composite(base, field)
    glow.putalpha(mask)
    img.alpha_composite(glow)
    # crisp accent edge
    d.line(dia + [dia[0]], fill=accent + (255,), width=int(W * 0.018), joint="curve")
    # Ramp-K knocked out in night colour (negative space)
    stamp, _ = _kstamp(W, KFRAC * 0.92, (255, 255, 255))
    night_k = Image.new("RGBA", (W, W), INDIGO0 + (255,))
    img = Image.alpha_composite(img, Image.composite(night_k, Image.new("RGBA", (W, W), (0, 0, 0, 0)), stamp.split()[3]))
    return _finish(img, size)


# =========================================================== 3 · signal-minimal
def sig_minimal(size, accent=SILVER, mono=True):
    img, d, W = _tile(size)
    cx = cy = W * 0.5
    R = W * 0.40
    col = SILVER if mono else accent
    d.ellipse([cx - R, cy - R, cx + R, cy + R], outline=col + (255,), width=int(W * 0.05))
    stamp, _ = _kstamp(W, KFRAC, col)
    img.alpha_composite(stamp)
    return _finish(img, size)


# ============================================================== 4 · signal-kray
def sig_kray(size, accent=CYAN, mono=False):
    img, d, W = _tile(size)
    cx, cy = W * 0.5, W * 0.5
    hw, hh = W * 0.40, W * 0.46
    dia = _diamond(cx, cy, hw, hh)
    col = SILVER if mono else accent
    # night diamond
    if not mono:
        mask = Image.new("L", (W, W), 0)
        ImageDraw.Draw(mask).polygon(dia, fill=255)
        night = _vgrad(W, NIGHT_TOP, NIGHT_BOT); night.putalpha(mask)
        img.alpha_composite(night)
        d.line(dia + [dia[0]], fill=accent + (255,), width=int(W * 0.016), joint="curve")
    else:
        d.line(dia + [dia[0]], fill=SILVER + (255,), width=int(W * 0.035), joint="curve")
    # Ramp-K stem+leg in silver; upper ramp arm becomes a projector beam escaping
    kcol = SILVER
    frac = KFRAC * 0.92
    stamp, (ox, oy, ksz) = _kstamp(W, frac, kcol, drop_upper=True)
    img.alpha_composite(stamp)
    jx, jy = _anchor(ox, oy, ksz, _K_JUNCTION)
    tx, ty = _anchor(ox, oy, ksz, _K_TIP)
    dx, dy = tx - jx, ty - jy
    L = math.hypot(dx, dy); ux, uy = dx / L, dy / L
    px, py = -uy, ux
    beamlen = W * 0.60
    w0, w1 = W * 0.03, W * 0.105
    bl = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    bd = ImageDraw.Draw(bl)
    nseg = 60
    for i in range(nseg):
        t0, t1 = i / nseg, (i + 1) / nseg
        a = int(255 * (1 - t0) ** 1.25)
        ww0 = w0 + (w1 - w0) * t0
        ww1 = w0 + (w1 - w0) * t1
        s = (jx + ux * beamlen * t0, jy + uy * beamlen * t0)
        e = (jx + ux * beamlen * t1, jy + uy * beamlen * t1)
        bd.polygon([(s[0] + px * ww0, s[1] + py * ww0), (e[0] + px * ww1, e[1] + py * ww1),
                    (e[0] - px * ww1, e[1] - py * ww1), (s[0] - px * ww0, s[1] - py * ww0)],
                   fill=(col if not mono else SILVER) + (a,))
    img.alpha_composite(bl)
    d.ellipse([jx - W * 0.028, jy - W * 0.028, jx + W * 0.028, jy + W * 0.028], fill=col + (255,))
    return _finish(img, size)


SIGNALS = {
    "1": ("Signal Circle", sig_circle),
    "2": ("Signal Diamond", sig_diamond),
    "3": ("Signal Minimal", sig_minimal),
    "4": ("Signal K-Ray", sig_kray),
}
