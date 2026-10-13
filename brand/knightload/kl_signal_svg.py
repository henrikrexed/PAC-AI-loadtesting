#!/usr/bin/env python3
"""kl_signal_svg.py — SVG twins of the LOAD-SIGNAL marks (ISI-5779 round 3.2b).

Two-tone Ramp-K: stem+leg = silver structure, the ascending ramp (upper arm) =
glowing accent "signal" (the feature Henrik called out). viewBox 0 0 1000 1000.
Glow via <filter> feGaussianBlur; containers filled with night gradient."""
import os, math

OUT = os.path.join(os.path.dirname(__file__), "svg")
os.makedirs(OUT, exist_ok=True)
S = 1000.0
CYAN, AMBER, SILVER = "#2EE6D6", "#FFB23E", "#C7CDD6"
INDIGO0, INDIGO1 = "#1A1A2E", "#16213E"
NIGHT_TOP, NIGHT_BOT = "#14162A", "#22305A"

RK_STEM = (0.17, 0.13, 0.30, 0.87)
RK_LEG = [(0.30, 0.52), (0.70, 0.87), (0.84, 0.87), (0.44, 0.50)]
JUNCTION = (0.375, 0.56)
TIP = (0.85, 0.16)
# ramp-up = ascending graph-bar chart (board feedback)
RK_BARS_N = 5
RK_BARS_X0 = 0.31
RK_BARS_W = 0.072
RK_BARS_BASE = 0.57
RK_BARS_TOP_HI, RK_BARS_TOP_LO = 0.49, 0.115


def _bar_rects(frac):
    step = (0.86 - RK_BARS_X0 - RK_BARS_W) / (RK_BARS_N - 1)
    out = []
    for i in range(RK_BARS_N):
        t = i / (RK_BARS_N - 1)
        bx = RK_BARS_X0 + i * step
        top = RK_BARS_TOP_HI + (RK_BARS_TOP_LO - RK_BARS_TOP_HI) * t
        x0, y0 = _map(frac, bx, top)
        x1, y1 = _map(frac, bx + RK_BARS_W, RK_BARS_BASE)
        out.append((x0, y0, x1 - x0, y1 - y0))
    return out


def _map(frac, lx, ly):
    tile = frac * S; o = (S - tile) / 2
    return (o + lx * tile, o + ly * tile)


def _polystr(pts):
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)


def k_shapes(frac, base, ramp, draw_ramp=True, glow=False):
    tile = frac * S
    x0, y0 = _map(frac, RK_STEM[0], RK_STEM[1])
    x1, y1 = _map(frac, RK_STEM[2], RK_STEM[3])
    out = [f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{x1-x0:.1f}" height="{y1-y0:.1f}" '
           f'rx="{0.03*tile:.1f}" fill="{base}"/>']
    out.append(f'<polygon points="{_polystr([_map(frac,*p) for p in RK_LEG])}" fill="{base}"/>')
    if draw_ramp:
        bars = _bar_rects(frac)
        rad = 0.012 * tile
        def bar(x, y, w, h, extra=""):
            return (f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
                    f'rx="{rad:.1f}" fill="{ramp}" {extra}/>')
        if glow:
            out.append('<g filter="url(#glow)" opacity="0.6">'
                       + "".join(bar(*b) for b in bars) + '</g>')
        out.extend(bar(*b) for b in bars)
    return "".join(out)


def _hdr(title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 1000" '
            f'width="512" height="512" role="img" aria-label="Knightload — {title}">\n'
            f'  <title>Knightload — {title}</title>\n')


def _glowfilter():
    return ('  <filter id="glow" x="-40%" y="-40%" width="180%" height="180%">'
            '<feGaussianBlur stdDeviation="14"/></filter>\n')


def _night(gid):
    return (f'    <linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0%" stop-color="{NIGHT_TOP}"/>'
            f'<stop offset="100%" stop-color="{NIGHT_BOT}"/></linearGradient>\n')


def _diamond_pts(cx, cy, hw, hh):
    return [(cx, cy - hh), (cx + hw, cy), (cx, cy + hh), (cx - hw, cy)]


