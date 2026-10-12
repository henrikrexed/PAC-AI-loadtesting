---
name: workload-model
description: >-
  SCOPE stage of the AI load-testing loop. Turns (service, timeframe, environment) into a
  schema-valid workload-model.json + scenario-proposal.md, gated by G0. Dual-source
  extraction (OTel spans + Istio/Envoy access logs) via DQL, front-end auto-discovery,
  1-6 scenario clustering, load + ramp derivation, cacheProfile sizing. Use when the user
  says "scope a load test", "build a workload model", "extract a scenario from production",
  or starts the load-testing loop.
---

# workload-model (SCOPE)

Turns a running system's telemetry into an approved, schema-valid workload model.

**Contract.** Input: `service` + `timeframe` + `environment` (your observability backend —
written for Dynatrace Grail/DQL; query pack below). Output: `out/<target>/workload-model.json`
(schema-valid, G0-passed) + `scenario-proposal.md`. The proposal is the **human VALIDATE gate** —
no synthesis or run may proceed until a person approves it, bound to the model revision+hash.

**Configuration (no hard-codes).** All environment wiring comes from env vars (see root
`.env.example`):

| Variable | Purpose |
|---|---|
| `DT_ENDPOINT` | Dynatrace environment URL, e.g. `https://your-env.live.dynatrace.com` |
| `DT_API_TOKEN` | read-only API token (scopes: `storage:spans:read`, `storage:logs:read`, and `storage:user.events:read` if you use RUM events) |
| `DT_TIMEFRAME` | default extraction window, DQL syntax (e.g. `-3h`) |

Run queries with any DQL-capable client (`dtctl dql`, REST `/api/v2/query/execute`,
or the Notebook UI). Everything in `scripts/` is **pure and deterministic**: the caller runs
the DQL and injects the rows — no telemetry I/O in the library.

## Workflow

1. **Timeframe sanity.** Confirm the window is deploy-free and incident-free (DQL on deployment
   events / problem records). Shrink/shift and record why if not. Record exclusions.
2. **Dual-source extraction** (run the DQL pack below live; confirm every field name in YOUR tenant):
   - **2a. Front-end discovery (G1)** — earliest-start root span per trace → noise classifier →
     load-driver-vs-edge-server tiebreak. Do **not** assume the front-end.
   - **2b. Istio/Envoy access logs + span fusion** — authoritative HTTP surface + `x-request-id`
     chaining; front-end resolved at `istio-ingressgateway`; fuse on `trace.id`≈`x-request-id`.
     **If access logs are absent, record the spans-only caveat** (G0 criterion 11) and recover
     the HTTP surface from server-span `span.name` routes instead.
