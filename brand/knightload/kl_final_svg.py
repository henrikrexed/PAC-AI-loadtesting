#!/usr/bin/env python3
"""kl_final_svg.py — final SVG deliverables for the chosen Signal Diamond (ISI-5779).

Icon SVGs are the production-true vector marks (reused from kl_signal_svg). Lockups
embed the diamond as a nested <svg> and set the wordmark in real <text> with the
production font stack (Space Grotesk / Sora) + web-safe fallbacks."""
import os
import kl_signal_svg as g

HERE = os.path.dirname(__file__)
SVGDIR = os.path.join(HERE, "svg")
FINAL = os.path.join(HERE, "final")
os.makedirs(FINAL, exist_ok=True)

CYAN, AMBER, SILVER, INDIGO0, INDIGO1 = g.CYAN, g.AMBER, g.SILVER, g.INDIGO0, g.INDIGO1
SILVERDIM, MUTE = "#7880", "#96A0B2"
FONT = "'Space Grotesk','Sora','Segoe UI',system-ui,sans-serif"


def _inner(svg_text):
    """Return the diamond SVG body (everything after the opening <svg ...>)."""
    return svg_text.split(">", 1)[1]  # includes title/defs/shapes + </svg>


def nested(svg_text, x, y, size):
    return (f'<svg x="{x}" y="{y}" width="{size}" height="{size}" '
            f'viewBox="0 0 1000 1000">' + _inner(svg_text))


def wordmark_svg(x, baseline, px, accent=CYAN, sub=None, silver=SILVER):
    t = (f'<text x="{x}" y="{baseline}" font-family="{FONT}" font-weight="700" '
         f'font-size="{px}" letter-spacing="{px*0.01:.1f}">'
         f'<tspan fill="{silver}">Knight</tspan><tspan fill="{accent}">load</tspan>')
    if sub:
        t += f'<tspan fill="{MUTE}" font-weight="400"> {sub}</tspan>'
    t += '</text>'
    return t


def lockup_horizontal(diamond_svg, W=1400, H=420, accent=CYAN, sub=None,
                      bg=None, tagline=True, silver=SILVER):
    ic = int(H * 0.68); ix = int(H * 0.14)
    s = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="Knightload{(" "+sub) if sub else ""}">\n'
    s += f'  <title>Knightload{(" "+sub) if sub else ""}</title>\n'
    if bg:
        s += f'  <rect width="{W}" height="{H}" fill="{bg}"/>\n'
    s += "  " + nested(diamond_svg, ix, (H - ic) // 2, ic) + "\n"
    px = int(H * 0.30)
    tx = ix + ic + int(H * 0.13)
    baseline = H // 2 + int(px * 0.34)
    s += "  " + wordmark_svg(tx, baseline, px, accent, sub, silver) + "\n"
    if tagline and not sub:
        s += (f'  <text x="{tx+4}" y="{baseline + int(px*0.42)}" font-family="{FONT}" '
              f'font-size="{int(px*0.2)}" fill="{MUTE}">Stop guessing. The signal shows the load.</text>\n')
    s += "</svg>\n"
    return s


def main():
    dia = open(os.path.join(SVGDIR, "knightload-signal-2-diamond.svg")).read()
    dia_amber = open(os.path.join(SVGDIR, "knightload-signal-2-diamond-amber.svg")).read()
    dia_mono = open(os.path.join(SVGDIR, "knightload-signal-2-diamond-mono.svg")).read()

    out = {
        "knightload-icon.svg": dia,
        "knightload-icon-amber.svg": dia_amber,
        "knightload-icon-mono.svg": dia_mono,
        "knightload-lockup-horizontal.svg": lockup_horizontal(dia),
        "knightload-lockup-horizontal-onindigo.svg": lockup_horizontal(dia, bg=INDIGO1),
        "knightload-engine-lockup.svg": lockup_horizontal(dia, W=1600, sub="Engine", tagline=False),
        "knightload-skills-lockup.svg": lockup_horizontal(dia, W=1600, sub="Skills", tagline=False),
    }
    for name, body in out.items():
        with open(os.path.join(FINAL, name), "w") as f:
            f.write(body)
        print("  ", name, len(body), "bytes")
    print("done ->", FINAL)


if __name__ == "__main__":
    main()
