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
(transparent, dark-optimised; full light/reversed SVG set ships with the final suite).

## Next (on board pick)

Final suite for the chosen direction: primary horizontal lockup, stacked lockup, icon-only
mark, monochrome + reversed-on-dark, favicon, and a social/OG card — transparent **PNG + SVG**
each, plus `Knightload Engine` / `Knightload Skills` lockups.

> Regeneration: `python3 gen_concepts.py` (toolkit `kl_brand.py`). Pure-Pillow + DejaVu, no
> cairo/resvg — same stack as ISI-5724.