3. **Build behavioral journeys (G1), then cap to 1-6.** A journey is a multi-step *user flow*,
   not a single span. Two stages:
   - **Behavioral archetypes (`scripts/archetypes.py`) — primary grouping.** Split entry flows
     by **business outcome**: does the flow place an order (reach an order-terminal service —
     `payment`/`checkout`/`charge`/`order`, matched structurally, not hard-coded)? The same
     engine classifies ANY terminal outcome (tool-use for agent apps, submit for forms, etc.)
     via `classify_by_terminal()`. Each journey's `steps[]` is the ordered sequence
     **reconstructed from the trace span-tree** (`collectArray` over `sort start_time asc`).
   - **Jaccard sub-split (`scripts/clustering.py`) — secondary.** If one archetype still fans
     into structurally distinct flows, sub-split by Jaccard(svcSet)≥0.6 **and** op-name stem;
     high-reach flows (reach≥10) never merge; keep cumulative coverage ≥0.80 and ≤6 journeys.
   - **Session-stitch (`session_stitch.py`, also shipped as `/utilities`) — step 2c tier (ii).**
     Where spans carry an OTel `session.id` (session semconv, baggage→attribute), group by it,
     order by start → **real** session chains + **measured** inter-action think-times + session
     boundaries. **Validity check first:** the id must sit on each *action's* entry span. A
     leaf-/single-op id (e.g. an ad-fetch call) yields only that op's *cadence*, not a journey —
     verify via `session.id`→`trace.id`→entry-op and a funnel-reach join before using it for
     pacing.
   - **RUM user sessions (`rum_sessions.py`, also shipped as `/utilities`) — step 2c PREFERRED
     when RUM is present.** Dynatrace RUM is Grail/DQL-native via `fetch user.sessions`
     (session shape: action/navigation counts, duration, bounce — one row per real-user session)
     and `fetch user.events` (ordered per-action navigation → exact sequence + think-times +
     real pages), keyed by `dt.rum.session.id`. `user.events` needs OAuth scope
     `storage:user.events:read`; `user.sessions` typically does not. Scrub PII (geo / user / IP)
     from any RUM field before it reaches the model dataset.
   - **Dual-source merge (`scripts/source_merge.py`) — combine RUM + spans.** Run both analyses,
     then reconcile per request/endpoint key: **common** (in RUM and spans) → RUM user session is
     primary, extrapolated by `factor = span_rate / rum_rate` (the unsampled span side calibrates
     RUM's sampling — no sampling-rate config needed); **span-only** (no RUM match) → span-order
     HTTP scenario; **rum-only** (no server span) → **dropped** (nothing to drive server-side).
     App-agnostic — works for non-browser apps too (validated on an agent app).
4. **Code-link** each journey step (`codeRef = path#symbol`); flag `unlinked: true` otherwise.
5. **Derive load + ramp (G3)** — `scripts/shaping.py`: pace (count/window, sampling-corrected),
   Little's Law concurrency **from the server span, never the load-driver wrapper**, CoV-gated
   ramp shaping (<0.15 → one steady stage; else ≤6 piecewise-linear stages) with a **mandatory
   ramp-down tail**.
6. **cacheProfile (G4)** — for cache-fronted payloads, size `keyCardinality` from the observed
   distinct-key count (or R×T×m_prod minimum), fit Zipf `distributionAlpha`, set `targetHitRatio`
   to the production ratio. Reuse the real key pool so the test reproduces (not collapses) the cache.
7. **Emit + self-validate** — `scripts/emit.py` assembles the model + proposal; `scripts/g0_gate.py`
   enforces G0. Emission is refused unless G0 passes.

`scripts/build_example.py` is the worked end-to-end reference (synthetic example extraction →
artifacts in `out/example-frontend/`; run it to see the whole pipeline without a tenant).

## DQL pack (validated field names; confirm on YOUR tenant)

`duration` is **ns**; `start_time`/`end_time` are the usable span timestamps (`timestamp` is
empty on spans). `request.is_root_span == true` is validated; `isEntrySpan()` is illustrative
only. Grail snaps `makeTimeseries`/`bin` interval upward over long windows (~1000-bucket cap) —
read the returned interval before computing CoV.

**G1-C — front-end discovery (earliest-start root per trace):**
```dql
fetch spans, from: $DT_TIMEFRAME
| filter request.is_root_span == true
| sort start_time asc
| summarize entryService = takeFirst(service.name), entryOp = takeFirst(span.name), by: { trace.id }
| summarize traces = count(), by: { entryService, entryOp }
| sort traces desc
```
Noise classifier drops: `GET /health|/healthz|/livez|/readyz`, `GET /metrics`, `flagd *`,
`span.kind == "consumer"` (Kafka `* receive`, `order-consumed`). Keep the external originator
(load-generator/driver) or the edge server (`span.kind=="server"`, `*-proxy`/`*gateway`/`ingress`).

**2b access-log availability probe (run FIRST; drives G0 criterion 11):**
```dql
fetch logs, from: $DT_TIMEFRAME | filter k8s.container.name == "istio-proxy" | summarize lines = count()
```
`lines > 0` → enumerate the edge HTTP surface by `{authority, method, path, response_code}` and
chain by `request_id`. `lines == 0` → **access logs unavailable**: set
`metadata.source.accessLogAvailability = "unavailable"` and record the spans-only caveat in the
proposal; recover the HTTP surface from the server-span route query below.

**G1-E — per-journey reach + service set (clustering input):**
```dql
fetch spans, from: $DT_TIMEFRAME
| filter request.is_root_span == true and service.name == $entryService and startsWith(span.name, $entryPrefix)
| fields trace.id, entryOp = span.name
| join [ fetch spans, from: $DT_TIMEFRAME | summarize services = collectDistinct(service.name), by: { trace.id } ],
       kind: inner, on: { trace.id }, fields: { services }
| fieldsAdd nsvc = arraySize(services)
| summarize traces = count(), avgReach = avg(nsvc), svcSet = takeAny(services), by: { entryOp }
| sort traces desc
```

**G3-A — per-journey pace:** `summarize calls = count(), by: { entryOp }` on the same filter.

**Server-span baseline + Little's Law inputs (NOT the wrapper):**
```dql
fetch spans, from: $DT_TIMEFRAME
| filter span.kind == "server" and service.name == $frontendServer
| summarize p50 = percentile(duration,50)/1000000.0, p95 = percentile(duration,95)/1000000.0,
            p99 = percentile(duration,99)/1000000.0, mean = avg(duration)/1000000.0, by: { span.name }
```
Observed concurrency (busy-time integral): `summarize sum(duration)` ÷ window_ns.

**G3-B — per-minute CoV:**
```dql
fetch spans, from: $DT_TIMEFRAME | filter request.is_root_span == true and service.name == $entryService and startsWith(span.name, $entryPrefix)
| summarize c = count(), by: { min = bin(start_time, 1m) }
| summarize meanRpm = avg(c), sd = stddev(c) | fieldsAdd cov = sd / meanRpm
```

**G4 — cache key cardinality:** `filter service.name == $cacheService and isNotNull($keyAttr)
| summarize keys = countDistinctExact($keyAttr), reads = count()`.

**Session-stitch (step 2c ii):**
```dql
fetch spans, from: $DT_TIMEFRAME
| filter isNotNull(session.id)
| fields session.id, start_time, duration, service.name, span.name
```

**RUM user sessions (step 2c preferred when RUM present):**
```dql
fetch user.sessions, from: $DT_TIMEFRAME
| summarize sessions = count(), actionsP50 = percentile(user_action_count,50),
            durationP50 = percentile(duration,50)/1000000000.0, by: { frontend.name }
```

## G0 exit gate (`scripts/g0_gate.py`) — all must pass before VALIDATE

schema-valid · coverage ≥0.80 · journeys ∈ [1,6] · every step `codeRef` or `unlinked` ·
every journey server-span baseline (p50/p95/p99/errorRate) · Little's Law ratio ∈ [0.5,2.0] ·
every `dependsOn` has a `correlates` edge (G2) · `cacheProfile.targetHitRatio>0` ⇒ `keyCardinality` (G4) ·
caps declared · all DQL run live · **access-log availability `available`, OR `unavailable` with a
spans-only caveat in the proposal** · every journey tagged `evidenceSource` (span/accesslog/both).

Run: `python3 scripts/g0_gate.py <model.json> <proposal.md>` (exit 0 iff G0 passes).

## Residual caveats (MUST appear in every proposal — never silently dropped)

- **R1** record the source sampling ratio; flag rare/error/under-sampled journeys in Risks.
- **R2** SCOPE models *mean* arrival; no peak-envelope profile yet.
- **R5** extraction and validation share telemetry blind spots (async fan-out, websockets,
  fire-and-forget); cross-check ≥1 run against infra metrics, not telemetry alone.

## Files

- `scripts/schema.json` — workload-model JSON schema (draft-07)
- `scripts/archetypes.py` — G1 behavioral-journey archetypes (classification by business outcome)
- `scripts/clustering.py` — G1 Jaccard + stem sub-clustering / ≤6 cap
- `scripts/shaping.py` — G3 pace / Little's Law / CoV ramp shaping
- `scripts/emit.py` — model assembly + proposal rendering + canonical hash
- `scripts/g0_gate.py` — G0 self-validation (schema + 12 exit criteria)
- `scripts/rum_sessions.py` / `scripts/session_stitch.py` / `scripts/source_merge.py` —
  step 2c session signals (mirrored as standalone CLIs in `/utilities`)
- `scripts/build_example.py` — worked end-to-end example on the synthetic fixture
- `fixtures/*.json` — SYNTHETIC example extractions (no real telemetry)
- `tests/` — pytest suite (run: `python3 -m pytest tests/ -q`)

## Interface for the next skill (SYNTHESIZE / `k6-synthesis`)

Consumes the approved `workload-model.json`: `arrivalProfile.model` (open/closed) +
`stages[].shape` → k6 executors; `journeys[].steps[].correlates` → extract/inject chain;
`payloads[].cacheProfile` → cache-avoidance payload generation; `baseline` → abort thresholds.
