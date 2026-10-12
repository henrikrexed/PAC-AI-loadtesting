# ISI-5693 — SCOPE step 2c Path B: stitch sessions from OTel `session.id` on spans

> **Grail-native, read-only.** Parent ISI-5622; follows ISI-5691 (RUM feasibility NO-GO →
> Path B recommended). Implements **methodology §3.1 step 2c tier (ii)**: detect an OTel
> `session.id` on spans and use it to stitch real sessions, closing the §11 **R5** "no notion
> of a session" gap **without** any RUM / classic-token dependency (Path A stays board-gated).
> Tenant **wkf10640** via the readonly `tenant-b` dtctl context. Window: 24h ending
> 2026-10-12T13:16Z. Extraction/investigation only — tenant kept read-only (§7.1).

## ⚑ UPDATE 2 (board review round 2, 2026-10-12) — the real signal is Grail RUM `user.sessions`

The board rejected the span/`session.id` framing and pointed at the correct object:
`fetch user.events | filter dt.rum.session.id == "…"`. Investigating confirmed a **major
correction that supersedes the ISI-5691 NO-GO**: Dynatrace RUM sessions **are** Grail/DQL-native
on this tenant — ISI-5691 simply probed the wrong objects (`dt.rum.*`, RUM attrs on `spans`). The
real objects are **`user.sessions`** and **`user.events`**, keyed by **`dt.rum.session.id`**. No
classic `dt0c01`/USQL token is needed (that was the Path-A assumption). Details in **§7**. The
span/`session.id` sections below (ad-fetch marker) remain true but are now **secondary** — the
RUM user-session objects are the primary, correct signal.

- `fetch user.sessions` — **accessible today** on the `tenant-b` read token. **35,679 sessions /
  24h** across 5 RUM apps incl. mobile; per-session action/navigation counts, duration, bounce,
  errors, app, geo/device. This is the real user-session population (Astroshop 17.1k · EasyTrade
  7.9k · Astroshop-PureOTel 5.2k · Astroshop_Android 2.9k · others).
- `fetch user.events` — **scope-gated** (`403`, needs OAuth scope `storage:user.events:read`).
  Holds the per-session **ordered** navigation (views / user actions / requests) → the exact
  action sequence, per-action think-times, and the actual pages/use-cases. **This is the one
  thing blocking full ordered-journey Path B.**

## Verdict (span/session.id track): **mechanism GO; the `session.id` span attribute is NOT a usable user-session journey.**

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

## 7. Grail-native RUM user sessions (`user.sessions` / `user.events`) — the correct signal

**This supersedes the ISI-5691 step-2c NO-GO.** ISI-5691 concluded RUM was unreachable in Grail,
but it probed `dt.rum.*` data objects and RUM attributes on `spans` — neither is how Dynatrace
exposes RUM in Grail. The real objects are `user.sessions` and `user.events`, keyed by
`dt.rum.session.id`, and they are DQL-native (no classic `dt0c01`/USQL token — the Path-A premise
was wrong for this platform version).

### 7.1 `user.sessions` — accessible now, the real user-session population

`fetch user.sessions` returns one row per real-user session with 54 fields incl.
`dt.rum.session.id`, `dt.rum.application.entities` / `frontend.name`, `duration`,
`user_action_count`, `navigation_count`, `user_interaction_count`, `request_count`,
`view_summary_count`, `characteristics.is_bounce`, `end_reason`, `error.*`, geo/device/browser.

**Live coverage (24h, read-only):** **35,679 sessions** across 5 RUM apps:

| app | type | sessions | actions/session (p50) | duration p50 | bounce |
|---|---|---:|---:|---:|---:|
| Astroshop | web | 17,114 | 8 | 15 s | 0.06 % |
| EasyTrade_1 | web | 7,865 | 9 | 26 s | 0 % |
| Astroshop_Pure_OpenTelemetry | web | 5,197 | 6 | 75 s | 1.4 % |
| Astroshop_Android | mobile | 2,905 | 1 | 89 s | 0 % |
| (My_web_application, APPLICATION-CB02…, …) | web | ~2,000 | varies | varies | — |

This alone delivers the **session boundary + session length (R5)** signal for the whole RUM
population — exactly "more use cases using the user session", and **app-agnostic** (web *and*
mobile). `scripts/rum_sessions.py` consumes these rows → per-app `session_shape()`
(actions / navigations / duration distributions, bounce, error-session rate) + `rum_coverage()`.
A first-order pacing estimate `mean_interaction_gap = duration/(actions-1)` is provided but
**labelled approximate** — `user.sessions` has no per-action timings.

### 7.2 `user.events` — scope-gated, needed for ordered journeys + exact think-times

