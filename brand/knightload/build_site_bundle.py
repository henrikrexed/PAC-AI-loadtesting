#!/usr/bin/env python3
"""build_site_bundle.py — WS-1 (ISI-5791): brand -> GitHub Pages web bundle.

Takes the locked Signal Diamond final suite (ISI-5779, brand/knightload/final/) and
emits a drop-in bundle for the Docusaurus Pages site (WS-2) under `site/`:

  logos/      navbar lockups (dark + light SVG) and the mark
  favicons/   favicon.svg + favicon.ico (16/32/48, 3-bar simplified small sizes) +
              apple-touch-icon + PWA icons (192/512) + full PNG set
  social/     og-card.png (1200x630, Space Grotesk wordmark)
  site.webmanifest
  mermaid-theme.json   on-brand Mermaid themeVariables (dark + light)

Pure-Pillow (no cairo/resvg). Reproducible: re-run after any brand change.
Font: Space Grotesk / Sora are vendored in fonts/ so the raster wordmark is the
production face (publish-time item #1), not the DejaVu stand-in.
"""
import os
import shutil
import struct
import io
from PIL import Image

import kl_brand as k
import kl_signal as s
import kl_final as f

HERE = os.path.dirname(__file__)
FINAL = os.path.join(HERE, "final")
SITE = os.path.join(HERE, "site")

CYAN, AMBER, SILVER = k.CYAN, k.AMBER, k.SILVER
INDIGO0, INDIGO1, INDIGO2 = k.INDIGO0, k.INDIGO1, k.INDIGO2

FONT = "'Space Grotesk','Sora','Segoe UI',system-ui,sans-serif"


def _hex(rgb):
    return "#%02X%02X%02X" % rgb


def fresh(d):
    if os.path.isdir(d):
        shutil.rmtree(d)
    os.makedirs(d, exist_ok=True)


