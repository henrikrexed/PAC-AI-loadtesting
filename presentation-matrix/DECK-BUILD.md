# PAC deck — build & export (ISI-5794)

**Deliverable:** the final 21-slide Matrix deck, composed from the three completed workstreams,
exported projector/import-ready. Hand back to **ISI-5720** (assembly hub) for board review.

## What was built
- **`gen_deck.py`** — one reproducible generator for all 21 slides (2560×1440, 16:9), laying
  A's rev4 Part-4 copy onto B's board-accepted Matrix visual system (`mtx_theme` + d1–d5 diagrams).
- **`qr_util.py`** — real, scannable repo QR via `segno`.
- **`build_pdf.py` → `PAC-deck-matrix.pdf`** — 21-page PDF (order derived from `gen_deck.SLIDES`
  so the export can't drift from the generator). Imports cleanly into Keynote / Google Slides /
  PowerPoint (one full-bleed image per slide) and prints as speaker handouts.
- **`images/slide-01-title.png … slide-21-close.png`** — the 21 composed slides.

## Slide order (A's narrative order)
1 title · 2 blue-pill · 3 basics · **4 💬 Discussion #1** · 5 OTel · 6 sampling-trap *(the one glitch slide)* ·
7 RUM · 8 spans+RUM (d3) · 9 DQL · **10 💬 Discussion #2 — the ×1.27 reveal** · 11 skill · 12 engine (d2) ·
**13 architecture (d5)** · 14 one-model (d4) · **15–18 live demo** · 19 loop/Oracle (d1) · 20 limits ·
**21 💬 Discussion #3 + close**.

## Ship-gates
- **G1 — QR / repo links (slides 13 + 21).** The public mirror
  `github.com/henrikrexed/AI-Performance-Testing` is **LIVE** (verified HTTP 200, public, no login
  redirect). So the QR codes are **real and scannable**, not placeholders — slide 13 carries the
  repo QR baked into the d5 diagram (bottom-right); slide 21 carries a large scan-me QR on the CTA.
  The stale "QR placeholder — pending ISI-5659" caption was removed.
  - *Note for the board:* QR codes are themed (light modules on dark), matching the accepted visual
    system. Modern iOS/Android cameras read inverted QRs; if any council scanner fails, the fix is a
    one-line swap to dark-on-light. Links are also printed in plain text beside each QR.
- **G2 — live demo + recorded fallback.** Slides 15–18 carry the live-DQL terminal framing **and**
  a footer pointer to C's recorded fallback (`run-demo.sh`). The deck accommodates both paths; the
  stage rehearsal on `tenant-b` is out of scope here (owner: Observability Agent + Henrik).
- **G3 — 30-min timing.** A already timed it (Part 3): ~22 min content + ~8 min across the 3
  discussion beats (slides 4/10/21) = 30 min. Structure preserved in the build. A's demo-compression
  fallback (drop JMeter detail if Discussion #2 runs hot) is noted on slide 18's footer.

## Honesty beats preserved (DESIGN-SYSTEM §5)
- Slide 6 is the **only** glitch-treatment slide. Slide 10 owns the ×1.27 **coverage** reveal
  (spans un-sampled, ratio 1.0) — kept distinct from sampling.
- Slide 13: logs leg **dashed** (empty on this tenant); `user.events` edge **solid** (live, scope
  granted ISI-5719) — no stale 403/glitch treatment (per rev4 / ISI-5726).

## Rebuild
```
cd presentation-matrix
python3 gen_diagrams.py && python3 gen_system.py && python3 gen_deck.py && python3 build_pdf.py
```

Branch `isi-5791/pages-brand` @ `6f1d501`. `presentation-matrix/` is `.gitignore`'d (internal talk
assets kept out of the public mirror) → force-added, consistent with the ISI-5724 masters/diagrams.