`fetch user.events | filter dt.rum.session.id == "…"` (the board's example) returns the ordered
navigation within a session: views, user actions, requests, errors — i.e. the actual pages/use
cases, their order, and exact inter-action timings. On the `tenant-b` read token it returns
**`403 NOT_AUTHORIZED_FOR_TABLE` — missing `storage:user.events:read`**. This is the **only**
blocker to a true ordered-journey Path B (real sequence + measured per-action think-times + the
real browse/cart/checkout use cases per session).

**Unblock:** tenant admin / board adds `storage:user.events:read` (and it already grants
`user.sessions`) to the `tenant-b` read token. Then the extractor stitches real ordered journeys
from `user.events` grouped by `dt.rum.session.id` — the full R5 closure, Grail-native, no classic
token, no PII beyond opaque session ids (§7.1 PII scrub still applies to geo/user fields).

## 8. Dual-source merge — RUM ⟗ spans (board design, 2026-10-12)

Board directive: *"both-sides analysis — RUM and span — then merge. If the requests are common
with RUM, use mainly the user session (beware the sampling → extrapolate). For spans with no RUM
match, generate an HTTP-based scenario."* `scripts/source_merge.py` is the deterministic
reconciler (`reconcile()` / `merge_plan()`), pure and tested.

**Per-key merge rules:**

| overlap | source | volume | rationale |
|---|---|---|---|
| **common** (in RUM *and* spans) | **RUM** user session (ordered journey + think-times) | `rum_rate × factor`, `factor = span_rate / rum_rate` | RUM is the session-accurate signal; the span side is **unsampled** here (`dt.system.sampling_ratio=1.0`), so the overlap ratio *measures* RUM's effective sampling and extrapolates the RUM-primary journey up to the real volume — no separate sampling-rate config needed |
| **span-only** (no RUM match) | **span** HTTP scenario (tiers 2a/2b) | span_rate | backend/internal gRPC + non-browser apps the RUM agent never sees (unguard, image-provider, A2A, cron) |
| **rum-only** (RUM, no server span) | RUM as-is (factor 1.0, flagged) | rum_rate | pure client-side activity; not span-extrapolatable |

**Self-calibrating sampling.** No RUM sampling-rate metric is exposed on this token
(`dt.sfm.*rum*` has only `total_sessions`), so a configured rate is unavailable — but the merge
does not need one: `factor = span_rate / rum_rate` on any shared endpoint both reveals and
corrects the sampling. Worked example shape: RUM sees an endpoint at 2/s, spans (truth) at 8/s →
`factor = 4` → the RUM-primary journey is driven 4× to reproduce real load.

**Both-sides coverage on wkf10640 (what routes where):**
- **RUM-primary** (browser user journeys): Astroshop, EasyTrade, Astroshop-PureOTel, Astroshop_Android — the `user.sessions`/`user.events` surface (§7).
- **Span HTTP fallback** (no browser RUM): unguard, image-provider, smartfreight/tms A2A agents, cron pollers, and all backend/internal service-to-service calls.

**Open dependency for the *real* merged model:** the authoritative per-endpoint RUM rates (to
compute the overlap set and the per-endpoint `factor`) live in `user.events` — gated on
`storage:user.events:read` (§7.2). The reconciler + extrapolation math are done and tested; they
light up unchanged the moment that scope lands. Span side and RUM session-shape side are already
extractable today.

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
- **`skills/workload-model/scripts/rum_sessions.py`** — Grail-native RUM module (§7): consumes
  `user.sessions` → `session_shape()` + `rum_coverage()` + approximate `mean_interaction_gap_s()`.
- **`skills/workload-model/fixtures/wkf10640_rum_sessions.json`** — live per-app `user.sessions`
  facts (35,679 sessions / 5 apps). **`tests/test_rum_sessions.py`** — 6 tests.
- Additive `source.rumSessionCoverage` in `schema.json`.
- **`skills/workload-model/scripts/source_merge.py`** — dual-source RUM⟗span reconciler (§8):
  `reconcile()` / `merge_plan()` with self-calibrating span/rum extrapolation. **`tests/test_source_merge.py`** — 6 tests.

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
| **§7** RUM session shape | `fetch user.sessions \| fieldsAdd app=dt.rum.application.entities[0], fe=frontend.name[0] \| summarize sessions=count(), avg(user_action_count), percentile(duration,50), avg(toLong(characteristics.is_bounce)), by:{fe, dt.rum.application.type}` → 35,679 sessions / 5 apps |
| **§7** RUM total | `fetch user.sessions \| summarize count(), countDistinctExact(dt.rum.session.id)` → 35,679 / 35,679 |
| **§7** user.events (gated) | `fetch user.events \| filter dt.rum.session.id=="…"` → **403 missing `storage:user.events:read`** |

Token `tenant-b-read` still un-rotated (flagged to board since ISI-5684) — valid for this round.
