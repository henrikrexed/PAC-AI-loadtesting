---
name: workload-model
description: >-
  SCOPE stage of the AI load-testing loop. Turns (service, timeframe, env) into a
  schema-valid workload-model.json + scenario-proposal.md, gated by G0. Dual-source
  extraction (OTel spans + Istio/Envoy access logs) via dtctl/DQL, front-end auto-discovery,
  1-6 scenario clustering, load + ramp derivation, cacheProfile sizing. Use when the user
  says "scope a load test", "build a workload model", "extract a scenario from production",
  or starts the load-testing loop from methodology.md §3.1.
---

# workload-model (SCOPE)

Implements **methodology.md §3.1** (SCOPE) and the **§4 workload-model schema (draft v1)**.
Parent plan: **ISI-5622 v0.4** (Gate-V1 approved, rev `0a74ca10`). Built under **ISI-5630**.

**Contract.** Input: `service` + `timeframe` + `environment` (Dynatrace tenant via dtctl).
Output: `loadtests/<target>/workload-model.json` (schema-valid, G0-passed) +
`scenario-proposal.md` (§5.2 template). The proposal is the **VALIDATE / Gate-V1** input —
no synthesis or run may proceed until a human approves it, bound to the model revision+hash.

## Build-vs-buy decision (§8 row 1) — BUILD SKILL

Per `docs/skills-mcp-decisions.md`: **build**, grounded in `dtctl` DQL. The extraction logic is
bespoke to our Dynatrace tenant's span/log attributes and to the §4 JSON contract, and must be
deterministic and version-controlled ("observability as code"). No off-the-shelf MCP maps
"DT traces+access-logs → workload-model". Grafana Assistant (NL→k6) and Tracetest are k6-side /
assertion tools, not extraction tools, and are Grafana-Cloud / span-assertion bound — pattern
references only. Dynatrace MCP `discover-*` is a useful *interactive* first pass but not the
deterministic path. **dtctl carries SCOPE; the skill owns the query pack, algorithms, and gate.**

## Workflow

1. **Timeframe sanity.** Confirm the window is deploy-free and incident-free (DQL on deployment
   events / problem records). Shrink/shift and record why if not. Record exclusions.
2. **Dual-source extraction** (run the DQL pack below live; confirm every field name on the tenant):
   - **2a. Front-end discovery (G1)** — earliest-start root span per trace → noise classifier →
     load-driver-vs-edge-server tiebreak. Do **not** assume the front-end.
   - **2b. Istio/Envoy access logs + span fusion** — authoritative HTTP surface + `x-request-id`
     chaining; front-end resolved at `istio-ingressgateway`; fuse on `trace.id`≈`x-request-id`.
     **If access logs are absent, record the spans-only caveat** (G0 criterion 11) and recover
     the HTTP surface from server-span `span.name` routes instead.
3. **Cluster to 1-6 scenarios (G1)** — `scripts/clustering.py`: merge iff Jaccard(svcSet)≥0.6
   **and** op-name stem agrees; high-reach journeys (reach≥10, e.g. checkout) never merge;
   keep cumulative coverage ≥0.80.
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

`scripts/build_example.py` is the worked end-to-end reference (oat05854 frontend → artifacts).

## Validated DQL pack (dtctl; tenant oat05854, 2026-10-09)

Field names confirmed live. `duration` is **ns**; `start_time`/`end_time` are the usable span
timestamps (`timestamp` is empty on spans). `request.is_root_span == true` is validated;
`isEntrySpan()` is illustrative only. Grail snaps `makeTimeseries`/`bin` interval upward over
long windows (~1000-bucket cap) — read the returned interval before computing CoV.

**G1-C — front-end discovery (earliest-start root per trace):**
```dql
fetch spans, from: -2h
| filter request.is_root_span == true
| sort start_time asc
| summarize entryService = takeFirst(service.name), entryOp = takeFirst(span.name), by: { trace.id }
| summarize traces = count(), by: { entryService, entryOp }
| sort traces desc
```
Noise classifier drops: `GET /health|/healthz|/livez|/readyz`, `GET /metrics`, `flagd *`,
`span.kind == "consumer"` (Kafka `* receive`, `order-consumed`). Keep the external originator
(`user_*` driver) or the edge server (`span.kind=="server"`, `*-proxy`/`*gateway`/`ingress`).

**2b access-log availability probe (run FIRST; drives G0 criterion 11):**
```dql
fetch logs, from: -2h | filter k8s.container.name == "istio-proxy" | summarize lines = count()
```
`lines > 0` → enumerate the edge HTTP surface by `{authority, method, path, response_code}` and
chain by `request_id`. `lines == 0` → **access logs unavailable**: set
`metadata.source.accessLogAvailability = "unavailable"` and record the spans-only caveat in the
proposal; recover the HTTP surface from the server-span route query below.