def svg_circle(accent=CYAN):
    cx = cy = 500; R = 400; f = 0.60
    s = _hdr("Signal Circle")
    s += "  <defs>\n" + _night("nC") + _glowfilter() + "  </defs>\n"
    s += f'  <circle cx="{cx}" cy="{cy}" r="{R}" fill="url(#nC)"/>\n'
    s += f'  <circle cx="{cx}" cy="{cy}" r="{R}" fill="none" stroke="{accent}" stroke-width="22"/>\n'
    s += "  " + k_shapes(f, SILVER, accent, glow=True) + "\n</svg>\n"
    return s


def svg_diamond(accent=CYAN, mono=False):
    cx, cy, hw, hh = 500, 500, 400, 460
    dia = _diamond_pts(cx, cy, hw, hh)
    if mono:
        s = _hdr("Signal Diamond (mono)")
        s += f'  <polygon points="{_polystr(dia)}" fill="none" stroke="{SILVER}" stroke-width="40" stroke-linejoin="round"/>\n'
        s += "  " + k_shapes(0.552, SILVER, SILVER) + "\n</svg>\n"
        return s
    s = _hdr("Signal Diamond")
    s += "  <defs>\n" + _night("nD") + _glowfilter() + "  </defs>\n"
    s += f'  <polygon points="{_polystr(dia)}" fill="url(#nD)" stroke="{accent}" stroke-width="18" stroke-linejoin="round"/>\n'
    s += "  " + k_shapes(0.552, SILVER, accent, glow=True) + "\n</svg>\n"
    return s


def svg_minimal(col=SILVER):
    cx = cy = 500; R = 400
    s = _hdr("Signal Minimal")
    s += f'  <circle cx="{cx}" cy="{cy}" r="{R}" fill="none" stroke="{col}" stroke-width="50"/>\n'
    s += "  " + k_shapes(0.60, col, col) + "\n</svg>\n"
    return s


def svg_kray(accent=CYAN):
    cx, cy, hw, hh = 500, 500, 400, 460
    dia = _diamond_pts(cx, cy, hw, hh)
    f = 0.552
    jx, jy = _map(f, *JUNCTION)
    tx, ty = _map(f, *TIP)
    dx, dy = tx - jx, ty - jy
    L = math.hypot(dx, dy); ux, uy = dx / L, dy / L
    px, py = -uy, ux
    blen = 620; w0, w1 = 35, 110
    e = (jx + ux * blen, jy + uy * blen)
    beam = [(jx + px * w0, jy + py * w0), (e[0] + px * w1, e[1] + py * w1),
            (e[0] - px * w1, e[1] - py * w1), (jx - px * w0, jy - py * w0)]
    s = _hdr("Signal K-Ray")
    s += "  <defs>\n" + _night("nK")
    s += (f'    <linearGradient id="beamK" gradientUnits="userSpaceOnUse" '
          f'x1="{jx:.0f}" y1="{jy:.0f}" x2="{e[0]:.0f}" y2="{e[1]:.0f}">'
          f'<stop offset="0%" stop-color="{accent}" stop-opacity="1"/>'
          f'<stop offset="100%" stop-color="{accent}" stop-opacity="0"/></linearGradient>\n  </defs>\n')
    s += f'  <polygon points="{_polystr(dia)}" fill="url(#nK)" stroke="{accent}" stroke-width="16" stroke-linejoin="round"/>\n'
    s += "  " + k_shapes(f, SILVER, SILVER, draw_ramp=False) + "\n"
    s += f'  <polygon points="{_polystr(beam)}" fill="url(#beamK)"/>\n'
    s += f'  <circle cx="{jx:.0f}" cy="{jy:.0f}" r="26" fill="{accent}"/>\n</svg>\n'
    return s


def main():
    files = {
        "knightload-signal-1-circle.svg": svg_circle(),
        "knightload-signal-2-diamond.svg": svg_diamond(),
        "knightload-signal-2-diamond-amber.svg": svg_diamond(accent=AMBER),
        "knightload-signal-2-diamond-mono.svg": svg_diamond(mono=True),
        "knightload-signal-3-minimal.svg": svg_minimal(),
        "knightload-signal-4-kray.svg": svg_kray(),
    }
    for name, body in files.items():
        with open(os.path.join(OUT, name), "w") as fh:
            fh.write(body)
        print("  ", name, len(body), "bytes")
    print("done ->", OUT)


if __name__ == "__main__":
    main()
