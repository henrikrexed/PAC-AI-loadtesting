#!/usr/bin/env python3
"""kl_signal_svg.py — production SVG twins of the LOAD-SIGNAL marks (ISI-5779 r3.2).

viewBox 0 0 1000 1000. Houses the approved round-3.1 Ramp-K glyph inside the
signal containers. Gradients (night / glow / beam) via <linearGradient> /
<radialGradient>; the diamond knockout is an over-drawn night-colour K."""
import os, math

OUT = os.path.join(os.path.dirname(__file__), "svg")
os.makedirs(OUT, exist_ok=True)
S = 1000.0
CYAN, AMBER, SILVER = "#2EE6D6", "#FFB23E", "#C7CDD6"
INDIGO0, INDIGO1 = "#1A1A2E", "#16213E"
NIGHT_TOP, NIGHT_BOT = "#14162A", "#22305A"

# Ramp-K local geometry (unit tile), from kl_k.k_ramp
STEM = (0.17, 0.13, 0.30, 0.87)
LEG = [(0.30, 0.52), (0.72, 0.87), (0.85, 0.87), (0.43, 0.49)]
RAMP = [(0.30, 0.45), (0.86, 0.09), (0.60, 0.27), (0.41, 0.55)]
JUNCTION = (0.30, 0.49)
TIP = (0.86, 0.09)


def _map(frac, lx, ly):
    tile = frac * S
    o = (S - tile) / 2
    return (o + lx * tile, o + ly * tile)


def _poly(pts, fill, extra=""):
    s = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    return f'<polygon points="{s}" fill="{fill}" {extra}/>'


def k_shapes(frac, fill, drop_upper=False):
    tile = frac * S
    x0, y0 = _map(frac, STEM[0], STEM[1])
    x1, y1 = _map(frac, STEM[2], STEM[3])
    out = [f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{x1-x0:.1f}" height="{y1-y0:.1f}" '
           f'rx="{0.03*tile:.1f}" fill="{fill}"/>']
    out.append(_poly([_map(frac, *p) for p in LEG], fill))
    if not drop_upper:
        out.append(_poly([_map(frac, *p) for p in RAMP], fill))
    return "".join(out)


def _hdr(title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 1000" '
            f'width="512" height="512" role="img" aria-label="Knightload — {title}">\n'
            f'  <title>Knightload — {title}</title>\n')


def _diamond_pts(cx, cy, hw, hh):
    return [(cx, cy - hh), (cx + hw, cy), (cx, cy + hh), (cx - hw, cy)]


# ------------------------------------------------------------- 1 signal-circle
def svg_circle(accent=CYAN):
    cx = cy = 500; R = 400; f = 0.60
    s = _hdr("Signal Circle")
    s += ('  <defs>\n'
          '    <radialGradient id="glowC" cx="50%" cy="50%" r="50%">\n'
          f'      <stop offset="0%" stop-color="{accent}" stop-opacity="0.45"/>\n'
          f'      <stop offset="100%" stop-color="{accent}" stop-opacity="0"/>\n'
          '    </radialGradient>\n'
          '    <linearGradient id="nightC" x1="0" y1="0" x2="0" y2="1">\n'
          f'      <stop offset="0%" stop-color="{NIGHT_TOP}"/>\n'
          f'      <stop offset="100%" stop-color="{NIGHT_BOT}"/>\n'
          '    </linearGradient>\n  </defs>\n')
    s += f'  <circle cx="{cx}" cy="{cy}" r="{R}" fill="url(#nightC)"/>\n'
    s += f'  <circle cx="{cx}" cy="{cy}" r="{R}" fill="none" stroke="{accent}" stroke-width="22"/>\n'
    s += f'  <circle cx="{cx}" cy="{cy}" r="{R*0.82:.0f}" fill="url(#glowC)"/>\n'
    s += "  " + k_shapes(f, accent) + "\n</svg>\n"
    return s