**G1-E — per-journey reach + service set (clustering input):**
```dql
fetch spans, from: -1h
| filter request.is_root_span == true and service.name == $entryService and startsWith(span.name, "user_")
| fields trace.id, entryOp = span.name
| join [ fetch spans, from: -1h | summarize services = collectDistinct(service.name), by: { trace.id } ],
       kind: inner, on: { trace.id }, fields: { services }
| fieldsAdd nsvc = arraySize(services)
| summarize traces = count(), avgReach = avg(nsvc), svcSet = takeAny(services), by: { entryOp }
| sort traces desc
```

**G3-A — per-journey pace:** `summarize calls = count(), by: { entryOp }` on the same filter.

**Server-span baseline + Little's Law inputs (NOT the wrapper):**
```dql
fetch spans, from: -3h
| filter span.kind == "server" and service.name == $frontendServer
| summarize p50 = percentile(duration,50)/1000000.0, p95 = percentile(duration,95)/1000000.0,
            p99 = percentile(duration,99)/1000000.0, mean = avg(duration)/1000000.0, by: { span.name }
```
Observed concurrency (busy-time integral): `summarize sum(duration)` ÷ window_ns.

**G3-B — per-minute CoV:**
```dql
fetch spans, from: -3h | filter request.is_root_span == true and service.name == $entryService and startsWith(span.name, "user_")
| summarize c = count(), by: { min = bin(start_time, 1m) }
| summarize meanRpm = avg(c), sd = stddev(c) | fieldsAdd cov = sd / meanRpm
```

**G4 — cache key cardinality:** `filter service.name == $cacheService and isNotNull($keyAttr)
| summarize keys = countDistinctExact($keyAttr), reads = count()`.

## G0 exit gate (`scripts/g0_gate.py`) — all must pass before VALIDATE

schema-valid · coverage ≥0.80 · journeys ∈ [1,6] · every step `codeRef` or `unlinked` ·
every journey server-span baseline (p50/p95/p99/errorRate) · Little's Law ratio ∈ [0.5,2.0] ·
every `dependsOn` has a `correlates` edge (G2) · `cacheProfile.targetHitRatio>0` ⇒ `keyCardinality` (G4) ·
caps declared · all DQL run live · **access-log availability `available`, OR `unavailable` with a
spans-only caveat in the proposal** · every journey tagged `evidenceSource` (span/accesslog/both).

Run: `python3 scripts/g0_gate.py <model.json> <proposal.md>` (exit 0 iff G0 passes).

## §11 residual caveats (MUST appear in every proposal — never silently dropped)

- **R1** record the source sampling ratio; flag rare/error/under-sampled journeys in §Risks.
- **R2** SCOPE models *mean* arrival; no peak-envelope profile yet (backlog).
- **R5** extraction and validation share telemetry blind spots (async fan-out, websockets,
  fire-and-forget); cross-check ≥1 run against infra metrics, not telemetry alone.

## Schema note (v0.3 → carried additive v0.4 fields)

The §4 schema (draft v1) predates v0.4's dual-source tagging. `scripts/schema.json` adds, as
optional additive fields (draft-07, no `additionalProperties:false`): `source.evidenceSources`,
`source.accessLogAvailability`, `source.samplingRatio`, and per-journey/step `evidenceSource` +
`spanless`. These carry the G0 dual-source reconciliation the v0.4 methodology mandates.

## Files

- `scripts/schema.json` — §4 workload-model JSON schema (+ additive v0.4 tags)
- `scripts/clustering.py` — G1 Jaccard + stem clustering to ≤6 scenarios
- `scripts/shaping.py` — G3 pace / Little's Law / CoV ramp shaping
- `scripts/emit.py` — model assembly + §5.2 proposal rendering + canonical hash
- `scripts/g0_gate.py` — G0 self-validation (schema + 12 exit criteria)
- `scripts/build_example.py` — worked end-to-end example (oat05854 frontend)
- `fixtures/oat05854_extract.json` — live extraction facts (every number from a real DQL run)
- `tests/` — 27 tests (clustering, shaping, G0 incl. access-log-block negative case)

## Interface for the next skill (SYNTHESIZE / `k6-synthesis`, ISI-5631)

Consumes the approved `workload-model.json`: `arrivalProfile.model` (open/closed) +
`stages[].shape` → k6 executors; `journeys[].steps[].correlates` → extract/inject chain;
`payloads[].cacheProfile` → cache-avoidance payload generation; `baseline` → abort thresholds.
