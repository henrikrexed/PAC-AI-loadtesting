# Knightload brand -> Pages web bundle (WS-1 / ISI-5791)

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
