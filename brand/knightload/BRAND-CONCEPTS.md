# Knightload — logo concepts (ISI-5779, round 1 · board pick)

**Brand essence:** **Knight** (guardian of performance / chess-knight strategy) ·
**Night** (load tests run through the night for external clients — the origin story) ·
**Load** (throughput & ramp grounded in observed reality — *"Stop guessing"*).

Three directions below. **Board picks one** (plus an accent); I then produce the full
final suite from the winner. All marks are font-free vector geometry (production-true in
both PNG and SVG). Wordmarks are shown in **DejaVu Bold as a stand-in** — production swaps
to **Space Grotesk / Sora** at build (host has no Space Grotesk; same constraint as the
Matrix deck, ISI-5724).

## Concepts

| | Concept | Idea |
|---|---|---|
| **A** ⭐ | **Visor Gauge** *(primary rec)* | Knight great-helm, frontal. The visor slit becomes a row of **ascending load bars** (throughput waveform); a **crescent moon** is carved from the dome in negative space. |
| **B** | **Chess Knight Sparkline** | Chess-knight head silhouette; the **mane doubles as a bar sparkline**. The knight's L-move nods to "Load." |
| **C** | **Shield Load-Bar** | Heater shield (guardian stance) with a **filling load bar** + ascending ramp ticks and a **crescent-moon plume** at the crest. |

**App icon / monogram:** a **"K"** whose arms are ascending bars, with a **crescent-moon
counter** in the junction (shown on a midnight-indigo tile).

**Designer note on the pick:** the brief names **A (Visor Gauge)** the primary rec and it
is the cleanest "guardian of performance" read. The strongest *alternative* is **B (Chess
Knight Sparkline)** — the most ownable/distinctive silhouette, fusing chess-knight + L-move
+ data sparkline in one shape and scaling best to favicon size. Board decides; any of the
three ships from the same system.

## Visual system (starting point)

- **Colour:** midnight indigo `#1A1A2E` / `#16213E`, brushed silver `#C7CDD6`, and **one**
  bright accent — **electric cyan `#2EE6D6` (primary)** or **amber `#FFB23E` (alternate)**.
- **Type:** geometric modern sans — **Space Grotesk / Sora**. No blackletter.
- **Lockups:** `Knightload` · `Knightload Engine` · `Knightload Skills`.
- **Tagline (optional):** *"Stop guessing. Load from reality."*

## Deliverables in this round

Images (`brand/knightload/images/`):
- `knightload-concepts-overview.png` — the board-pick sheet (all 3 + monogram + palette)
- `knightload-concept-A-visor.png`, `-B-chess.png`, `-C-shield.png` — per-concept boards
  (primary mark + on-dark / on-light / monochrome / amber-alt variants + horizontal lockup)
- `knightload-visual-system.png` — palette, type, mark trio

Scalable source (`brand/knightload/svg/`): `knightload-mark-A-visor-gauge.svg`,
`-B-chess-knight-sparkline.svg`, `-C-shield-loadbar.svg`, `knightload-monogram.svg`
(0–1000 viewBox, themeable via `--silh` / `--accent` / `--indigo` CSS vars, negative-space
cuts via `<mask>`; full light/reversed SVG set ships with the final suite).

Raw production exports (`brand/knightload/png/`): clean per-mark cutouts
`mark-{A,B,C}-{ondark,transparent,mono,reversed}.png`, horizontal + stacked lockups
`lockup-{A,B,C}-{horizontal,stacked}.png`, app icons `appicon-{indigo,amber}.png`,
`monogram-transparent.png`, rasterised favicons `favicon-{32,64,180}.png`, and `palette.png`.

## Usage guardrails

- **One accent per application** — cyan is default; amber is the alternate line / tile.
- **Clear space** ≥ the height of the monogram's crescent counter on all sides.
- **Minimum size** — icon-only legible to **32 px** (favicons at 32/64/180); wordmark
  lockup minimum height **40 px**.
- Wordmark is two-tone: `Knight` silver, `load` accent. No blackletter.

## Next (on board pick)

Final suite for the chosen direction: primary horizontal lockup, stacked lockup, icon-only
mark, monochrome + reversed-on-dark, favicon, and a social/OG card — transparent **PNG + SVG**
each, plus `Knightload Engine` / `Knightload Skills` lockups, with **Space Grotesk / Sora**
swapped in for the wordmark.

> Regeneration (pure-Pillow + DejaVu, no cairo/resvg — same stack as ISI-5724), all on the
> shared `kl_brand.py` geometry toolkit:
> - `python3 gen_concepts.py` → presentation sheets in `images/`
> - `python3 kl_render.py` → raw production export PNGs in `png/`
> - `python3 kl_svg.py` → production SVG twins in `svg/`

---

## Round 3.2 — THE LOAD-SIGNAL (supersedes rounds 1 & 3.1)

Board origin (Henrik, 2026-10-13): Knightload was inspired by **Batman / The Dark
Knight** ("Alfred" the Paperclip agent is from the same universe). Creative key:
the **bat-signal reimagined as a LOAD-SIGNAL** — *"un K dans un rond ou losange"*.
At night the signal lights up, the knight answers. One mark fuses all pillars:
**Knight** (answers) · **Night** (when it shines) · **Load** (the signal IS the ramp).

The approved **round-3.1 Ramp-K** (`kl_k.k_ramp`) is housed inside the signal — so
this builds on the K Henrik liked rather than restarting.

Four directions (`kl_signal.py` → board `images/knightload-signal-board.png`):

| | Direction | Idea |
|---|---|---|
| 1 | Signal Circle | Glowing Ramp-K in a night roundel; halo + slim rising signal shaft. |
| 2 ⭐ | **Signal Diamond** *(recommended)* | Ramp-K knocked out of a glowing lozenge — projector beam, plot-point & badge in one. |
| 3 | Signal Minimal | Circle + K, thin stroke, monochrome. 16px-proof essence. |
| 4 | Signal K-Ray | The K's ramp arm fires off as a beam escaping the lozenge — load curve + signal. |

Guardrails honoured: 16px favicon tested (strip under each on the board; Dir 3 is the
16px champion), mandatory monochrome variant, **defensibly original** (geometric K +
abstract signal — no bat silhouette, no DC-trademark proximity), dark night palette +
**one** accent glow (teal default / amber alt).

Deliverables: board `images/knightload-signal-board.png`; raw exports `png/signal-*`
(per-direction on-dark/mono/amber, hero lockups diamond/circle, favicons 16–512);
SVG twins `svg/knightload-signal-*.svg` (gradients + beam, Ramp-K housed).

> Regeneration: `python3 kl_signal_render.py` (PNGs) · `python3 kl_signal_svg.py` (SVGs).
> Both on `kl_signal.py` (containers) + `kl_k.py` (approved Ramp-K glyph).