# ---------------------------------------------------------------- favicon.ico
def build_ico(path, sources):
    """Write a multi-resolution ICO embedding PNG entries (Vista+/all modern
    browsers). `sources` = list of (size, png_path); each PNG is embedded verbatim
    so the hand-tuned 3-bar small sizes stay crisp."""
    imgs = []
    for size, src in sources:
        im = Image.open(src).convert("RGBA")
        if im.size != (size, size):
            im = im.resize((size, size), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, format="PNG")
        imgs.append((size, buf.getvalue()))

    n = len(imgs)
    out = bytearray()
    out += struct.pack("<HHH", 0, 1, n)                 # reserved, type=icon, count
    offset = 6 + 16 * n
    for size, data in imgs:
        w = 0 if size >= 256 else size
        h = 0 if size >= 256 else size
        out += struct.pack("<BBBBHHII", w, h, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    for _, data in imgs:
        out += data
    with open(path, "wb") as fh:
        fh.write(out)
    print("  favicon.ico", [s for s, _ in imgs])


# ---------------------------------------------------------------- light-mode SVG
def onlight_svg():
    """Light-mode navbar lockup: dark-navy diamond (reads on white) + indigo
    wordmark. Matches the board-accepted knightload-lockup-horizontal-onlight.png
    (monochrome indigo wordmark). Transparent bg so it adapts to the navbar tint."""
    dia = open(os.path.join(FINAL, "knightload-icon.svg")).read()
    import kl_final_svg as fs
    return fs.lockup_horizontal(dia, accent=_hex(INDIGO0), silver=_hex(INDIGO0),
                                tagline=True)


# ---------------------------------------------------------------- webmanifest
WEBMANIFEST = """{
  "name": "Knightload",
  "short_name": "Knightload",
  "description": "Stop guessing. The signal shows the load. — observability-driven load testing.",
  "icons": [
    { "src": "/img/favicons/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/img/favicons/icon-512.png", "sizes": "512x512", "type": "image/png" },
    { "src": "/img/favicons/favicon.svg", "type": "image/svg+xml", "purpose": "any" }
  ],
  "theme_color": "#16213E",
  "background_color": "#1A1A2E",
  "display": "standalone",
  "start_url": "/"
}
"""


# ---------------------------------------------------------------- brand token CSS
# WS-1 owns the brand token layer. Maps the Signal Diamond palette onto Infima
# (Docusaurus) variables + raw --kl-* custom props. Light-mode uses an accessible
# darkened teal for link/primary contrast (bright teal fails AA on white); dark-mode
# uses the full bright teal accent. Headings = Space Grotesk, body = Sora.
CUSTOM_CSS = """/* Knightload — Signal Diamond brand tokens (ISI-5791 / WS-1).
 * Drop into src/css/custom.css (or @import it). Pairs with @fontsource/space-grotesk
 * + @fontsource/sora (recommended) or the vendored TTFs in static/fonts/. */

/* ---- raw brand palette (single source of truth) ---- */
:root {
  --kl-indigo-0: #1A1A2E;   /* darkest night / page bg (dark) */
  --kl-indigo-1: #16213E;   /* indigo surface / navbar (dark) */
  --kl-indigo-2: #212E50;   /* raised surface */
  --kl-silver:   #C7CDD6;   /* text on dark */
  --kl-teal:     #2EE6D6;   /* primary accent (the signal glow) */
  --kl-teal-700: #0C7D73;   /* accessible teal for links on light (AA on white) */
  --kl-amber:    #FFB23E;   /* alternate accent / callouts */
  --kl-mute:     #96A0B2;   /* muted labels */

  --ifm-font-family-base: 'Sora', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
  --ifm-heading-font-family: 'Space Grotesk', 'Sora', system-ui, sans-serif;
  --ifm-code-font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace;
}

/* ---- light mode (default) ---- */
:root {
  --ifm-color-primary: var(--kl-teal-700);
  --ifm-color-primary-dark: #0b7169;
  --ifm-color-primary-darker: #0a6b63;
  --ifm-color-primary-darkest: #085851;
  --ifm-color-primary-light: #0d897d;
  --ifm-color-primary-lighter: #0e8f83;
  --ifm-color-primary-lightest: #119e90;

  --ifm-background-color: #ffffff;
  --ifm-background-surface-color: #f3f6fa;
  --ifm-navbar-background-color: #ffffff;
  --ifm-heading-color: var(--kl-indigo-1);
  --ifm-link-color: var(--kl-teal-700);
  --ifm-menu-color-active: var(--kl-teal-700);
  --docusaurus-highlighted-code-line-bg: rgba(46, 230, 214, 0.12);
}

/* ---- dark mode (the brand's native key) ---- */
[data-theme='dark'] {
  --ifm-color-primary: var(--kl-teal);
  --ifm-color-primary-dark: #1ad9c8;
  --ifm-color-primary-darker: #18cdbd;
  --ifm-color-primary-darkest: #13a89b;
  --ifm-color-primary-light: #47e9db;
  --ifm-color-primary-lighter: #54ebdd;
  --ifm-color-primary-lightest: #79f0e6;

  --ifm-background-color: var(--kl-indigo-0);
  --ifm-background-surface-color: var(--kl-indigo-1);
  --ifm-navbar-background-color: var(--kl-indigo-1);
  --ifm-heading-color: var(--kl-silver);
  --ifm-font-color-base: #d7dce4;
  --ifm-link-color: var(--kl-teal);
  --ifm-menu-color-active: var(--kl-teal);
  --docusaurus-highlighted-code-line-bg: rgba(46, 230, 214, 0.15);
}

/* navbar logo: SVG lockup swaps with theme via logo.src / logo.srcDark */
.navbar__logo { height: 2rem; }

/* optional: vendored self-hosted fonts (if not using @fontsource) */
/* @font-face { font-family:'Space Grotesk'; font-weight:300 700; font-display:swap;
     src:url('/fonts/SpaceGrotesk-VF.ttf') format('truetype-variations'); }
   @font-face { font-family:'Sora'; font-weight:100 800; font-display:swap;
     src:url('/fonts/Sora-VF.ttf') format('truetype-variations'); } */
"""


# ---------------------------------------------------------------- mermaid theme
def mermaid_theme():
    """On-brand Mermaid themeVariables for both Docusaurus (@docusaurus/theme-mermaid
    themeConfig.mermaid.options) and raw GitHub `%%{init}%%` blocks. base theme so
    every variable is honoured. Palette locked to the Signal Diamond brand."""
    import json
    C = {
        "indigo0": _hex(INDIGO0),   # #16213E  primary surface (dark)
        "indigo1": _hex(INDIGO1),   # #1A1A2E  darkest night
        "indigo2": _hex(INDIGO2),   # node fill mid
        "silver": _hex(SILVER),     # #C7CDD6  text on dark
        "teal": _hex(CYAN),         # #2EE6D6  accent / primary border + lines
        "amber": _hex(AMBER),       # #FFB23E  alternate accent / notes
        "mute": "#96A0B2",
    }
    dark = {
        "darkMode": True,
        "background": "transparent",
        "fontFamily": FONT,
        "primaryColor": C["indigo2"],
        "primaryTextColor": C["silver"],
        "primaryBorderColor": C["teal"],
        "secondaryColor": C["indigo0"],
        "secondaryTextColor": C["silver"],
        "secondaryBorderColor": C["mute"],
        "tertiaryColor": C["indigo1"],
        "tertiaryTextColor": C["silver"],
        "tertiaryBorderColor": C["mute"],
        "lineColor": C["teal"],
        "textColor": C["silver"],
        "mainBkg": C["indigo2"],
        "nodeBorder": C["teal"],
        "clusterBkg": C["indigo1"],
        "clusterBorder": C["mute"],
        "titleColor": C["silver"],
        "edgeLabelBackground": C["indigo1"],
        "nodeTextColor": C["silver"],
        # notes / callouts -> amber alt accent
        "noteBkgColor": C["amber"],
        "noteTextColor": C["indigo1"],
        "noteBorderColor": C["amber"],
        # sequence
        "actorBkg": C["indigo2"],
        "actorBorder": C["teal"],
        "actorTextColor": C["silver"],
        "actorLineColor": C["mute"],
        "signalColor": C["silver"],
        "signalTextColor": C["silver"],
        "labelBoxBkgColor": C["indigo0"],
        "labelBoxBorderColor": C["teal"],
        "labelTextColor": C["silver"],
        "loopTextColor": C["silver"],
        "activationBkgColor": C["teal"],
        "activationBorderColor": C["teal"],
        # state / flow extras
        "errorBkgColor": C["amber"],
        "errorTextColor": C["indigo1"],
    }
    light = dict(dark)
    light.update({
        "darkMode": False,
        "background": "transparent",
        "primaryColor": "#EEF1F6",
        "primaryTextColor": C["indigo0"],
        "primaryBorderColor": C["indigo0"],
        "secondaryColor": "#DCE3EC",
        "secondaryTextColor": C["indigo0"],
        "secondaryBorderColor": C["mute"],
        "tertiaryColor": "#F3F6FA",
        "tertiaryTextColor": C["indigo0"],
        "tertiaryBorderColor": C["mute"],
        "lineColor": C["indigo0"],
        "textColor": C["indigo0"],
        "mainBkg": "#EEF1F6",
        "nodeBorder": C["indigo0"],
        "clusterBkg": "#F3F6FA",
        "clusterBorder": C["mute"],
        "titleColor": C["indigo0"],
        "edgeLabelBackground": "#FFFFFF",
        "nodeTextColor": C["indigo0"],
        "noteBkgColor": C["amber"],
        "noteTextColor": C["indigo1"],
        "noteBorderColor": "#E09A24",
        "actorBkg": "#EEF1F6",
        "actorBorder": C["indigo0"],
        "actorTextColor": C["indigo0"],
        "actorLineColor": C["mute"],
        "signalColor": C["indigo0"],
        "signalTextColor": C["indigo0"],
        "labelBoxBkgColor": "#EEF1F6",
        "labelBoxBorderColor": C["indigo0"],
        "labelTextColor": C["indigo0"],
        "activationBkgColor": "#0FB5A6",
        "activationBorderColor": "#0FB5A6",
    })
    return {
        "_comment": "Knightload Signal Diamond Mermaid theme (ISI-5791 / WS-1). "
                    "Use `dark`/`light` under Docusaurus themeConfig.mermaid.options, "
                    "or paste `initDark`/`initLight` into a %%{init}%% block on GitHub.",
        "palette": C,
        "dark": {"theme": "base", "themeVariables": dark},
        "light": {"theme": "base", "themeVariables": light},
        "initDark": {"theme": "base", "themeVariables": dark},
        "initLight": {"theme": "base", "themeVariables": light},
    }


# ---------------------------------------------------------------- mermaid usage doc
def mermaid_usage(theme):
    import json
    init_dark = "%%{init: " + json.dumps(theme["initDark"], separators=(",", ":")) + " }%%"
    return f"""# Knightload Mermaid theme — usage (ISI-5791 / WS-1)

On-brand Mermaid palette for the Signal Diamond brand. Two consumption paths.

## 1. Docusaurus site (`@docusaurus/theme-mermaid`)

Docusaurus renders Mermaid live and already switches with the color mode. Point the
two themeVariables sets from `mermaid-theme.json` at light/dark in `docusaurus.config`:

```js
// npm i @docusaurus/theme-mermaid ; markdown.mermaid = true ; themes:['@docusaurus/theme-mermaid']
const kl = require('./static/img/mermaid-theme.json'); // or wherever WS-2 places it
themeConfig: {{
  mermaid: {{
    theme: {{ light: 'base', dark: 'base' }},
    options: kl.dark.themeVariables, // Docusaurus applies one set; use dark (brand key)
  }},
}}
```

Docusaurus applies a single `options` object regardless of color mode, so use the
**dark** set (the brand's native key) and let the `base` theme + transparent
backgrounds sit on the page surface. For true per-mode variables, WS-2 can inject
`light`/`dark` via a small client module keyed on `[data-theme]`.

## 2. Raw GitHub / README (`%%{{init}}%%`)

GitHub renders Mermaid but has no Knightload theme — prepend an init directive to each
diagram. Dark variant (GitHub READMEs render on a dark-ish surface):

```
{init_dark}
flowchart LR
  A[Model] --> B{{Engine}} --> C[k6 / JMeter / Locust / Gatling]
```

(The light variant — `initLight` in `mermaid-theme.json` — is available for light
contexts.) Keep the directive on the first line of the code block.

## Palette reference

| token | hex | role |
|---|---|---|
| indigo-0 | {_hex(INDIGO0)} | darkest night / page bg |
| indigo-1 | {_hex(INDIGO1)} | indigo surface / node fill-dark |
| indigo-2 | {_hex(INDIGO2)} | raised node fill |
| silver | {_hex(SILVER)} | text on dark |
| teal | {_hex(CYAN)} | primary accent / edges (dark) |
| amber | {_hex(AMBER)} | notes / callouts / errors |
| mute | #96A0B2 | secondary borders / labels |

Edges/lines use **teal** on dark and **indigo** on light; notes use **amber**.
"""


HANDOFF = """# Knightload brand -> Pages web bundle (WS-1 / ISI-5791)

Drop-in brand assets + theme tokens for the Docusaurus Pages site
(`github.com/henrikrexed/AI-Performance-Testing`). Source of truth: the locked
**Signal Diamond** final suite (ISI-5779, `brand/knightload/final/`). Regenerate the
whole bundle with `python3 build_site_bundle.py` (pure-Pillow, no cairo/resvg).

## What's in here

```
site/
  logos/
    knightload-lockup-horizontal.svg           navbar logo — DARK mode (silver+teal, transparent)
    knightload-lockup-horizontal-onlight.svg   navbar logo — LIGHT mode (indigo wordmark)
    knightload-lockup-horizontal-onindigo.svg  lockup baked on indigo (hero/footer)
    knightload-icon.svg / -icon-mono.svg       standalone mark (colour / monochrome)
    *.png                                      raster lockups (Space Grotesk) as fallback
  favicons/
    favicon.svg                                modern scalable favicon
    favicon.ico                                multi-res 16/32/48 (3-bar simplified at 16/32)
    favicon-16/32.png                          3-bar simplified (crisp small sizes)
    favicon-48/64/256.png, icon-192/512.png    full 5-bar PNG set + PWA icons
    apple-touch-icon.png                       180x180
  social/
    og-card.png                                1200x630 social/OG preview
  fonts/
    SpaceGrotesk-VF.ttf, Sora-VF.ttf           vendored OFL fonts (+ OFL licenses)
  custom-brand.css                             Infima/Docusaurus brand tokens (light+dark)
  mermaid-theme.json                           Mermaid themeVariables (light + dark + %%init%%)
  mermaid-usage.md                             how to wire Mermaid (Docusaurus + GitHub)
  site.webmanifest                             PWA manifest
```

## Wiring guide (WS-2 / DevOps)

- **Navbar logo** — `themeConfig.navbar.logo = { src: '.../knightload-lockup-horizontal-onlight.svg',
  srcDark: '.../knightload-lockup-horizontal.svg', alt: 'Knightload' }`. SVGs carry the
  real font stack (`'Space Grotesk','Sora',...`) so they render crisp without the webfont,
  and sharper with it.
- **Favicons / head** — favicon.svg (modern) + favicon.ico (legacy) + apple-touch-icon +
  `site.webmanifest`. In Docusaurus set `favicon: 'img/favicons/favicon.ico'` and add the
  svg/apple-touch/manifest links via `headTags`.
- **Brand tokens** — import `custom-brand.css` from `src/css/custom.css`. Headings render in
  Space Grotesk, body in Sora. Load the fonts with `@fontsource/space-grotesk` +
  `@fontsource/sora` (recommended) or the vendored TTFs in `fonts/` via the commented
  `@font-face` block.
- **Mermaid** — see `mermaid-usage.md`. `mermaid-theme.json` has `light`/`dark`
  themeVariables and ready `%%{init}%%` objects.
- **OG card** — `social/og-card.png` for `og:image` / `twitter:image` (1200x630).

## Accessibility note (deliberate)

Bright teal `#2EE6D6` is the accent on **dark** surfaces (its native key). On **light**
surfaces links/primary use a darkened teal `#0C7D73` for AA contrast on white — bright teal
is reserved for accents/borders there, not text. Both are the same brand hue.

## Scope boundary

WS-1 (this bundle) = brand assets + theme tokens. WS-2 owns the Docusaurus scaffold,
site structure, diagram authoring, and the Pages deploy. No logo choice remains —
Signal Diamond is locked.
"""


# ---------------------------------------------------------------- main
def main():
    fresh(SITE)
    logos = os.path.join(SITE, "logos")
    favs = os.path.join(SITE, "favicons")
    social = os.path.join(SITE, "social")
    for d in (logos, favs, social):
        os.makedirs(d, exist_ok=True)

    print("logos...")
    # dark-mode navbar (silver + teal on transparent) and the standalone mark
    for name in ("knightload-lockup-horizontal.svg",
                 "knightload-lockup-horizontal-onindigo.svg",
                 "knightload-icon.svg", "knightload-icon-mono.svg"):
        shutil.copy(os.path.join(FINAL, name), os.path.join(logos, name))
    # light-mode navbar lockup (generated)
    with open(os.path.join(logos, "knightload-lockup-horizontal-onlight.svg"), "w") as fh:
        fh.write(onlight_svg())
    # raster lockups (Space Grotesk) for anywhere SVG is awkward
    for name in ("knightload-lockup-horizontal.png",
                 "knightload-lockup-horizontal-onlight.png"):
        shutil.copy(os.path.join(FINAL, name), os.path.join(logos, name))
    print("   dark svg + light svg + onindigo + mark + raster")

    print("favicons...")
    # modern scalable favicon
    shutil.copy(os.path.join(FINAL, "knightload-icon.svg"),
                os.path.join(favs, "favicon.svg"))
    # full PNG set + 3-bar simplified small sizes
    pngset = {
        "favicon-16.png": "knightload-favicon-16-simple.png",   # 3-bar at 16
        "favicon-32.png": "knightload-favicon-32-simple.png",   # 3-bar at 32
        "favicon-48.png": "knightload-favicon-48.png",
        "favicon-64.png": "knightload-favicon-64.png",
        "favicon-256.png": "knightload-favicon-256.png",
        "icon-512.png": "knightload-favicon-512.png",
        "apple-touch-icon.png": "knightload-favicon-180.png",   # 180x180
    }
    for dst, src in pngset.items():
        shutil.copy(os.path.join(FINAL, src), os.path.join(favs, dst))
    # PWA 192 (resize from 512)
    Image.open(os.path.join(FINAL, "knightload-favicon-512.png")).convert("RGBA") \
        .resize((192, 192), Image.LANCZOS).save(os.path.join(favs, "icon-192.png"))
    # multi-res .ico (crisp 3-bar 16/32 + full 48)
    build_ico(os.path.join(favs, "favicon.ico"), [
        (16, os.path.join(FINAL, "knightload-favicon-16-simple.png")),
        (32, os.path.join(FINAL, "knightload-favicon-32-simple.png")),
        (48, os.path.join(FINAL, "knightload-favicon-48.png")),
    ])

    print("social...")
    shutil.copy(os.path.join(FINAL, "knightload-og-card.png"),
                os.path.join(social, "og-card.png"))

    print("fonts...")
    fdir = os.path.join(SITE, "fonts")
    os.makedirs(fdir, exist_ok=True)
    for fn in ("SpaceGrotesk-VF.ttf", "Sora-VF.ttf", "OFL-SpaceGrotesk.txt", "OFL-Sora.txt"):
        src = os.path.join(HERE, "fonts", fn)
        if os.path.isfile(src):
            shutil.copy(src, os.path.join(fdir, fn))

    print("manifest + css + mermaid + docs...")
    with open(os.path.join(SITE, "site.webmanifest"), "w") as fh:
        fh.write(WEBMANIFEST)
    with open(os.path.join(SITE, "custom-brand.css"), "w") as fh:
        fh.write(CUSTOM_CSS)
    import json
    theme = mermaid_theme()
    with open(os.path.join(SITE, "mermaid-theme.json"), "w") as fh:
        json.dump(theme, fh, indent=2)
    with open(os.path.join(SITE, "mermaid-usage.md"), "w") as fh:
        fh.write(mermaid_usage(theme))
    with open(os.path.join(SITE, "HANDOFF.md"), "w") as fh:
        fh.write(HANDOFF)

    print("done ->", SITE)


if __name__ == "__main__":
    main()
