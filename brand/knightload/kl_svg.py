#!/usr/bin/env python3
"""
kl_svg.py — production-true SVG twins of the Knightload icon marks (ISI-5779).

The PNG marks in kl_brand.py are pure geometry on a 0..1 normalized tile. These
SVGs mirror that geometry exactly on a 0..1000 viewBox so the vector art is
resolution-independent and editable (no cairo/resvg needed to author SVG text).
Negative-space cuts (crescent moon, visor slot) use <mask>.

Colours are CSS custom properties with concrete fallbacks so a single edit
re-themes every file:  --silh (#C7CDD6), --accent (#2EE6D6), --indigo (#16213E).
"""
import os, math

OUT = os.path.join(os.path.dirname(__file__), "svg")
os.makedirs(OUT, exist_ok=True)

S = 1000.0
SILH, ACCENT, INDIGO, INDIGO0 = "#C7CDD6", "#2EE6D6", "#16213E", "#1A1A2E"


def P(nx, ny):
    return f"{nx*S:.2f},{ny*S:.2f}"


def arc(cx, cy, rx, ry, a0, a1, n=40):
    out = []
    for i in range(n + 1):
        a = math.radians(a0 + (a1 - a0) * i / n)
        out.append(P(cx + rx * math.cos(a), cy + ry * math.sin(a)))
    return out


def poly(points, fill, extra=""):
    return f'<polygon points="{" ".join(points)}" fill="{fill}" {extra}/>'


def header(title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 1000" '
            f'width="512" height="512" role="img" aria-label="Knightload — {title}">\n'
            f'  <title>Knightload — {title}</title>\n'
            f'  <style>:root{{--silh:{SILH};--accent:{ACCENT};--indigo:{INDIGO};}}</style>\n')


def rrect(x0, y0, x1, y1, r, fill):
    return (f'<rect x="{x0*S:.2f}" y="{y0*S:.2f}" width="{(x1-x0)*S:.2f}" '
            f'height="{(y1-y0)*S:.2f}" rx="{r*S:.2f}" fill="{fill}"/>')


def circle(cx, cy, r, fill):
    return f'<circle cx="{cx*S:.2f}" cy="{cy*S:.2f}" r="{r*S:.2f}" fill="{fill}"/>'


# ----------------------------------------------------------------- A: helm
def svg_helm():
    body = []
    body += arc(0.50, 0.335, 0.265, 0.235, 180, 360, 40)
    body += [P(0.765, 0.34), P(0.74, 0.62), P(0.715, 0.86)]
    body += arc(0.655, 0.86, 0.06, 0.06, 0, 90, 10)
    body += [P(0.345, 0.92)]
    body += arc(0.345, 0.86, 0.06, 0.06, 90, 180, 10)
    body += [P(0.285, 0.86), P(0.26, 0.62), P(0.235, 0.34)]
    # visor bars
    vx0, vy0, vy1 = 0.285, 0.40, 0.50
    n, pad = 7, 0.012
    bw = (0.715 - vx0 - pad * 2) / (n * 1.6)
    gap = bw * 0.6
    heights = [0.22, 0.35, 0.5, 0.68, 0.55, 0.82, 1.0]
    bars = []
    bx = vx0 + pad
    for i in range(n):
        h = heights[i] * (vy1 - vy0 - 0.012)
        y1 = vy1 - 0.006
        bars.append(rrect(bx, y1 - h, bx + bw, y1, 0.004, "var(--accent)"))
        bx += bw + gap
    dots = [(0.40, 0.66), (0.455, 0.69), (0.50, 0.705), (0.545, 0.69), (0.60, 0.66)]
    dotsvg = "".join(circle(nx, ny, 0.013, "var(--accent)") for nx, ny in dots)
    s = header("Visor Gauge helm")
    s += ('  <defs>\n'
          '    <mask id="helmMask">\n'
          '      <rect width="1000" height="1000" fill="white"/>\n'
          # crescent cut
          f'      <circle cx="{0.385*S}" cy="{0.255*S}" r="{0.093*S}" fill="black"/>\n'
          f'      <circle cx="{(0.385+0.058)*S}" cy="{(0.255-0.006)*S}" r="{0.090*S}" fill="white"/>\n'
          # visor slot cut
          f'      <rect x="{0.285*S}" y="{0.40*S}" width="{(0.715-0.285)*S}" height="{(0.50-0.40)*S}" rx="{0.02*S}" fill="black"/>\n'
          '    </mask>\n  </defs>\n')
    s += f'  <g mask="url(#helmMask)">{poly(body, "var(--silh)")}</g>\n'
    s += f'  <rect x="{0.494*S}" y="{0.11*S}" width="{0.012*S}" height="{0.19*S}" fill="var(--silh)"/>\n'
    s += "  " + "".join(bars) + "\n"
    s += "  " + dotsvg + "\n</svg>\n"
    return s


