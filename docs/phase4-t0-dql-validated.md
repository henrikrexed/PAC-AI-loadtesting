# Phase 4 T0 — Validated §3.1 DQL pack (oat05854) + baggage-promotion proof

*ISI-4089 · validated live against Dynatrace tenant **oat05854** (`dynatrace-dev` dtctl context,
`https://oat05854.dev.dynatracelabs.com`) on 2026-09-09. Applies [`methodology.md`](methodology.md) §3.1 / §3.5.*

This is the **O11y query-validation gate** output. Every query in the methodology §3.1 pack was run
against the live tenant and its field names / functions corrected against sample output before being
baked into SCOPE/ANALYZE.

## Field-name corrections (methodology §3.1 illustrative → live Grail on oat05854)

| Methodology §3.1 (illustrative) | ❌ Live result | ✅ Corrected (validated) |
|---|---|---|
| `isEntrySpan()` | `UNKNOWN_FUNCTION` — no such function on this tenant | `request.is_root_span == true` (true trace entry) — per-service server entry: `span.kind == "server"` |
| `count(error)` | not an aggregation; `error` is not a field | `countIf(request.is_failed == true)` |
| `duration` (assumed ms) | value is in **nanoseconds** (e.g. `11676000` = 11.68 ms) | divide by `1000000.0` for ms in output |
| `service.name`, `span.name` | ✅ valid as-is | unchanged |
| `makeTimeseries count(), interval: 1m` | ✅ valid as-is | unchanged |

Other validated span fields available for ANALYZE: `trace.id`, `span.id`, `span.parent_id`,
`span.kind` (`server`/`client`/…), `request.is_failed` (bool), `request.is_root_span` (bool).
Note `k8s.cluster.name` / `k8s.namespace.name` are **NULL** for the ambient otel-demo already in this
tenant — which is exactly why we isolate our deployment with `deployment.environment == "pac-lt-t0"`
(see below).

## Validated §3.1 query pack (copy-ready; `$service`, `$op`, `$env` bound at run time)

**Isolation clause** — prepend every baseline query with our tag so ambient otel-demo traffic
(NULL-k8s `frontend`/`cart`/… already flowing to oat05854) is excluded:
`filter deployment.environment == "pac-lt-t0"`.

```sql
-- (1) Top entry operations by volume  [$service e.g. "frontend-proxy"]
fetch spans, from: -7d
| filter deployment.environment == "pac-lt-t0"
| filter request.is_root_span == true and service.name == $service
| summarize calls = count(), by: { service.name, span.name }
| sort calls desc | limit 25
```
```sql
-- (2) Arrival curve (per-minute request rate at entry)
fetch spans, from: -7d
| filter deployment.environment == "pac-lt-t0"
| filter request.is_root_span == true and service.name == $service
| makeTimeseries count(), interval: 1m
```
```sql
-- (3) Latency + error baseline per entry operation  (duration ns -> ms)
fetch spans, from: -7d
| filter deployment.environment == "pac-lt-t0"
| filter request.is_root_span == true and service.name == $service and span.name == $op
| summarize calls = count(),
            p50_ms = percentile(duration, 50) / 1000000.0,
            p95_ms = percentile(duration, 95) / 1000000.0,
            p99_ms = percentile(duration, 99) / 1000000.0,
            errs   = countIf(request.is_failed == true)
```
```sql
-- (4) Service-graph fan-out (downstream client edges + rates from traces)
fetch spans, from: -7d
| filter deployment.environment == "pac-lt-t0"
| filter span.kind == "client"
| summarize calls = count(), by: { service.name, span.name }
| sort calls desc | limit 50
```
```sql
-- (5) Timeframe sanity — confirm deploy/incident-free window (error-rate over time)
fetch spans, from: -24h
| filter deployment.environment == "pac-lt-t0" and request.is_root_span == true
| makeTimeseries errs = countIf(request.is_failed == true), total = count(), interval: 10m
```

### ANALYZE separator (methodology §3.5) — synthetic vs baseline
```sql
-- k6 test traffic only (promoted from baggage.synthetic):
fetch spans | filter deployment.environment == "pac-lt-t0" and synthetic == "true"
-- production baseline (loadgen) = same env, synthetic unset:
fetch spans | filter deployment.environment == "pac-lt-t0" and isNull(synthetic)
```

## Live validation evidence (2026-09-09, `frontend-proxy`, ambient window)

```
(1) entry-op volume:  ingress  -> 23,861 calls
(3) latency/error:    ingress  -> calls 23,884 | p50 11ms | p95 74ms | p99 588ms | errs 98
(2) arrival curve:    ~1,450 root spans/min steady (makeTimeseries 1m)
```

## Baggage → attribute promotion — PROVEN (deliverable #2)

Mechanism: `transform/baggage` processor in `pac-lt-collector` promotes span attribute
`baggage.synthetic == "true"` → first-class `synthetic = "true"` (OTTL, auto-prefixed to
`span.attributes[...]` on collector 0.135). Config: [`../deploy/otel-demo/pac-lt-collector.yaml`](../deploy/otel-demo/pac-lt-collector.yaml).

Probe: an OTLP/HTTP span (`service.name=pac-lt-probe`) carrying `baggage.synthetic=true` was POSTed
to the collector; DQL on oat05854 returned it with the promoted attribute:

```sql
fetch spans, from: now()-10m | filter service.name == "pac-lt-probe"
| fields span.name, synthetic, baggage.synthetic, deployment.environment
```
```
span.name        synthetic  baggage.synthetic  deployment.environment
pac-lt-t0-probe  true       true               pac-lt-t0
```
→ Without this promotion the ANALYZE filter `synthetic == "true"` matches nothing. Confirmed queryable.
