# ISI-5693 — SCOPE step 2c Path B: stitch sessions from OTel `session.id` on spans

> **Grail-native, read-only.** Parent ISI-5622; follows ISI-5691 (RUM feasibility NO-GO →
> Path B recommended). Implements **methodology §3.1 step 2c tier (ii)**: detect an OTel
> `session.id` on spans and use it to stitch real sessions, closing the §11 **R5** "no notion
> of a session" gap **without** any RUM / classic-token dependency (Path A stays board-gated).
> Tenant **wkf10640** via the readonly `tenant-b` dtctl context. Window: 24h ending
> 2026-10-12T13:16Z. Extraction/investigation only — tenant kept read-only (§7.1).

## Verdict: **mechanism GO; on wkf10640 the signal is NOT usable as a user-session journey.**

The session-stitch **mechanism** works and is shipped (pure module, app-agnostic, tested). But
a board review (2026-10-12, §6 below) correctly flagged that the `session.id` on this tenant is
**not a usable user-session signal**: it is emitted *only* on the homepage ad/recommendation
data fetch (`frontend /api/data` → `ad GetAds`), which **repeats** during a session. It tags a
**single use case** (ad fetch), never a real user action — verified: ad-session traces reach
**none** of cart/checkout/payment/product-catalog, and **0 of 1.41M** frontend spans carry
`session.id`, even though the full browse→cart→checkout surface exists. So Path B here yields
ad-fetch *cadence*, **not** multi-action journeys or per-action think-time. The ~7.2s cadence is
therefore **deliberately NOT attached** to any journey (correcting an earlier rev-2 overstatement);
both journeys stay on span-order. Coverage is still recorded for auditability. The mechanism will
light up only once the **app** propagates `session.id` as baggage onto every action's entry span.

---

## 1. Coverage — which services carry `session.id`? (step 2c.1)

Live DQL (`--context tenant-b`, 24h):

```
fetch spans | filter isNotNull(session.id)
  | summarize spans=count(), sessions=countDistinctExact(session.id), by:{service.name}
```

| service | total spans | session-bearing spans | **service coverage** | distinct sessions | mean actions/session | op carrying the id |
|---|---:|---:|---:|---:|---:|---|
| `ad` | 137,490 | 28,018 | **20.38 %** | 5,241 | 5.35 (max 7) | `oteldemo.AdService/GetAds` (server) |
| `smartfreight-agent-service` | 2,413 | 132 | **5.47 %** | 131 | 1.00 | `smartfreight_chat_stream.workflow` |
| *(all other services)* | — | 0 | 0 % | — | — | — |

**Tenant-wide:** 28,165 of **50,451,393** spans carry `session.id` ⇒ **0.056 %** overall. Only
**two** services carry it, and only on a **single operation each**. The browser frontend,
checkout, payment, cart, etc. carry **none** — consistent with the ISI-5691 spike baseline
(`ad` 5,274 / smartfreight 132).