# ----------------------------------------------------------------- B: knight
def svg_knight():
    knight = [P(0.545, 0.115), P(0.455, 0.175), P(0.375, 0.255), P(0.305, 0.315),
              P(0.235, 0.360), P(0.195, 0.420), P(0.225, 0.470), P(0.300, 0.495),
              P(0.355, 0.520), P(0.395, 0.600), P(0.420, 0.700), P(0.415, 0.800),
              P(0.360, 0.800), P(0.330, 0.885), P(0.690, 0.885), P(0.660, 0.800),
              P(0.585, 0.800), P(0.600, 0.560), P(0.590, 0.300), P(0.600, 0.175),
              P(0.560, 0.095)]
    n, t0, t1, base_x = 6, 0.80, 0.235, 0.585
    heights = [0.045, 0.065, 0.085, 0.105, 0.085, 0.060]
    bar_h = (t0 - t1) / n
    bars = []
    for i in range(n):
        ny0 = t0 - (i + 1) * bar_h + bar_h * 0.12
        ny1 = t0 - i * bar_h - bar_h * 0.12
        bars.append(rrect(base_x, ny0, base_x + heights[i], ny1, 0.006, "var(--accent)"))
    s = header("Chess Knight Sparkline")
    s += "  " + poly(knight, "var(--silh)") + "\n"
    s += "  " + "".join(bars) + "\n"
    s += "  " + circle(0.360, 0.330, 0.020, "var(--indigo)") + "\n</svg>\n"
    return s


# ----------------------------------------------------------------- C: shield
def svg_shield():
    shield = [P(0.26, 0.195), P(0.74, 0.195), P(0.745, 0.42)]
    shield += arc(0.50, 0.42, 0.245, 0.47, 0, 90, 28)
    shield += arc(0.50, 0.42, 0.245, 0.47, 90, 180, 28)
    shield += [P(0.255, 0.42)]
    # load bar
    tx0, tx1, ty0, ty1 = 0.335, 0.665, 0.455, 0.525
    track = rrect(tx0, ty0, tx1, ty1, 0.03, "var(--indigo)")
    fx1 = tx0 + (tx1 - tx0) * 0.64
    fill = rrect(tx0 + 0.006, ty0 + 0.006, fx1, ty1 - 0.006, 0.025, "var(--accent)")
    # ramp
    ramp_base, bw2 = 0.415, 0.052
    bars = []
    for i, nx in enumerate([0.345, 0.418, 0.491, 0.564, 0.637]):
        h = 0.045 + i * 0.038
        bars.append(rrect(nx, ramp_base - h, nx + bw2, ramp_base, 0.006, "var(--accent)"))
    s = header("Shield Load-Bar")
    s += "  " + poly(shield, "var(--silh)") + "\n"
    s += "  " + track + fill + "\n"
    s += "  " + "".join(bars) + "\n"
    # crescent plume (mask)
    mcx, mcy, mr = 0.50, 0.135, 0.058
    s += ('  <defs><mask id="plume">'
          f'<circle cx="{mcx*S}" cy="{mcy*S}" r="{mr*S}" fill="white"/>'
          f'<circle cx="{(mcx+0.028)*S}" cy="{(mcy-0.018)*S}" r="{0.052*S}" fill="black"/>'
          '</mask></defs>\n')
    s += f'  <circle cx="{mcx*S}" cy="{mcy*S}" r="{mr*S}" fill="var(--accent)" mask="url(#plume)"/>\n</svg>\n'
    return s


# ----------------------------------------------------------------- monogram
def svg_monogram():
    stem = rrect(0.255, 0.20, 0.355, 0.80, 0.02, "var(--silh)")
    topbars = [(0.44, 0.40, 0.085), (0.545, 0.30, 0.115), (0.655, 0.185, 0.145)]
    bars = []
    for bx, by, bh in topbars:
        bars.append(rrect(bx, by, bx + 0.085, by + bh + 0.14, 0.014, "var(--accent)"))
    lower = [P(0.355, 0.47), P(0.455, 0.49), P(0.725, 0.80), P(0.585, 0.80), P(0.355, 0.565)]
    mcx, mcy, mr = 0.475, 0.49, 0.055
    s = header("monogram K")
    s += "  " + stem + "\n"
    s += "  " + "".join(bars) + "\n"
    s += "  " + poly(lower, "var(--silh)") + "\n"
    s += ('  <defs><mask id="counter">'
          f'<circle cx="{mcx*S}" cy="{mcy*S}" r="{mr*S}" fill="white"/>'
          f'<circle cx="{(mcx+0.030)*S}" cy="{(mcy-0.014)*S}" r="{0.050*S}" fill="black"/>'
          '</mask></defs>\n')
    s += f'  <circle cx="{mcx*S}" cy="{mcy*S}" r="{mr*S}" fill="var(--accent)" mask="url(#counter)"/>\n</svg>\n'
    return s


def main():
    files = {
        "knightload-mark-A-visor-gauge.svg": svg_helm(),
        "knightload-mark-B-chess-knight-sparkline.svg": svg_knight(),
        "knightload-mark-C-shield-loadbar.svg": svg_shield(),
        "knightload-monogram.svg": svg_monogram(),
    }
    for name, body in files.items():
        with open(os.path.join(OUT, name), "w") as f:
            f.write(body)
        print("  ", name, len(body), "bytes")
    print("done ->", OUT)


if __name__ == "__main__":
    main()
