# PAC Deck — Final Build & Export (ISI-5794)

*Assembly of the 21-slide Matrix deck from the three completed workstreams. Child-of / hand-back → [ISI-5720](/ISI/issues/ISI-5720) (assembly hub). Board green-lit the assembly (`confirmation:ISI-5720:assembly-greenlight-v1`).*

Deck: **There Is No Spoon — Load-Testing the Real World** · 21 slides · PAC 30-min expert session · Henrik Rexed · IsItObservable.

---

## Inputs (all committed, consumed as-is)
- **Copy (A, [ISI-5722](/ISI/issues/ISI-5722))** — `narrative-and-slide-copy.md` **rev4** (`08a6163`): Part-3 timed narrative + Part-4 per-slide copy, 21 slides.
- **Visual system (B, [ISI-5724](/ISI/issues/ISI-5724))** — board-accepted @ `7e2ea96`: `mtx_theme.py`, masters, diagrams `d1`–`d5` (+ `--onbg`), `DESIGN-SYSTEM.md`.
- **Demo (C, [ISI-5723](/ISI/issues/ISI-5723))** — `loadtests/wkf10640-astroshop-frontend/` live + recorded fallback; drives slides 15–18 framing.

## Build chain (deterministic — pure Pillow, no cairo/LibreOffice)
```
cd presentation-matrix
python3 gen_diagrams.py   # d1–d5 (d5 bakes the REAL repo QR — mirror now live)
python3 gen_system.py     # masters + visual-system board
python3 gen_deck.py       # all 21 slides → images/slide-01-title.png … slide-21-close.png
python3 build_deck.py     # → dist/PAC-there-is-no-spoon.{pptx,pdf}
```
- `gen_deck.py` is the single source of truth for every slide: A's Part-4 copy laid onto B's masters/diagrams. One function per slide, deterministic seeds.
- `build_deck.py` assembles the renders into an **editable 16:9 PPTX** (one full-bleed slide PNG per slide + A's Part-3 timed narrative as PowerPoint speaker notes, parsed live from the copy doc — no drift) and a **universal PDF** (one slide/page).

## Deliverables
| File | What |
|---|---|
| `images/slide-01…21-*.png` | 21 slides, 2560×1440 (16:9), dark base baked in |
| `dist/PAC-there-is-no-spoon.pptx` | editable deck — opens / imports into PowerPoint · Keynote · Google Slides; speaker notes on all 21 |
| `dist/PAC-there-is-no-spoon.pdf` | click-to-present, 21 pages, %PDF-1.4 |

**Export-format note.** v1 "Stop Guessing" ([ISI-4048](/ISI/issues/ISI-4048)) shipped as a markdown slide *spec* (`presentation/slides-draft.md`), **not** a binary deck — so there was no prior PPTX/Slides file to byte-mirror. This build matches the design-system's stated export path (2560×1440 PNGs → slide tool) and adds an editable PPTX + universal PDF so Henrik can present or hand-edit directly. **If the board wants a native Google Slides deck specifically, the PPTX imports 1:1** — flag on hand-back.

---

## Slide map (A's order)
1 title · 2 red/blue pill · 3 basics · **4 💬 Discussion #1** · 5 OTel · **6 sampling trap (the one glitch slide)** · 7 state of RUM · 8 spans+RUM (d3) · 9 DQL · **10 💬 Discussion #2 — the ×1.27 reveal** · 11 skill · 12 engine (d2) · **13 architecture (d5 + real QR)** · 14 many worlds (d4) · **15–18 LIVE demo** · 19 loop + Oracle (d1) · 20 honest limits · **21 💬 Discussion #3 + close (real QR)**.

## Ship-gates
- **G1 — QR / repo links (slides 13 + 21).** ✅ **Real, scannable.** Public mirror `github.com/henrikrexed/AI-Performance-Testing` is **live** ([ISI-5659](/ISI/issues/ISI-5659)) — verified HTTP 200 (repo page + raw README on `main`). QRs encode that URL via `segno`/`qr_util.py` (slide 13's is baked into the `d5` diagram; slide 21 has a large scan-from-the-room QR). No placeholder, no 404.
- **G2 — live-demo rehearsal** (stage `tenant-b`, owner Observability Agent + Henrik). Out of scope for this build; the demo slides (15–18) accommodate **both** the live `run-demo-live.sh` run and the recorded `run-demo.sh` fallback (footer badge on slide 18 carries the compress-to-~3-min path).
- **G3 — 30-min timing/length pass.** ✅ A's Part-3 narrative is timed end-to-end **0:00 → 30:00** across all 21 slides; 3 discussion beats (4/10/21) built in; slide 20 marked `[FLEX]`; demo-compression fallback (drop JMeter detail → ~3 min if Discussion #2 runs hot) documented and surfaced on slide 18.

## Honesty flags preserved (DESIGN-SYSTEM §5 — do not strip)
- **slide 6** is the *only* glitch-treatment slide (sampling trap).
- **slide 10** owns the ×1.27 **coverage** reveal (spans un-sampled, `samplingRatio 1.0`) — kept distinct from sampling.
- **slide 13 (d5):** `logs` leg **dashed** (empty on this tenant); `user.events` edge **solid** (live, scope granted [ISI-5719](/ISI/issues/ISI-5719)). Graceful-degrade to spans + `user.sessions` is the documented fallback.
- **slide 16:** `user.events` 403→granted shown as "the wall came down" (resolved transition, green), not a live blocker.

## Hand-back
→ [ISI-5720](/ISI/issues/ISI-5720) for board review before PAC submission. Open confirm item for the board: accept PPTX+PDF as the deck format (or request native Google Slides — PPTX imports 1:1).
