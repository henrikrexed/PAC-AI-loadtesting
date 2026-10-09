# G1/G3 — observability-extraction findings note

*ISI-5625 (child of [ISI-5622](/ISI/issues/ISI-5622)) · planning only, no code · 2026-10-09*
*Validated live against Dynatrace tenant **oat05854** (`dynatrace-dev` dtctl context). Builds on the validated pack in [`phase4-t0-dql-validated.md`](phase4-t0-dql-validated.md); closes the two gaps in [`methodology.md`](methodology.md) §3.1 (front-end discovery + scenario cap) and §3.5 (load + ramp shaping).*

This note proposes the queries and heuristics for the SCOPE stage to (G1) **discover the front-end and reduce journeys to 1–6 named scenarios** and (G3) **derive pace, concurrency, and ramp shape from telemetry** — with every query run against the live tenant and its real quirks flagged. It is a design note, not an implementation; open questions are called out for Henrik.

---

## 0. What the live tenant looks like (grounding)

Full OpenTelemetry astronomy-shop demo flowing to oat05854, driven by a `load-generator` (locust) that emits **named user journeys as root spans** (`user_browse_product`, `user_checkout_multi`, …). Two quirks dominate the design:

1. **Trace fragmentation.** `request.is_root_span == true` is *not* unique per trace — context propagation is partial, so a single `trace.id` can carry up to **27 root spans** (per-min, 2 h window: 4 585 traces have 1 root; thousands have 5/10/18/21+). Naïve "root service = entry service" is wrong.
2. **Entry noise.** The top raw root-span emitters include health/metrics scrapes (`GET /health` on `memos`/`honcho`, `GET /metrics`), feature-flag polling (`flagd …/ResolveBoolean`), and Kafka consumers (`fraud-detection: orders receive`). None are application traffic.

Both must be handled explicitly or front-end discovery picks the wrong service.

---

## G1 — front-end discovery + scenario cap (1–6)

### G1.1 Discover the entry point (don't be told it)

Root-span **count** alone is misleading: `frontend` (160 k roots/24 h) outranks `frontend-proxy` (83 k), and the lexical `takeMax(service.name)` tiebreak silently mis-assigns fragmented traces to whichever root service sorts last (we observed `shipping` falsely credited with reach 12). **Fix: attribute each trace to the earliest-starting root span.**

```sql
-- G1-C: entry point = earliest-start root span per trace  (validated)
fetch spans, from: -2h
| filter request.is_root_span == true
| sort start_time asc
| summarize entryService = takeFirst(service.name),
            entryOp      = takeFirst(span.name),
  by: { trace.id }
| summarize traces = count(), by: { entryService, entryOp }
| sort traces desc
```
Notes validated live: `start_time`/`end_time` are the usable span timestamps (`timestamp` is empty on spans); `takeFirst` after `sort start_time asc` yields the true originator.

**Classifier applied to the ranked (service, op) list** — keep a candidate only if it is application traffic:
- **drop operational ops**: `GET /health`, `/healthz`, `/livez`, `/readyz`, `GET /metrics` (regex on op name);
- **drop infra RPC / polling**: `flagd *.Service/*`, config/stream endpoints;
- **drop async consumers**: `span.kind == "consumer"` (Kafka `… receive`, `order-consumed`) — these are downstream, not front-ends;
- **keep external originators**: a load driver emitting `user_*` client/internal roots, **or** the edge/ingress server (`span.kind == "server"`, names like `*-proxy`, `*gateway`, `ingress`, `envoy`).

**Tiebreak between "load driver" and "edge server" (frontend-proxy/frontend):** prefer whichever is *earliest in the trace*. Here the `load-generator` `user_*` span starts before the `frontend-proxy` ingress server span, so it is correctly the originator — and conveniently its op names are already human-legible journeys. In a production window with no synthetic driver, the classifier falls through to the edge server (`frontend-proxy ingress`) as the front-end.

**Confirm with reach** — the real front-end's traces touch the largest/deepest slice of the graph:

```sql
-- G1-E: per-journey downstream reach + service set  (validated; join works on this tenant)
fetch spans, from: -1h
| filter request.is_root_span == true and service.name == "load-generator"
         and startsWith(span.name, "user_")
| fields trace.id, entryOp = span.name
| join [ fetch spans, from: -1h
         | summarize services = collectDistinct(service.name), by: { trace.id } ],
       kind: inner, on: { trace.id }, fields: { services }
| fieldsAdd nsvc = arraySize(services)
| summarize traces = count(), avgReach = avg(nsvc), svcSet = takeAny(services),
  by: { entryOp }
| sort traces desc
```

