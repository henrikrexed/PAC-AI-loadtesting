# PAC Talk B — Themed Visual System, Slide Masters & Diagram Redraws

*ISI-5724 (workstream B · Graphic Designer) · child of [ISI-5720](/ISI/issues/ISI-5720) · theme **The Matrix** 🔴💊 (plan rev `d09391e7`)*
*Lays out A's approved copy ([ISI-5722](/ISI/issues/ISI-5722) `presentation-matrix/narrative-and-slide-copy.md`). Diagram content validated against C ([ISI-5723](/ISI/issues/ISI-5723)).*

Deck: *There Is No Spoon — Load-Testing the Real World* · 21 slides · PAC 30-min expert session.

---

## 1. Visual system — "The Matrix, but for a serious expert council"

The theme is a **thin framing layer**. Dark base, green "digital rain" used *sparingly* (right-edge strips, title bookend, the terminal), a red-pill / blue-pill **semantic** pair. In the technical core (slides 5–14) the numbers carry the weight; the Matrix line is punctuation, not argument. Every themed line maps to a real technical claim (Part 1 table in A's doc) — or it gets cut.

### Palette (taste-skill compliant: neutral near-black base + ONE structural accent)
| Token | Hex | Role |
|---|---|---|
| `BG0` | `#070A08` | deepest base (near-black, faint green cast) |
| `BG1` / `BG2` / `BG3` | `#0C120E` / `#121A15` / `#18221C` | panel / raised / chip |
| `LINE` / `LINE2` | `#202E26` / `#2E4035` | hairline / stronger border |
| **`GREEN`** | **`#39D98A`** | **the one structural accent** — telemetry / the signal / observed-truth-in-the-stack |
| `GREEN_HI` | `#78F5B4` | rain heads, code glow |
| `RED` | `#FF4D5E` | **red pill = observed truth / the human gate (the Oracle)** |
| `BLUE` | `#5C8DEF` | **blue pill = guessing / synthetic / folklore** |
| `AMBER` | `#F6B23C` | honesty beats: dashed "unavailable" (empty logs leg) / the sampling glitch (#6) / graceful-degrade fallback / caveats |
| `INK` / `MUTE` / `FAINT` | `#EAF3EC` / `#8DA296` / `#5C6E64` | text tiers |

**Discipline:** red/blue appear *only* where guess-vs-truth is the actual point. Amber is reserved for "unavailable" (the empty logs leg) and the sampling-glitch beat. The glitch treatment is reserved for the sampling slide (#6). One corner-radius scale (9px @1x). Hairline borders, accent top-rail on nodes.

### Typography
- **DejaVu Sans / Sans Bold** — titles & body (the host has no Geist/Satoshi/Inter; DejaVu is the available neutral grotesque and avoids the default-Inter tell).
- **DejaVu Sans Mono** — all code, DQL, labels, kickers, footers, terminal (the signature "code" face; thematically correct).
- Scale @1920×1080 intent: deck title ~150 · slide title 84/72 · body 40 · bullets ≤6 words where possible · mono code 30–32.

### Motifs
Red/blue **pills** · **lock** = the V1 gate / the Oracle · amber **dashed "unavailable"** marker (logs leg) · **code-rain** (hex/binary glyphs, low alpha, edge strips only).

See **`images/00-visual-system.png`** — the one-page reference board (palette swatches with hex, type scale, motifs, discipline rules).

---

## 2. Slide masters (5 layouts)

| Master | File | Use for | Signature |
|---|---|---|---|
| Title | `master-title.png` | slide 1, 21 | full-bleed rain, pills introduced; bookend |
| Section | `master-section.png` | act turns | big `§NN` numeral, rain on right third, pill divider |
| Content | `master-content.png` | slides 3,5,6,7,8,9,11,12,13,14,20 | kicker + title top-left, bullets left, visual/diagram right **or** full-bleed diagram |
| Demo | `master-demo.png` | slides 15–18 | terminal chrome, green-on-black, `● LIVE` badge, live `user.events` + gate highlighted |
| Discussion 💬 | `master-discussion.png` | slides 4,10,21 | near-empty, one big question, blinking `> _`, rain strip |

Every slide carries the same chrome: 6px green top accent, footer rule with `There is no spoon · PAC 2026 · IsItObservable` (left) and `§ section` + `NN / 21` (right).

---

## 3. Diagram redraws (the technical core)

Each diagram ships **twice**: `name.png` (transparent background, drop onto any master) and `name--onbg.png` (dark base baked in, for standalone review / full-bleed use). Content cross-checked against A's copy + C's tech-accuracy review.

| # | File | Slide | What it shows |
|---|---|---|---|
| D1 | `d1-loop` | 19 | **The loop** — SCOPE→VALIDATE→SYNTHESIZE→EXECUTE→ANALYZE clockwise; VALIDATE = the Oracle (red, lock, *Temet Nosce*); closing edge dashed-amber `iterate ≤ 3 → escalate`; center "delegate EXECUTION, not judgment". |
| D2 | `d2-construct` | 12 | **The Construct (3-layer engine)** — INPUT ADAPTER (backend-specific: DQL/Tempo/Jaeger/Envoy) → **ENGINE** (agnostic·deterministic·offline-testable; discovery, ~80% clustering, Little's Law, ramp, dataset sizing) → RENDERERS (k6/JMeter/Locust/Gatling ✓). Labels: `neutral telemetry`, `workload-model.json`. |
| D3 | `d3-dual-source` | 8 | **Dual-source storage** — SERVER-SIDE TRACES → `fetch spans`; RUM → `fetch user.sessions` (LIVE) + `fetch user.events` (**LIVE · 16 journeys**, green — scope granted ISI-5719); both via **DQL**; **stitched on `dt.rum.session.id`** (red); → one workload model. "Residual self image" wireframe motif. |
| D4 | `d4-many-worlds` | 14 | **One model, many worlds** — one `workload-model.json` → renderer registry → k6 / JMeter / Locust / Gatling, each `✓ acceptance tests`. "Guns. Lots of guns." |
| D5 | `d5-stack` | 13 | **The wired stack** — Astroshop (OTel Demo) → OTel Collector → Dynatrace Grail (`spans` / `user.sessions` / `user.events`) → agent → skill → engine → **V1 gate (lock)** → renderers (k6, JMeter). **Honest annotations:** `logs` leg **dashed** (empty on this tenant); `user.events` edge **solid** (live — scope granted ISI-5719 → ordered journeys). Footer: read-only · extraction-only · non-production · tenant-isolated. |

---

## 4. Exemplar slides (masters applied to A's real copy)

Proof the system holds up with real content — `slide-01-title`, `slide-02-bluepill`, `slide-08-dual` (D3 full-bleed), `slide-10-discussion` (the ×1.27 beat), `slide-15-demo` (live terminal — `user.events` returns rows + the gate), `slide-19-loop` (D1 full-bleed).

---

## 5. Honesty flags carried into the visuals (do not remove)

- **`user.events` = LIVE** (scope `storage:user.events:read` granted 2026-10-13, ISI-5719) — D3/D5 draw it **solid/green** (ordered journeys → `rum-journey-model.json`); the demo terminal shows it **returning rows** ("the wall came down"). The honesty beat is now the *graceful degrade*: the model is sized from spans + `user.sessions` and never depended on `user.events`, so it degrades cleanly if the scope is ever removed — the 403 is the documented **fallback**, not a live blocker. (A §Part5.3 rev4, C §9, ISI-5726.)
- **logs = unavailable on this tenant** — D5 draws the logs leg dashed (spans-&-RUM here, not logs). (C §8.)
- **1.27 = source-coverage, not a sampling inverse** — spans are un-sampled (`samplingRatio 1.0`). D3 says so explicitly; the ×1.27 bar reveal lives on slide 10, kept distinct from the sampling-trap slide (6).
- **QR / repo links are a PLACEHOLDER** — D5's QR is a non-scannable placeholder tile labelled *"pending public mirror (ISI-5659)"*. ⚠ **Do not bake a live QR until [ISI-5659](/ISI/issues/ISI-5659) publishes `github.com/henrikrexed/AI-Performance-Testing` and every linked path resolves.** (A §Part5.9.)

---

## 6. Rebuild

Pure Pillow + the DejaVu TTFs shipped in matplotlib's `mpl-data` (this host has no libcairo/resvg/rsvg/inkscape/imagemagick). Deterministic (fixed seeds).

```
cd presentation-matrix
python3 gen_diagrams.py   # D1–D5  → images/
python3 gen_system.py     # visual system + masters + exemplars → images/
```

`mtx_theme.py` = shared palette / fonts / node·arrow·pill·lock·rain primitives. Edit tokens there to re-skin the whole deck.

Export to the deck: import the transparent `dN-*.png` onto the matching master in Keynote / Google Slides / PowerPoint, or use the `slide-*.png` / `*--onbg.png` renders directly (16:9, 2560×1440).
