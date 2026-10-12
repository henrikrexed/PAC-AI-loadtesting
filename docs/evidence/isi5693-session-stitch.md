# ISI-5693 — SCOPE step 2c Path B: stitch sessions from OTel `session.id` on spans

> **Grail-native, read-only.** Parent ISI-5622; follows ISI-5691 (RUM feasibility NO-GO →
> Path B recommended). Implements **methodology §3.1 step 2c tier (ii)**: detect an OTel
> `session.id` on spans and use it to stitch real sessions, closing the §11 **R5** "no notion
> of a session" gap **without** any RUM / classic-token dependency (Path A stays board-gated).
> Tenant **wkf10640** via the readonly `tenant-b` dtctl context. Window: 24h ending
> 2026-10-12T13:16Z. Extraction/investigation only — tenant kept read-only (§7.1).

## Verdict: **GO (partial, sparse).** Path B works and is now shipped in the extractor.

`session.id` is real, Grail-native, and stitchable — but **sparse** on wkf10640. It closes R5
for the **Browser** journey (real browse think-times) and generalises to a non-browser A2A
agent, while the full browse→checkout chain still needs span-order reconstruction because the
id does not propagate to the frontend/checkout spans.

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

> **Why so sparse:** the astronomy-shop demo sets the OTel `session.id` baggage→span-attribute
> only on the `ad` service's `GetAds` call (the ad-slot lookup fired on each ad-bearing page
> view); it is not propagated end-to-end. smartfreight sets it once per chat workflow. This is
> an instrumentation choice in the apps, not a tenant limitation — the mechanism would light up
> fully if apps propagated `session.id` as baggage across all services (OTel session semconv).

## 2. Stitch where present (step 2c.2)

Group session-bearing spans by `session.id`, order by `start_time`, diff consecutive actions.
`scripts/session_stitch.py` does this as a pure function (`stitch()`), reproduced here on the
5,241 `ad` chains (28,021 spans exported read-only to CSV, nanosecond-precise parse):

**Think-time** (next.start − prev.end, clipped ≥ 0; 1.0 % of gaps were negative/overlapping):

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

## 4. Side-by-side — Browser journey, span-only vs Path B (astroshop)

The **Browser** archetype's page views are exactly the ad-bearing views that carry `session.id`.

| dimension | span-only (tiers 2a/2b, pre-ISI-5693) | **Path B (ISI-5693)** |
|---|---|---|
| session boundary | none — "no notion of a session" (R5) | real: 5,241 `session.id` chains |
| actions/session | inferred from a self-contained trace | **measured 5.35** (p50 5, p99 7) |
| inter-action think-time | **assumed** flat constant (analyst guess) | **measured** empirical dist, p50 **7.2 s** / p90 27.7 s / p99 45.1 s |
| session duration | n/a | p50 47 s, p99 96 s |
| think-time on steps | absent | `thinkTime` object on 4/5 Browser steps |
| Buyer (checkout) path | self-contained checkout trace | **unchanged** — no `session.id` on checkout/payment spans |
| dependency | none | none (Grail only; no RUM, no classic token, no PII) |

Net: the Browser journey's pacing is now data-derived, not assumed — a strict R5 fidelity gain
for the dominant (99.1 % weight) journey. The Buyer journey is honestly left on span-order
inference because the signal does not reach its spans.

## 5. Generalization check (step 2c.4) — app-agnostic

The stitcher keys **only** on `session.id`, never on anything browser-specific. Confirmed live:
`smartfreight-agent-service` — a **non-browser A2A agent** — carries `session.id` and stitches
cleanly into 131 single-action chat sessions. Single-action sessions correctly yield **no**
think-time (`think_time_spec()` returns `None`) rather than a fabricated one. Any service that
propagates `session.id` is stitchable, browser or not. ✓

## Deliverables (shipped)

- `skills/workload-model/scripts/session_stitch.py` — pure Path B module: `stitch()`,
  `think_time_spec()` (empirical/exponential), `session_coverage()`, ns-precise ISO parse.
- `skills/workload-model/scripts/schema.json` — additive `source.sessionIdCoverage` (R5 audit).
- `skills/workload-model/scripts/emit.py` — threads coverage onto the model + renders the R5
  Path B proposal line (both the `hasSessionSignal` and the 0 %-fallback branch).
- `skills/workload-model/scripts/build_wkf10640.py` — astroshop build now stitches the Browser
  journey think-time from `session.id` chains, records coverage, bumps to **rev 2**, refines R5.
- `skills/workload-model/fixtures/wkf10640_session_stitch.json` — live facts + real think-time
  samples (deterministic replay without tenant access).
- `skills/workload-model/tests/test_session_stitch.py` — 12 tests (ordering, think-time clip,
  coverage %, empirical/exponential spec, single-action→None, max-gap split, fixture repro).

## Methodology note for BigBoss (fold into §3.1 step 2c)

Step 2c tier (ii) is now **implemented and default-on**: the extractor detects `session.id` on
spans, stitches sessions where present, records coverage, and falls back to span-order where
absent. Reality on wkf10640: the signal exists but is **sparse** (0.056 % tenant-wide, 2
services, single op each) because the demo apps do not propagate it end-to-end. To realise the
full R5 closure the **apps** must propagate `session.id` as baggage across all services — an
instrumentation recommendation, not a SCOPE change. Path A (RUM/USQL fusion) remains the only
route to true browser user-session journeys and stays board-gated (ISI-5691).

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

Token `tenant-b-read` still un-rotated (flagged to board since ISI-5684) — valid for this round.