### G1.2 Coverage + clustering to 1–6 named scenarios

Application journeys and volumes (load-generator `user_*` entries, 1–2 h window):

| journey | traces (2 h) | share | cum. | reach |
|---|---|---|---|---|
| user_browse_product | 1816 | 33.9% | 33.9% | 4 |
| user_add_to_cart | 1000 | 18.7% | 52.6% | 5 |
| user_get_ads | 536 | 10.0% | 62.6% | 4 |
| user_view_cart | 506 | 9.5% | 72.1% | 4 |
| user_get_recommendations | 472 | 8.8% | **80.9%** | 5 |
| user_get_product_reviews | 353 | 6.6% | 87.5% | 4 |
| user_ask_product_ai_assistant | 183 | 3.4% | 90.9% | 4 |
| user_index | 172 | 3.2% | 94.1% | 3 |
| user_checkout_multi | 159 | 3.0% | 97.1% | **12** |
| user_checkout_single | 155 | 2.9% | 100% | **12** |

**Coverage rule unchanged (≥80%)**: rank filtered entries by volume, accumulate until cumulative ≥ 0.80 — here the top **5** journeys already reach 80.9%.

**Clustering heuristic to ≤6 named scenarios** — merge journeys that share a **structural fan-out signature** (downstream `svcSet` / `avgReach`) *and* a semantic op-name stem, keeping each merged cluster's cumulative weight explicit:

| # | scenario (human-legible) | merges | reach | weight |
|---|---|---|---|---|
| 1 | **Browse product page** | browse_product + get_ads + get_product_reviews + ask_product_ai_assistant | 4 | ~53.9% |
| 2 | **Cart** | add_to_cart + view_cart | 4–5 | ~28.2% |
| 3 | **Recommendations** | get_recommendations | 5 | ~8.8% |
| 4 | **Checkout** | checkout_single + checkout_multi | 12 | ~5.9% |
| 5 | **Home** | user_index | 3 | ~3.2% |

Five named scenarios, 100% coverage, each with a telemetry-derived weight → drop straight into `workload-model.json` `spec.journeys[].weight`. Checkout stays its own cluster despite low weight because its reach-12 signature is structurally unique (full transactional back-end) and is the highest-risk path. If a tenant yields >6 clusters after the merge, drop the lowest-weight clusters *only while cumulative weight stays ≥0.80* and record the dropped tail in the proposal.

> **Clustering rule, stated normatively:** two journeys merge iff (a) Jaccard(svcSet_a, svcSet_b) ≥ 0.6 **and** (b) they share an op-name stem (or the operator confirms the semantic grouping). Checkout's svcSet is disjoint from the browse cluster → never merges.

---

## G3 — load + ramp shaping from telemetry

### G3.1 Pace (TPS/TPM) per scenario

Per-scenario arrival rate = entry-trace count ÷ window, summed over the cluster's member ops. Tenant reported `Sampled: no` for these windows, so raw counts are rate-accurate (no sampling correction needed here — but §3.5 sampling-parity still applies when a tenant *does* sample).

```sql
-- G3-A: per-journey arrival rate (validated)
fetch spans, from: -1h
| filter request.is_root_span == true and service.name == "load-generator"
         and startsWith(span.name, "user_")
| summarize calls = count(), by: { entryOp = span.name }
| fieldsAdd tpm = calls / 60.0, tps = calls / 3600.0
| sort calls desc
```

### G3.2 Concurrency / VUs via Little's Law — **use the server span, not the load driver**

Critical finding: the load-generator's `user_*` wrapper `duration` bakes in client think-time and is quantized — `user_checkout_*` reports a flat **15 000 ms** (the locust `wait_time`), not latency. Feeding that into Little's Law inflates concurrency ~1000×. The response-time term MUST come from the **server-side entry span**:

| source | checkout latency | browse latency |
|---|---|---|
| load-generator wrapper (❌ think-time baked in) | 15 002 ms (flat) | 7 ms |
| `frontend` server span (✅ true response time) | p50 3 ms / p95 36 ms / **p99 75 s** | — |

