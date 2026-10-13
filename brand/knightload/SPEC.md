# Knightload — Logo & Brand Mark Spec (ISI-5779)

**Status:** Stage 1 — concept directions for board pick. Final family follows the pick.
Parent naming decision: [ISI-5766](/ISI/issues/ISI-5766) → "Round 3 — Logo direction".

## Brand essence
- **Knight** — guardian of performance; chess-knight strategy (the L-move).
- **Night** — origin story: load tests run through the night for external clients.
- **Load** — throughput / ramp metrics grounded in observed reality → *"Stop guessing."*

## Concept directions (pick one)
| | Concept | Mark idea |
|---|---|---|
| **A** | **Visor Gauge** | Knight great-helm in profile; visor slits = ascending load bars; crescent moon carved into the dome (negative space). |
| **B** | **Chess Knight Sparkline** | Chess-knight head; the mane doubles as a throughput sparkline / bar chart; the knight's L-move nods to "Load". |
| **C** | **Shield Load-Bar** | Heater shield with a filling load bar + ascending ramp; crescent-moon plume at the crest. |

**Shared app-icon monogram:** a "K" whose upper arm is built from ascending bars, with a crescent-moon counter in the junction negative space. Works with any of the three.

**Designer recommendation: Concept B (Chess Knight Sparkline).** Most ownable and
immediately legible — it fuses all three essence pillars (chess knight + L-move +
data sparkline) in one silhouette, scales to favicon size, and has the lowest
"accidental read" risk. A is a strong runner-up (the helm reads as a performance
guardian); C is the most literal/corporate.

## Palette
| Role | Hex | Name |
|---|---|---|
| Deepest midnight | `#1A1A2E` | midnight |
| Primary background | `#16213E` | midnight indigo |
| Primary mark on dark | `#C7CDD6` | brushed silver |
| Primary accent | `#2EE6D6` | electric cyan |
| Alternate accent | `#FFB23E` | amber |

One accent per application. Cyan is the default; amber is the alternate (e.g. a
second product line or dark-tile app icon). Aligned with the ISI-5724 Matrix deck
system so assets reuse cleanly.

## Typography
- **Wordmark:** geometric modern sans — **Space Grotesk** or **Sora**, Bold.
  Two-tone lockup: `Knight` in silver, `load` in the accent.
- **Tagline:** *"Stop guessing. Load with proof."* — regular weight, muted.
- No blackletter. Wordmark must stay legible at small sizes.

> ⚠ **Font note (host constraint):** this host has no cairo/resvg and no
> Space Grotesk/Sora installed — same as the ISI-5724 deck. Every **rasterized
> wordmark PNG uses DejaVu Sans Bold as a faithful stand-in**. Swap to
> Space Grotesk/Sora before production publish. The **icon marks are pure vector
> geometry → production-true**; SVG twins ship in `svg/`.

## Clear space & minimum size
- Clear space ≥ the height of the monogram's crescent counter on all sides.
- Icon-only mark legible down to **32 px** (favicon provided at 32/64/180).
- Wordmark lockup minimum height **40 px**.

## Deliverables
**Stage 1 (this delivery — all three concepts):**
- `png/knightload-concept-board.png` — the board-pick sheet.
- `png/mark-{A,B,C}-{ondark,transparent,mono,reversed}.png`
- `png/lockup-{A,B,C}-{horizontal,stacked}.png`
- `png/appicon-{indigo,amber}.png`, `png/monogram-transparent.png`, `png/favicon-{32,64,180}.png`
- `png/palette.png`
- `svg/knightload-mark-{A,B,C}-*.svg`, `svg/knightload-monogram.svg` — production-true vector.

**Stage 2 (after board picks ONE concept):** full locked family for the winner —
primary horizontal lockup, stacked lockup, icon-only, monochrome + reversed-on-dark,
favicon set, social/OG card, plus `Knightload Engine` and `Knightload Skills` lockups,
all in transparent **PNG + SVG**, with the Space Grotesk/Sora font swapped in.

## Regenerating
```
python3 kl_render.py   # all PNGs -> png/
python3 kl_svg.py      # production SVG twins -> svg/
```
`kl_brand.py` holds the pure-geometry mark functions (single source of truth for
both PNG and SVG). `kl_svg.py` mirrors the same normalized coordinates on a
0–1000 viewBox with `<mask>` for negative-space cuts.