# ------------------------------------------------------------ 2 signal-diamond
def svg_diamond(accent=CYAN, mono=False):
    cx, cy, hw, hh = 500, 500, 400, 460
    dia = _diamond_pts(cx, cy, hw, hh)
    if mono:
        s = _hdr("Signal Diamond (mono)")
        s += f'  <polygon points="{" ".join(f"{x:.0f},{y:.0f}" for x,y in dia)}" fill="none" stroke="{SILVER}" stroke-width="40" stroke-linejoin="round"/>\n'
        s += "  " + k_shapes(0.55, SILVER) + "\n</svg>\n"
        return s
    s = _hdr("Signal Diamond")
    s += ('  <defs>\n'
          '    <radialGradient id="glowD" cx="50%" cy="46%" r="62%">\n'
          f'      <stop offset="0%" stop-color="{accent}"/>\n'
          f'      <stop offset="100%" stop-color="{INDIGO1}"/>\n'
          '    </radialGradient>\n  </defs>\n')
    s += f'  <polygon points="{" ".join(f"{x:.0f},{y:.0f}" for x,y in dia)}" fill="url(#glowD)" stroke="{accent}" stroke-width="18" stroke-linejoin="round"/>\n'
    # Ramp-K knocked out in night colour
    s += "  " + k_shapes(0.55, INDIGO0) + "\n</svg>\n"
    return s


# ------------------------------------------------------------ 3 signal-minimal
def svg_minimal(col=SILVER):
    cx = cy = 500; R = 400
    s = _hdr("Signal Minimal")
    s += f'  <circle cx="{cx}" cy="{cy}" r="{R}" fill="none" stroke="{col}" stroke-width="50"/>\n'
    s += "  " + k_shapes(0.60, col) + "\n</svg>\n"
    return s


# -------------------------------------------------------------- 4 signal-kray
def svg_kray(accent=CYAN):
    cx, cy, hw, hh = 500, 500, 400, 460
    dia = _diamond_pts(cx, cy, hw, hh)
    f = 0.55
    jx, jy = _map(f, *JUNCTION)
    tx, ty = _map(f, *TIP)
    dx, dy = tx - jx, ty - jy
    L = math.hypot(dx, dy); ux, uy = dx / L, dy / L
    px, py = -uy, ux
    blen = 600; w0, w1 = 30, 105
    e = (jx + ux * blen, jy + uy * blen)
    beam = [(jx + px * w0, jy + py * w0), (e[0] + px * w1, e[1] + py * w1),
            (e[0] - px * w1, e[1] - py * w1), (jx - px * w0, jy - py * w0)]
    s = _hdr("Signal K-Ray")
    s += ('  <defs>\n'
          '    <linearGradient id="nightK" x1="0" y1="0" x2="0" y2="1">\n'
          f'      <stop offset="0%" stop-color="{NIGHT_TOP}"/>\n'
          f'      <stop offset="100%" stop-color="{NIGHT_BOT}"/>\n    </linearGradient>\n'
          f'    <linearGradient id="beamK" gradientUnits="userSpaceOnUse" '
          f'x1="{jx:.0f}" y1="{jy:.0f}" x2="{e[0]:.0f}" y2="{e[1]:.0f}">\n'
          f'      <stop offset="0%" stop-color="{accent}" stop-opacity="1"/>\n'
          f'      <stop offset="100%" stop-color="{accent}" stop-opacity="0"/>\n'
          '    </linearGradient>\n  </defs>\n')
    s += f'  <polygon points="{" ".join(f"{x:.0f},{y:.0f}" for x,y in dia)}" fill="url(#nightK)" stroke="{accent}" stroke-width="16" stroke-linejoin="round"/>\n'
    s += "  " + k_shapes(f, SILVER, drop_upper=True) + "\n"
    s += "  " + _poly(beam, "url(#beamK)") + "\n"
    s += f'  <circle cx="{jx:.0f}" cy="{jy:.0f}" r="28" fill="{accent}"/>\n</svg>\n'
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