> **Why so sparse (and why it's the wrong signal here):** the astronomy-shop demo sets the OTel
> `session.id` baggage→span-attribute **only** on the homepage ad/recommendation data fetch
> (`frontend /api/data` → `ad GetAds`), which repeats during a session; it is **not** propagated
> onto the frontend entry spans of real actions (browse/cart/checkout — §6). smartfreight sets it
> once per chat workflow. This is an app instrumentation choice, not a tenant limitation — the
> mechanism lights up only when apps propagate `session.id` onto every action's entry span.

## 2. Stitch where present (step 2c.2) — what the chain actually contains

Group session-bearing spans by `session.id`, order by `start_time`, diff consecutive events.
`scripts/session_stitch.py` does this as a pure function (`stitch()`), reproduced here on the
5,241 `ad` chains (28,021 spans exported read-only to CSV, nanosecond-precise parse). **Note:
every event in these chains is the *same* ad fetch — so the gaps below are ad-refresh _cadence_,
not think-time between distinct user actions (see §4/§6).**

**Inter-event gap** (next.start − prev.end, clipped ≥ 0; 1.0 % negative/overlapping):

| metric | value |
|---|---:|
| p50 | **7.20 s** |
| p90 | 27.67 s |
| p99 | 45.11 s |
| max | 70.08 s |
| mean | 11.07 s |
| median/mean ratio | 0.65 → **exponential-shaped** (exp ⇒ 0.69) |

**Session shape:** 5,241 sessions, **5.35** actions/session (p50 5, p99 7, max 7); session span
p50 **47.1 s**, p90 73.4 s, p99 95.7 s, max 152 s.

These feed the §8.4 SequenceReconstructor as genuine session chains. The extractor emits a
schema-valid `thinkTime` object per step — either `empirical` (256-sample strided real draw,
the shipped default) or the compact `exponential` (`meanMs` 11,069) closed-form.

## 3. Fallback intact + auditability (step 2c.3)

Where `session.id` is absent, nothing changes: the span-order method (tiers 2a/2b) is the
fallback. Coverage is now recorded on the model so fidelity is auditable next to the §11-R1
sampling ratio — new additive `metadata.source.sessionIdCoverage`
(`schema.json`), e.g. in `loadtests/wkf10640-astroshop-frontend/workload-model.json` (rev 2):

```json
"sessionIdCoverage": {
  "hasSessionSignal": true,
  "overallCoveragePct": 20.12,
  "services": [
    {"service":"ad","totalSpans":137490,"sessionSpans":28018,"sessions":5241,"coveragePct":20.38,"meanActions":5.346},
    {"service":"smartfreight-agent-service","totalSpans":2413,"sessionSpans":132,"sessions":131,"coveragePct":5.47,"meanActions":1.0}
  ]
}
```
(`overallCoveragePct` is over the **reported session-bearing services**, not the tenant; the
tenant-wide 0.056 % is noted above so the number is never overstated.) `hasSessionSignal:false`
⇒ 0 % coverage ⇒ pure span-order fallback, surfaced as an R5 line in the proposal.

## 4. Side-by-side — what `session.id` stitches vs what a user journey needs (astroshop)

| dimension | span-only (tiers 2a/2b) | Path B on `session.id` here | usable as journey? |
|---|---|---|---|
| session boundary | none (R5) | real: 5,241 `session.id` chains | boundary yes |
| what the chain contains | — | **only** repeated `ad GetAds` / `/api/data` fetches | **no** — one use case |
| actions/session | inferred from a self-contained trace | 5.35 **ad fetches** (not distinct actions) | no |
| inter-event gap | assumed | 7.2 s median — **ad-fetch cadence**, not think-time | no |
| distinct use cases reached | browse/cart/checkout (span-order) | **none** beyond ad (verified join, §6) | no |
| dependency | none | none (Grail only) | — |

**Net (corrected):** on wkf10640, `session.id` does **not** reconstruct a user journey — it only
measures how often the homepage ad block re-fetches within a browser session. Attaching that
cadence as journey think-time (earlier rev 2) **overstated** the signal and is reverted. Both
journeys stay on span-order; `session.id` coverage is recorded but not used for pacing. The
fidelity gain Path B promises is real **only** when the app tags real actions with `session.id`.

## 5. Generalization check (step 2c.4) — app-agnostic

The stitcher keys **only** on `session.id`, never on anything browser-specific. Confirmed live:
`smartfreight-agent-service` — a **non-browser A2A agent** — carries `session.id` and stitches
cleanly into 131 single-action chat sessions. Single-action sessions correctly yield **no**
think-time (`think_time_spec()` returns `None`) rather than a fabricated one. Any service that
propagates `session.id` is stitchable, browser or not. ✓

## 6. Board review (2026-10-12) — "ad is a main-page request, this is incorrect"

The board challenged the first pass: *"ad is technically a request called on the main page… so
it is incorrect. you should see more use cases using the user session."* Correct. Deeper
read-only analysis of the tenant confirms it:

1. **No other session/user attribute exists.** Probing every candidate over 50.5M spans
   (`session.id`, `session_id`, `app.session.id`, `user.session.id`, `enduser.id`, `user.id`,
   `rum.sessionId`, `dt.session.id`): only `session.id` is non-null (28,170), the rest are 0.

2. **`session.id` tags only the ad data-fetch.** Joining `session.id` ad spans → their `trace.id`
   → the trace's entry spans shows the traces are rooted at
   `frontend-proxy ingress → frontend GET /api/data → ad GetAds` — the homepage
   ad/recommendation fetch, repeating within a session.

3. **Those traces reach no real use case.** Join of ad-session `trace.id`s against
   `{cart, checkout, payment, product-catalog, recommendation, currency}` → **0 rows**. The
   session never touches a purchase funnel action.

4. **The real actions exist but are untagged.** `0 of 1,406,793` frontend spans carry
   `session.id`, yet the frontend serves the full surface: `GET /api/cart`, `POST /api/cart`,
   `GET /api/products/[productId]`, `POST /api/checkout`, `/api/recommendations`, `/api/shipping`,
   `/api/currency`, … None of them is session-tagged.

**Conclusion:** `session.id` on wkf10640 is a main-page ad-fetch marker, not a user-session
signal. Path B cannot recover multi-use-case journeys here. Fix is app-side (propagate
`session.id` baggage onto every action's entry span). The extractor change is corrected to
record coverage **without** using the cadence as think-time (model rev 3).

## Deliverables (shipped)

- `skills/workload-model/scripts/session_stitch.py` — pure Path B module: `stitch()`,
  `think_time_spec()` (empirical/exponential), `session_coverage()`, ns-precise ISO parse.
- `skills/workload-model/scripts/schema.json` — additive `source.sessionIdCoverage` (R5 audit).
- `skills/workload-model/scripts/emit.py` — threads coverage onto the model + renders the R5
  Path B proposal line (both the `hasSessionSignal` and the 0 %-fallback branch).
- `skills/workload-model/scripts/build_wkf10640.py` — astroshop build records `session.id`
  coverage on the model and bumps to **rev 3**; after the board review it does **not** attach the
  ad-fetch cadence as journey think-time (both journeys stay on span-order); R5 note corrected.
- `skills/workload-model/fixtures/wkf10640_session_stitch.json` — live facts + real think-time
  samples (deterministic replay without tenant access).
- `skills/workload-model/tests/test_session_stitch.py` — 12 tests (ordering, think-time clip,
  coverage %, empirical/exponential spec, single-action→None, max-gap split, fixture repro).

## Methodology note for BigBoss (fold into §3.1 step 2c)

Step 2c tier (ii) is **implemented and default-on** as a mechanism: the extractor detects
`session.id`, stitches where present, records coverage, and falls back to span-order otherwise.
**But on wkf10640 the signal must not be used for journey pacing** (board review §6): `session.id`
tags only the homepage ad fetch (0.056 % tenant-wide; 0 of 1.41M frontend spans; ad-session
traces reach no funnel action), so it reconstructs a single repeating use case, not a user
journey. The extractor therefore records coverage **without** deriving think-time from it here.
The blocker to realising Path B's value is **app-side**: propagate `session.id` as baggage onto
every action's **entry span** (OTel session semconv) — an instrumentation recommendation, not a
SCOPE change. Until then, span-order (2a/2b) is the method. Path A (RUM/USQL fusion) remains the
only route to true browser user-session journeys and stays board-gated (ISI-5691).

## Appendix — query ledger (all read-only, `--context tenant-b`)

| purpose | query (abbrev.) |
|---|---|
| coverage per service | `fetch spans, from:now()-24h \| filter isNotNull(session.id) \| summarize count(), countDistinctExact(session.id), by:{service.name}` |
| coverage denominators | `fetch spans \| filter service.name=="ad" or ... \| summarize count(), countIf(isNotNull(session.id)), by:{service.name}` |
| tenant-wide coverage | `fetch spans \| summarize totalSpans=count(), sessionSpans=countIf(isNotNull(session.id))` |
| actions/session (ad) | `... service.name=="ad" and isNotNull(session.id) \| summarize actions=count(), by:{session.id} \| summarize percentile(actions,50/90/99), max, avg` |
| raw chains (ad) | `... service.name=="ad" and isNotNull(session.id) \| fields session.id, start_time, duration, span.name` (→ CSV, think-times computed in `session_stitch.py`) |
| op carrying id (ad) | `... service.name=="ad" and isNotNull(session.id) \| summarize count(), by:{span.name, span.kind}` → single op `GetAds` |
| generalization (smartfreight) | `... service.name=="smartfreight-agent-service" and isNotNull(session.id) \| summarize actions=count(), by:{session.id} \| summarize ...` → 131 × 1 action |
| **§6** all session/user attrs | `fetch spans \| summarize countIf(isNotNull(session.id)), countIf(isNotNull(session_id)), countIf(isNotNull(app.session.id)), countIf(isNotNull(user.session.id)), countIf(isNotNull(enduser.id)), countIf(isNotNull(user.id)), ...` → only `session.id` non-null |
| **§6** session→trace→entry op | `... service.name=="ad" and isNotNull(session.id) \| fields session.id, trace.id \| join [ ... request.is_root_span==true \| fields trace.id, service.name, span.name ], on:{trace.id} \| summarize by:{entryOp}` → frontend-proxy ingress / frontend /api/data / ad GetAds |
| **§6** ad-session ⟂ funnel | `... service.name=="ad" and isNotNull(session.id) \| fields trace.id \| join [ ... in(service.name,{"cart","checkout","payment","product-catalog",...}) \| fields trace.id, service.name ], on:{trace.id} \| summarize by:{svc}` → **0 rows** |
| **§6** frontend untagged | `fetch spans \| filter service.name=="frontend" \| summarize total=count(), withSession=countIf(isNotNull(session.id))` → 1,406,793 / **0** |

Token `tenant-b-read` still un-rotated (flagged to board since ISI-5684) — valid for this round.