- **Open model (primary):** `concurrency ≈ arrival_rate × mean_server_response_time` (§3.1 step 5 Little's-Law check uses the *server* mean).
- **Closed model (VU-bound):** `VUs ≈ arrival_rate × (server_response_time + think_time)`, where `think_time = wrapper_duration − server_response_time` per journey (the wrapper is exactly response+think, so `VUs ≈ arrival_rate × wrapper_duration` is the shortcut). This recovers the think-time distribution for `spec.journeys[].steps[].thinkTime` directly from telemetry.
- **Heavy tail flag:** `frontend` p99 = 75 s vs p50 3 ms. The arrival/latency baseline MUST carry p99, and abort thresholds (§3.4) must be set above the real p99 tail or every run self-aborts.

```sql
-- server-side response time for Little's Law + baseline (validated; duration is ns)
fetch spans, from: -1h
| filter span.kind == "server" and service.name == "frontend"
| summarize p50_ms = percentile(duration,50)/1000000.0,
            p95_ms = percentile(duration,95)/1000000.0,
            p99_ms = percentile(duration,99)/1000000.0
```

### G3.3 Ramp-up / ramp-down from the per-minute arrival curve

Procedure the agent runs per scenario:

1. **Build the curve** — `makeTimeseries count(), interval: 1m` on the scenario's entries (§3.1 query 2).
2. **Steady-vs-ramp decision** — compute CoV = stddev ÷ mean of the per-minute counts. If **CoV < ~0.15 → steady**: emit a single `constant-arrival-rate` stage. Else → extract the ramp.
3. **Ramp extraction** (when CoV ≥ 0.15): find the global-peak minute; the monotone-rising prefix = ramp-up, the monotone-falling suffix = ramp-down, the middle = plateau. Piecewise-linear-segment the curve down to **≤6 stages** (one `ramping-arrival-rate` stage per segment, `rate` = segment mean), so the shape — not just the average — is preserved in `spec.arrivalProfile.stages`.

```sql
-- G3-B: per-minute counts for CoV + segmentation  (validated)
fetch spans, from: -3h
| filter request.is_root_span == true and service.name == "load-generator"
         and startsWith(span.name, "user_")
| summarize c = count(), by: { min = bin(start_time, 1m) }
| summarize meanRpm = avg(c), sd = stddev(c), minRpm = min(c), maxRpm = max(c)
| fieldsAdd cov = sd / meanRpm
```

**Live result:** mean ≈ 45 rpm, CoV **0.10** over 3 h and **0.10** over 24 h (flat across the full day — no diurnal shape; the only non-flat bins are partial window edges). → On this tenant the ramp-extractor correctly emits **one steady stage**. Validating a *non-trivial* ramp (ramp-up→plateau→ramp-down) end-to-end needs either a production window with diurnal traffic or a deliberately-ramped driver profile — see open questions.

> **Gotcha for the implementer:** Grail snaps `makeTimeseries`/`bin` interval upward over long windows (~1000-bucket cap) — e.g. a 90 d query silently becomes 2 h buckets. Read the returned interval, don't assume the requested one, before computing CoV or segmenting (observed previously on this tenant).

---

## Open questions (for Henrik / parent plan ISI-5622)

1. **Front-end semantics.** When a synthetic load driver is present (as here), it is the true traffic originator and its `user_*` ops *are* the journeys — but in real production the front-end is the edge server (`frontend-proxy ingress`). Should SCOPE prefer the driver when present (richer journey names) or always resolve to the edge server for production-faithfulness? Proposed default: **prefer the driver only in non-prod analysis windows; resolve to the edge server for any window intended to model production.**
2. **Ramp demo.** The T0 tenant traffic is flat (CoV 0.10), so G3's ramp extraction can't be shown firing on live data. Do we (a) point the Phase-4 demo at a window/driver with a real ramp, or (b) ship a deliberately-ramped locust profile to generate one? Recommend (b) for a repeatable, committed demo artifact.
3. **Clustering thresholds.** Jaccard ≥ 0.6 and the ≤6 cap are proposed, not yet tuned on a second tenant. Confirm the thresholds before baking them into the `workload-model` skill.
4. **Think-time distribution shape.** We can recover per-journey think-time (wrapper − server), but `spec` currently models `constant/uniform/exponential/empirical`. Checkout's flat 15 s is constant; others are near-zero. Which distribution does SCOPE fit by default — and does it matter below the latency noise floor?

---

## Validation summary

All six query shapes above were executed live on oat05854 (2026-10-09) and returned the cited numbers; field-name/function quirks are consistent with [`phase4-t0-dql-validated.md`](phase4-t0-dql-validated.md) (`request.is_root_span`, `span.kind`, `duration` in ns, `start_time`). New quirks surfaced and documented here: multi-root fragmentation + lexical-tiebreak mis-attribution (G1), load-driver wrapper vs server-span latency for Little's Law (G3), and the Grail interval-snap caveat. No code was written; this note is the requested findings deliverable.
