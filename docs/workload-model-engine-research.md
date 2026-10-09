# Workload-model engine — research spike (ISI-5634)

**Parent:** ISI-5622 · **Spike type:** research / planning (prototype OK, no production code) ·
**Author:** Research Engineer · **Date:** 2026-10-09 ·
**Status:** delivered — hand back to BigBoss to fold into `docs/methodology.md` §2.1 and re-scope ISI-5630 / ISI-5631.

## 0. TL;DR

- **Build the engine; build the interchange schema.** No off-the-shelf tool converts
  *traces → end-to-end chained scenarios + Little's-Law load + CoV-gated ramp + cache-avoidance
  datasets* in a backend- **and** tool-agnostic way. The closest prior art (WESSBAS) validates
  our *architecture* (tool-agnostic model + per-tool transformers) but not our feature set.
- **The engine already exists in embryo** as `skills/workload-model/scripts/` (`clustering.py`,
  `shaping.py`, `emit.py`, `g0_gate.py`). This spike's refactor is small and low-risk: change the
  engine's *input* from "dtctl extraction facts" to the **neutral telemetry interchange schema**,
  and the output stays the §4 `workload-model.json`.
- **Packaging:** Python **library-first with a thin CLI entrypoint** (`engine build <interchange.json>
  → workload-model.json`). Pure function, no network, no clock, no unseeded randomness. Reject
  standalone network-MCP and WASM for the engine itself (an MCP *wrapper* around the CLI is a cheap
  later add).
- **§4 is ~90% renderer-complete.** Six concrete gaps listed in §5 — all additive optional fields or
  per-renderer documentation, none structural. Propose a §4 v1.1 additive bump.
- **Thin-slice PoC:** oat05854 frontend — we already hold the live extract *and* the golden
  `workload-model.json`, so the PoC is a **refactor-with-golden-regression** (lowest-risk shape):
  dtctl adapter → interchange.json → refactored engine → existing k6 renderer → assert byte-identical
  to the committed golden + hash match.

---

## 1. Prior-art survey — do we even build it?

### 1.1 The landscape

| Tool / work | Input | Output | Chained scenarios? | Load + ramp derivation? | Cache-avoidance datasets? | Backend-agnostic? | Tool-agnostic? |
|---|---|---|---|---|---|---|---|
| **Grafana `har-to-k6`** | HAR (browser/proxy capture) | k6 script | ✗ flat request list (capture order only) | ✗ none (you hand-write stages) | ✗ | partial (HAR, browser-bound) | ✗ k6 only |
| **`har2locust`** | HAR | Locust `locustfile.py` | ✗ flat | ✗ | ✗ | partial (HAR) | ✗ Locust only |
| **Postman→k6 / OpenAPI→k6** | collection / spec | k6 script | partial (declared order) | ✗ | ✗ | ✗ (not telemetry) | ✗ k6 only |
| **Speedscale** | captured traffic (mesh/proxy/sidecar) | replay "snapshots" + RPS replay | partial (recorded sequence, no abstraction) | partial (replay at observed/multiplied RPS; no Little's-Law VU or ramp shaping) | ✗ (replays recorded bodies; no key-pool resizing) | partial (its own capture) | ✗ Speedscale replay engine |
| **GoReplay (gor)** | live HTTP tap / pcap | replay at ×N rate | ✗ (per-request replay) | partial (rate multiply only) | ✗ | ✗ (its own tap) | ✗ gor only |
| **Tracetest** | OTel traces | **trace assertions** (trace-based *testing*) | n/a — it's a verification tool, not a load modeler | ✗ | ✗ | ✓ (OTLP) | n/a |
| **JMeter proxy recorder / Gatling recorder / Tsung recorder** | live browser session | tool script | partial (recorded order) | ✗ (manual thread-group/injection config) | ✗ | ✗ (browser capture) | ✗ one tool each |
| **WESSBAS** (academic; van Hoorn et al.) | session logs | **tool-agnostic workload DSL** (Markov behavior models + workload intensity) → transformers to JMeter (Markov4JMeter), BenchFlow | ✓ (Markov chain behavior models) | partial (closed-workload intensity + think-time; no Little's-Law VU sizing, no CoV ramp, no ramp-down policy) | ✗ | ✗ (session-log specific) | **✓ (model + per-tool transformer — same pattern we want)** |
| **This engine (target)** | neutral telemetry interchange (OTel-aligned) | §4 `workload-model.json` | ✓ (`journeys[].steps` + `correlates`) | ✓ (pace + Little's-Law VU + CoV-gated ramp + mandatory ramp-down) | ✓ (`cacheProfile`: Zipf α, `keyCardinality`, `targetHitRatio`) | ✓ (adapter boundary) | ✓ (renderer boundary) |

### 1.2 Verdict, per concern

- **End-to-end chained scenarios.** HAR converters and recorders emit *flat* request lists; replay
  tools (Speedscale, GoReplay) preserve chaining only implicitly in recorded order and never abstract
  it into a reusable, parameterizable model with explicit extract→inject correlation. Only WESSBAS
  abstracts sessions (Markov chains), and it is session-log — not OTel-trace — native. **→ BUILD.**
  Our §4 `steps[].correlates` (source → extract → inject) is the asset no library gives us.
- **Load + ramp.** Nothing in the field derives Little's-Law VU ceilings from server-span busy-time,
  CoV-gates the ramp shape, and enforces a ramp-down tail. Replay tools do rate-multiply; WESSBAS does
  closed-workload intensity. **→ BUILD** (`shaping.py` already does this).
- **Cache-avoidance datasets.** No surveyed tool sizes a unique-key pool to *reproduce* a production
  cache-hit ratio (Zipf-α fit, `keyCardinality` = R×T×m_prod floor, seeded backing store). This is
  genuinely novel to our methodology (G4). **→ BUILD.**
- **Backend- & tool-agnostic.** HAR is a *semi-neutral capture* but browser/proxy-bound and flat;
  none are OTel-trace-native feeding a tool-agnostic model. **→ BUILD the engine + both contracts.**

### 1.3 What we *reuse* rather than build

- **Architecture pattern:** WESSBAS is external validation that "neutral model + per-tool transformer"
  is a proven, publishable design — adopt the pattern, not the code.
- **HAR as *one optional adapter input*** for browser-originated flows where traces are thin (an
  `har → interchange` adapter is a future, not core).
- **Execution engines at the *run* layer** (already decided in `docs/skills-mcp-decisions.md`):
  `grafana/mcp-k6` `validate_script`/`run_script` for k6; native JMeter/Gatling/Locust binaries for
  the others. We never rebuild a load generator — renderers emit scripts, commodity engines run them.
- **Payload generators:** `faker`-style libraries behind the `generator: "faker:*"` field (per tool).

**Overall reuse verdict:** BUILD all three layers thin, REUSE the commodity execution engines and
(optionally) HAR capture. The IP is the engine + the two contracts; everything executable underneath
is commodity.

---

## 2. Neutral telemetry interchange schema (adapter → engine contract)

### 2.1 Design decision: layered, OTLP-aligned, provenance-tagged

The §2.1 brief says the interchange carries "traces + HTTP request records + arrival/timing stats +
sampling metadata." The tension is **raw vs pre-aggregated**:

- *Raw-only* (ship every span) keeps the engine maximally pure but is heavy (a 3h window = ~20k root
  traces here) and forces the engine to re-implement percentile/CoV math that Grail/Tempo compute
  natively and cheaply.
- *Aggregate-only* is light but leaks front-end discovery / clustering fidelity into the adapter —
  exactly the logic §2.1 says must live in the **engine**.

**Recommendation — a layered interchange:** *structure travels as records, heavy distributions travel
as summaries*, and every block is **provenance-tagged** (`raw` vs `backend_aggregated`) so the engine
knows what it may recompute vs must trust:

1. **`meta`** — timeframe, exclusions, `samplingRatio`, `coverage` hint, backend id, adapter version.
   (Honors §11 **R1**: sampling blindness is a first-class, mandatory field.)
2. **`traces[]`** — a sampled set of normalized traces; each span mirrors **OTLP/trace semconv**.
   Drives front-end discovery (G1), reach/service-set clustering (G1), correlation-edge mining (G2),
   and think-time. *Provenance: `raw`.*
3. **`httpRequests[]`** *(optional; present when access logs exist)* — authoritative flat HTTP
   surface for spanless recovery (`{method, authority, path, status, durationMs, tsUnixNano,
   requestId, traceId}`). *Provenance: `raw`.*
4. **`arrival[]`** — per-entrypoint per-bucket count histogram → pace + CoV + stages (G3).
   *Provenance: `backend_aggregated` (a `bin()`/`makeTimeseries` rollup).*
5. **`serviceLatency[]`** — per `(service, operation, spanKind)` `{p50,p95,p99,mean,count,
   busyTimeNano}` → server-span baseline + Little's-Law observed concurrency (busyTime ÷ window).
   *Provenance: `backend_aggregated`.*
6. **`keyAccess[]`** *(optional)* — per `(service, keyAttr)` `{distinctKeys, totalReads,
   topKeys[]{key,count}}` → Zipf-α fit + `keyCardinality` (G4). *Provenance: `backend_aggregated`.*

**Why OTLP-aligned span fields:** any OTLP-native backend (Tempo/Jaeger/raw OTLP collector) maps 1:1
with zero translation; only non-OTLP backends (Dynatrace Grail field names — `start_time`, `duration`
ns, `request.is_root_span`, `span.kind`) need a rename table *in the adapter*. This maximizes adapter
reuse and keeps the agnostic boundary honest. The aggregate blocks mirror the **OTel metrics** data
model (histogram/summary) conceptually.

**Engine purity preserved:** because the interchange is a static recorded document, the engine stays a
deterministic pure function regardless of raw-vs-aggregate mix. Aggregates are an *optimization*, not
a backdoor — the engine may optionally recompute any aggregate from `traces[]` when present, to
cross-check the adapter (a cheap R5 guard).

### 2.2 JSON Schema draft (`neutral-telemetry.schema.json`, draft v0.1)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://github.com/henrikrexed/PAC-AI-loadtesting/schemas/neutral-telemetry.schema.json",
  "title": "NeutralTelemetryInterchange",
  "type": "object",
  "required": ["apiVersion", "kind", "meta", "traces"],
  "properties": {
    "apiVersion": { "const": "loadtest.isi/v1alpha1" },
    "kind": { "const": "NeutralTelemetry" },
    "meta": {
      "type": "object",
      "required": ["backend", "timeframe", "windowSeconds", "samplingRatio"],
      "properties": {
        "backend": { "type": "string", "examples": ["dynatrace-dql", "tempo", "jaeger", "otlp-file"] },
        "adapterVersion": { "type": "string" },
        "timeframe": { "type": "string", "description": "ISO interval analyzed" },
        "timeframeNotes": { "type": "string", "description": "deploy/incident exclusions applied" },
        "windowSeconds": { "type": "number" },
        "samplingRatio": { "type": "number", "minimum": 0, "maximum": 1,
          "description": "R1: 1.0 = unsampled; < 1 flags under-sampled journeys downstream" },
        "coverageHint": { "type": "number", "minimum": 0, "maximum": 1,
          "description": "fraction of edge traffic the trace sample is believed to represent" },
        "accessLogAvailability": { "enum": ["available", "unavailable", "unknown"] },
        "queries": { "type": "array", "items": { "type": "string" },
          "description": "provenance: the backend queries the adapter ran (audit trail)" }
      }
    },
    "traces": {
      "type": "array",
      "description": "sampled normalized traces; provenance = raw",
      "items": {
        "type": "object",
        "required": ["traceId", "spans"],
        "properties": {
          "traceId": { "type": "string" },
          "spans": {
            "type": "array", "minItems": 1,
            "items": { "$ref": "#/definitions/span" }
          }
        }
      }
    },
    "httpRequests": {
      "type": "array",
      "description": "optional authoritative HTTP surface from access logs; provenance = raw",
      "items": { "$ref": "#/definitions/httpRecord" }
    },
    "arrival": {
      "type": "array",
      "description": "per-entrypoint arrival histogram; provenance = backend_aggregated",
      "items": {
        "type": "object",
        "required": ["entryOp", "bucketWidthSec", "buckets"],
        "properties": {
          "entryService": { "type": "string" },
          "entryOp": { "type": "string" },
          "bucketWidthSec": { "type": "number", "description": "read from the returned interval (Grail may snap upward)" },
          "buckets": { "type": "array", "items": {
            "type": "object", "required": ["tsUnixNano", "count"],
            "properties": { "tsUnixNano": { "type": "integer" }, "count": { "type": "number" } } } },
          "total": { "type": "number" }
        }
      }
    },
    "serviceLatency": {
      "type": "array",
      "description": "per (service, operation, spanKind) latency summary; provenance = backend_aggregated",
      "items": {
        "type": "object",
        "required": ["service", "operation", "spanKind", "p50Ms", "p95Ms", "p99Ms", "count"],
        "properties": {
          "service": { "type": "string" },
          "operation": { "type": "string" },
          "spanKind": { "enum": ["server", "client", "internal", "producer", "consumer"] },
          "p50Ms": { "type": "number" }, "p95Ms": { "type": "number" },
          "p99Ms": { "type": "number" }, "meanMs": { "type": "number" },
          "count": { "type": "integer" }, "errorCount": { "type": "integer" },
          "busyTimeNano": { "type": "integer", "description": "sum(duration) over window -> Little's Law observed concurrency" }
        }
      }
    },
    "keyAccess": {
      "type": "array",
      "description": "optional per-attribute key popularity for G4 Zipf sizing; provenance = backend_aggregated",
      "items": {
        "type": "object",
        "required": ["service", "keyAttr", "distinctKeys", "totalReads"],
        "properties": {
          "service": { "type": "string" },
          "keyAttr": { "type": "string", "examples": ["app.product.id"] },
          "distinctKeys": { "type": "integer" },
          "totalReads": { "type": "integer" },
          "topKeys": { "type": "array", "items": {
            "type": "object", "required": ["key", "count"],
            "properties": { "key": { "type": "string" }, "count": { "type": "integer" } } } }
        }
      }
    }
  },
  "definitions": {
    "span": {
      "type": "object",
      "required": ["spanId", "service", "name", "kind", "startUnixNano", "durationNano"],
      "properties": {
        "spanId": { "type": "string" },
        "parentSpanId": { "type": "string" },
        "service": { "type": "string", "description": "service.name (resource attr)" },
        "name": { "type": "string", "description": "span.name / operation" },
        "kind": { "enum": ["server", "client", "internal", "producer", "consumer"] },
        "isRoot": { "type": "boolean" },
        "startUnixNano": { "type": "integer" },
        "durationNano": { "type": "integer" },
        "callType": { "enum": ["http", "grpc", "db", "mq", "cache"] },
        "http": {
          "type": "object",
          "description": "OTel HTTP semconv subset",
          "properties": {
            "method": { "type": "string" },
            "route": { "type": "string", "description": "http.route / templated path" },
            "target": { "type": "string", "description": "url.path (concrete)" },
            "authority": { "type": "string", "description": "server.address[:port]" },
            "statusCode": { "type": "integer" }
          }
        },
        "correlationKeys": {
          "type": "object",
          "description": "G2 chaining keys: trace.id approx x-request-id",
          "properties": {
            "requestId": { "type": "string" },
            "sessionId": { "type": "string" }
          }
        },
        "attributes": { "type": "object", "description": "pass-through semconv attrs the engine may mine (e.g. app.product.id)" }
      }
    },
    "httpRecord": {
      "type": "object",
      "required": ["method", "path", "status", "durationMs", "tsUnixNano"],
      "properties": {
        "method": { "type": "string" },
        "authority": { "type": "string" },
        "path": { "type": "string" },
        "status": { "type": "integer" },
        "durationMs": { "type": "number" },
        "tsUnixNano": { "type": "integer" },
        "requestId": { "type": "string" },
        "traceId": { "type": "string" }
      }
    }
  }
}
```

### 2.3 Worked example (real oat05854 window, `-3h`, 2026-10-09)

Grounded in `skills/workload-model/fixtures/oat05854_extract.json` — every number is from a live DQL
run. Trace bodies elided to one representative; aggregates verbatim.

```jsonc
{
  "apiVersion": "loadtest.isi/v1alpha1",
  "kind": "NeutralTelemetry",
  "meta": {
    "backend": "dynatrace-dql",
    "adapterVersion": "dtctl-adapter/0.1",
    "timeframe": "-3h (2026-10-09, deploy-free/incident-free window)",
    "timeframeNotes": "noise classifier dropped health/metrics (memos, honcho), flagd polling, Kafka consumers",
    "windowSeconds": 10800,
    "samplingRatio": 1.0,
    "coverageHint": 1.0,
    "accessLogAvailability": "unavailable",
    "queries": ["fetch spans | filter request.is_root_span==true ...", "fetch logs | filter k8s.container.name=='istio-proxy' -> 0", "..."]
  },
  "traces": [
    {
      "traceId": "t-browse-0001",
      "spans": [
        { "spanId": "a1", "service": "load-generator", "name": "user_browse_product", "kind": "client",
          "isRoot": true, "startUnixNano": 1000000000000, "durationNano": 2300000, "callType": "http" },
        { "spanId": "a2", "parentSpanId": "a1", "service": "frontend-proxy", "name": "ingress", "kind": "server",
          "startUnixNano": 1000000100000, "durationNano": 2100000, "callType": "http",
          "http": { "method": "GET", "route": "/api/products/[productId]/index", "authority": "frontend-proxy", "statusCode": 200 } },
        { "spanId": "a3", "parentSpanId": "a2", "service": "frontend", "name": "GET /api/products/[productId]/index",
          "kind": "server", "startUnixNano": 1000000150000, "durationNano": 2000000, "callType": "http",
          "http": { "method": "GET", "route": "/api/products/[productId]/index", "statusCode": 200 } },
        { "spanId": "a4", "parentSpanId": "a3", "service": "product-catalog", "name": "oteldemo.ProductCatalog/GetProduct",
          "kind": "server", "startUnixNano": 1000000300000, "durationNano": 600000, "callType": "grpc",
          "attributes": { "app.product.id": "2ZYFJ3GM2N" } }
      ]
    }
    /* ... sampled traces for user_add_to_cart, user_get_recommendations, user_checkout_single, user_index, ... */
  ],
  "arrival": [
    { "entryService": "load-generator", "entryOp": "user_*", "bucketWidthSec": 60, "total": 7997,
      "buckets": [ /* 181 bins; meanRpm 44.19, sd 5.45 -> CoV 0.1233 (steady), minRpm 6, maxRpm 57 */ ] }
  ],
  "serviceLatency": [
    { "service": "frontend", "operation": "GET /api/products/[productId]/index", "spanKind": "server",
      "p50Ms": 2, "p95Ms": 3, "p99Ms": 4, "count": 4047, "errorCount": 0 },
    { "service": "frontend", "operation": "POST /api/cart",     "spanKind": "server", "p50Ms": 3, "p95Ms": 5,  "p99Ms": 7,  "count": 1525, "errorCount": 0 },
    { "service": "frontend", "operation": "GET /api/recommendations", "spanKind": "server", "p50Ms": 12, "p95Ms": 15, "p99Ms": 20, "count": 773, "errorCount": 0 },
    { "service": "frontend", "operation": "POST /api/checkout", "spanKind": "server", "p50Ms": 53188, "p95Ms": 106377, "p99Ms": 150441, "count": 528, "errorCount": 0 },
    { "service": "frontend", "operation": "*", "spanKind": "server", "p50Ms": 3, "p95Ms": 15813, "p99Ms": 63252, "meanMs": 2018, "count": 19872, "errorCount": 0, "busyTimeNano": 39960000000000 }
  ],
  "keyAccess": [
    { "service": "product-catalog", "keyAttr": "app.product.id", "distinctKeys": 10, "totalReads": 9032,
      "topKeys": [ {"key":"2ZYFJ3GM2N","count":1001}, {"key":"66VCHSJNUP","count":947}, {"key":"6E92ZMYYFZ","count":921} /* ...10 total */ ] }
  ]
}
```

From this single document the engine deterministically reproduces the committed golden
`loadtests/otel-astronomy-frontend/workload-model.json`: front-end = `frontend-proxy`; 10 raw ops
clustered to 5 journeys (coverage 1.0); open model at pace 0.7365/s with a CoV-driven single steady
stage + mandatory ramp-down; Little's-Law expected 3.705 ≈ observed 3.7 (ratio 1.0014); `cacheProfile`
`keyCardinality` 10, Zipf α ≈ 0.1, `targetHitRatio` 0.99.

**Observability Agent sanity-check needed:** confirm a dtctl/DQL + Istio-log adapter can actually
populate every block above from the ISI-5630 extraction (esp. `serviceLatency.busyTimeNano`,
`arrival.bucketWidthSec` after Grail's interval snap, and `keyAccess.topKeys` cardinality).

---

## 3. Engine packaging & invocation

### 3.1 Options considered

| Form factor | Agent can call? | Offline-deterministic test? | Pure-function fit | Verdict |
|---|---|---|---|---|
| **Importable library (Python)** | via CLI wrapper | ✓ `build_model(dict) -> dict`, trivial fixtures | ✓ native | **recommend (core)** |
| **Thin CLI** (`engine build in.json > out.json`) | ✓ shell out, language-agnostic | ✓ file-in/file-out golden | ✓ | **recommend (entrypoint)** |
| Standalone network MCP server | ✓ | ✗ network/state invites hidden nondeterminism; harder to golden | ✗ violates "no network" | reject for engine (OK as later CLI *wrapper*) |
| WASM module | ✓ | ✓ | ✓ but | reject — no benefit server-side; Python scientific stack doesn't WASM cleanly; added toolchain cost |

### 3.2 Recommendation

**Python library-first, with a thin CLI entrypoint.** Rationale:

1. **The fidelity code already lives in Python** (`clustering.py`, `shaping.py`, Zipf fit, percentile
   math). A rewrite buys nothing and risks regressing the 27 existing tests.
2. **Pure function contract:** `build_model(interchange: dict, *, now: str, seed: int) -> dict`. No
   network, no backend SDK, no wall-clock (`generatedAt` is injected, not read), no unseeded RNG
   (payload sampling uses `spec.payloads[].seed`). This is exactly what makes golden fixtures possible.
3. **CLI gives the agent a language-agnostic door** (`python3 -m workload_model.engine build
   interchange.json --now <ts> --seed 42 > workload-model.json`); the library gives in-process unit
   tests and lets a future MCP/HTTP wrapper reuse it without duplicating logic.
4. **Language boundary to renderers is a file, not a call.** The engine is Python; the k6 renderer is
   Node (`skills/k6-synthesis`, JS — natural, since k6 scripts are JS). That split is fine and
   intentional: the §4 `workload-model.json` file *is* the contract, so each renderer picks whatever
   language suits its target tool.

**Refactor shape (small):** today `emit.py`/`build_example.py` take the dtctl *extract facts* dict.
Introduce `engine.build_model(interchange)` that (a) validates against `neutral-telemetry.schema.json`,
(b) runs front-end discovery + `clustering.py` + `shaping.py` + cacheProfile sizing on the interchange
blocks, (c) emits the §4 model. The dtctl-specific knowledge (`fetch spans`, Grail field names) moves
**out** of the engine into a `dtctl-adapter` that *produces* the interchange. The G0 gate stays where
it is (post-emit self-validation).

---

## 4. Renderer interface (engine output → tool contract)

### 4.1 Is §4 renderer-complete for k6 / JMeter / Locust / Gatling?

Checked each §4 construct against all four tools:

| §4 construct | k6 | JMeter | Locust | Gatling | Verdict |
|---|---|---|---|---|---|
| `arrivalProfile.model` open/closed + `stages[].{duration,rate,shape}` | ramping-/constant-arrival-rate / -vus | Concurrency TG + Throughput Shaping Timer / Thread Group | **closed native; open needs `LoadTestShape`+pacing approximation** | `rampUsersPerSec`/`constantConcurrentUsers` | covered (Locust open = renderer approximation) |
| `littlesLawCheck.expectedConcurrency` → VU ceiling | ✓ clamp to caps | ✓ thread count | ✓ user count | ✓ max concurrent | covered |
| `journeys[].weight` → traffic mix | scale rate | TG weighting | `@task(weight)` | `.randomSwitch` weights | covered |
| `steps[].correlates` extract(`body_json`/`header`/`body_html`/`body_regex`)→inject(`header`/`path_param`/`query_param`/`body_field`) | ✓ | JSON/Regex/Boundary/Header Extractor → Header Mgr/param/body | `.json()`/headers → next req | `.check(jsonPath/header/regex.saveAs)` → session | covered (`body_html`→JMeter Boundary / Gatling regex) |
| `steps[].thinkTime` {constant/uniform/exponential/empirical} | `sleep()` | Constant/Uniform/Gaussian/Poisson timer | `wait_time` | `pause`/`exponentialPauses` | covered (**`empirical`** = renderer-approximation everywhere but k6) |
| `payloads[].fields[]` + `distribution` + `seed` | pre-gen pool JSON | **pre-gen → CSV Data Set** | pre-gen list | **pre-gen → feeder** | covered **iff renderer pre-generates the pool** |
| `payloads[].cacheProfile` (Zipf α, keyCardinality, hitRatio) | ✓ | via CSV pool | via list | via feeder | covered (renderer bakes the key pool; distribution is in the pool, not the tool) |
| `baseline` p50/p95/p99/errorRate → abort thresholds | `thresholds` | assertions / listener | custom | `assertions` | covered |

### 4.2 §4 gap list (concrete, all additive — propose §4 v1.1)

- **G-R1 (medium):** `steps[].operation` conflates method + route (`"POST /api/cart"`). A generic
  renderer must string-parse it. **Add** an optional structured `steps[].request`
  `{ method, pathTemplate, queryParams, headers, bodyPayloadRef }`. k6-synthesis already parses the
  string; structuring it de-risks the non-k6 renderers.
- **G-P1 (medium):** `payloads[].fields[]` have no request-location binding — which field goes into
  body vs query vs path is implicit. **Add** optional `fields[].target`
  `{ into: body_field|query_param|path_param|header, as: <name> }` (mirrors the `correlates.inject`
  shape). Without this, checkout's `email`/`ccNumber` are "assumed body."
- **G-D1 (low/doc):** `stages[].rate` is model-polymorphic (iterations/s when open, VUs when closed)
  and lacks an explicit start-rate / ramp convention. **Document** in §4: a ramping stage ramps *from
  the previous stage's end rate* (first ramping stage starts at 0); `shape` is authoritative for
  ramp_up/plateau/steady/ramp_down.
- **G-E1 (renderer-note):** `empirical` think-time and `body_html` extraction have no native construct
  in JMeter/Gatling/Locust — each renderer documents its approximation (JSR223 timer / Boundary
  extractor / custom pause).
- **G-O1 (renderer-note):** open arrival → Locust requires a `LoadTestShape` + pacing approximation
  (Locust is user/closed-native). The model carries enough (`rate` per stage); the Locust renderer
  must declare the approximation in its capability report.
- **G-X1 (scope note):** non-http `callType` (grpc/db/mq/cache) steps are *topology/baseline*, not
  directly driven. Renderers drive the edge HTTP entrypoint steps; driving an internal grpc/db step
  needs a per-renderer protocol plugin (out of thin-slice scope).

**Net:** §4 is ~90% renderer-complete. All gaps are optional additive fields (G-R1, G-P1), one doc
clarification (G-D1), and three per-renderer capability notes (G-E1, G-O1, G-X1). No structural change.

### 4.3 Renderer plugin interface sketch

A renderer is a **pure function** over the approved model; renderers live in separate packages
(any language) and consume the §4 JSON file:

```
interface Renderer {
  name: string                 // "k6" | "jmeter" | "locust" | "gatling"
  targetTool: string
  schemaRange: string          // compatible §4 versions, e.g. ">=1.0 <2.0"

  // declare what this renderer can/can't honor BEFORE rendering (drives agent warnings)
  supports(model) -> { ok: boolean, unsupported: Array<{feature, reason, approximation?}> }

  // the render itself — deterministic, no network
  render(model, opts) -> { files: Array<{path, content}>, warnings: string[] }
}
```

- **Capability report (`supports`)** is the key agnostic affordance: the Locust renderer returns
  `{feature:"arrivalProfile.model=open", reason:"Locust is closed-native", approximation:"LoadTestShape+pacing"}`
  so the agent can warn the human at VALIDATE time — before generating misleading code.
- **Registry** keyed by tool name; the agent/user picks the tool, the registry returns the renderer.
- **k6 renderer already exists** (`skills/k6-synthesis`) and matches this shape (model-in → files-out,
  V2a static gate). Refactor is cosmetic: expose a `supports()` and formalize the signature.

**Testing Architect sanity-check needed:** validate this interface by prototyping one *non-k6*
renderer stub (recommend **Gatling** — richest open/closed injection DSL, or **Locust** to exercise
the hardest open-model approximation, G-O1) and confirming G-R1/G-P1 are the only blocking gaps.

---

## 5. Build-vs-buy recommendation (per layer) + thin-slice PoC

### 5.1 Per layer

| Layer | Decision | Reuse | Build |
|---|---|---|---|
| **Input adapter** (backend-specific) | **BUILD thin, per backend** | backend SDK/CLI (dtctl, Tempo API, OTLP file reader), HAR parser (optional) | the normalize-to-interchange mapping; one adapter per backend. dtctl adapter = the ISI-5630 query pack, repurposed to *emit interchange* instead of a model. |
| **Workload-model engine** (agnostic) | **BUILD — core IP** | faker libs (payload gen), stdlib stats | front-end discovery, clustering (G1), correlation (G2), Little's-Law + CoV ramp (G3), Zipf cache sizing (G4). *Already ~built in `skills/workload-model/scripts/`; refactor input to interchange.* |
| **Output renderers** (tool-specific) | **BUILD thin, per tool** | **commodity execution engines** (`grafana/mcp-k6`, native JMeter/Gatling/Locust) | model→script codegen per tool. k6 renderer exists (`skills/k6-synthesis`). |

### 5.2 Thin-slice PoC proposal

**Target: oat05854 frontend** — chosen because we *already hold* the live extract
(`fixtures/oat05854_extract.json`) **and** the golden `workload-model.json`, making this a
**refactor-with-golden-regression** (the lowest-risk PoC shape — we know the exact expected output):

1. **dtctl adapter** (`adapters/dtctl/`): run the validated DQL pack (SKILL.md §"Validated DQL pack"),
   emit `interchange.json` conforming to §2.2. *(Observability Agent — reuse ISI-5630.)*
2. **Engine refactor** (`skills/workload-model/scripts/engine.py`): `build_model(interchange)` →
   §4 model, interchange-in only, no dtctl knowledge. Keep G0 gate.
3. **k6 renderer** (existing `skills/k6-synthesis`): feed the emitted model unchanged.
4. **Golden regression:** assert `build_model(interchange_oat05854)` is byte-identical to the committed
   `loadtests/otel-astronomy-frontend/workload-model.json` and `status.hash` matches; assert
   k6-synthesis output is unchanged vs its current fixtures.

**Success criterion:** one backend adapter + engine + k6 renderer reproduce the existing golden on one
real service, proving the three-layer split is behavior-preserving. Then add a second-backend adapter
stub (OTLP-file) reading the *same* interchange to prove agnosticism, and a non-k6 renderer stub
(Gatling/Locust) to prove §5-§4.3.

---

## 6. Validation strategy (engine determinism)

1. **Golden fixtures.** Commit `interchange.json` (recorded from a real window) → `workload-model.json`
   (golden, with `status.hash`). The oat05854 extract already exists; convert it to interchange form
   and freeze the current emitted model as the golden. Test: `build_model(fixture) == golden` **and**
   recomputed `status.hash` matches the stored hash.
2. **Determinism proof (byte-identical, twice).** Run the engine twice on the same fixture in CI;
   assert byte-identical output + identical hash. Enforced by: (a) no network / no wall-clock
   (`generatedAt` injected via `--now`); (b) seeded RNG only (`payloads[].seed`); (c) canonical JSON
   serialization (sorted keys) feeding the sha256 in `status.hash`.
3. **Order-invariance property test.** Randomly permute `traces[]` / `serviceLatency[]` input order →
   output must be identical. This catches non-total sorts in clustering/shaping (every sort must have a
   stable tie-breaker: e.g. journeys sorted by `weight` desc then `id` asc). The strongest determinism
   guard — nondeterministic iteration order is the classic failure mode here.
4. **Provenance round-trip (R1).** Assert `meta.samplingRatio` and `meta.coverageHint` propagate to
   `metadata.source.samplingRatio` and `spec.coverage`; assert under-sampled journeys
   (`samplingRatio < 1`) are flagged for the proposal §Risks.
5. **Cross-check guard (R5).** When `traces[]` is present, optionally recompute an aggregate (e.g. pace
   from arrival buckets vs from trace timestamps) and warn on divergence beyond tolerance — a cheap
   instrumentation-coverage sanity check that doesn't trust the adapter blindly.
6. **Golden-diff review gate.** Any engine change that alters a golden must surface the model diff for
   explicit human review (consistent with the existing `baseline-diff` skill ethos) — determinism is
   not just "stable," it's "stable *and* reviewed when it moves."

The existing 27-test suite (`skills/workload-model/tests/`) already exercises clustering/shaping/G0;
items 2–3 above are the new determinism-specific additions this spike recommends.

---

## 7. Handoff

- **To BigBoss:** fold §2.1 three-layer wording to reference the new `neutral-telemetry.schema.json`
  (adapter→engine) alongside §4 (engine→renderer); re-scope **ISI-5630** (SCOPE → split into
  *dtctl adapter* emitting interchange + *engine* consuming it) and **ISI-5631** (SYNTHESIZE → first
  renderer behind the §4.3 interface); schedule the §4 v1.1 additive bump (G-R1, G-P1, G-D1).
  This spike **unblocks ISI-5622 re-synthesis** and **gates ISI-5630/5631**.
- **To Observability Agent (44c97981) — pull in, don't block:** sanity-check §2.2 against what
  dtctl/DQL + Istio logs can emit (esp. `busyTimeNano`, bucket interval, key cardinality).
- **To Testing Architect (7ed0592a) — pull in, don't block:** validate §4.3 by stubbing one non-k6
  renderer and confirming G-R1/G-P1 are the only blocking §4 gaps.

---

## 8. Scenario reconstruction: ML evaluation (ISI-5635, 2026-10-09)

**Spike question (Henrik, local-board 2026-10-09):** *does scenario-building need machine learning, or
are the deterministic heuristics enough?* Evaluated honestly against the engine's non-negotiable —
**determinism + golden-fixture testability** (its whole value prop). No production code; analysis +
one empirical probe on the live oat05854 fixture.

### 8.0 Recommendation (verdict first)

**Keep the heuristic as v1 and the fallback; add ONE deterministic, ML-*adjacent* sequence miner
(PrefixSpan) as the real fix behind the existing scenario-reconstruction interface; keep all
*stochastic* ML strictly OUTSIDE the engine boundary as an offline, human-reviewed proposal assist.**

The probe below (§8.1) changed the framing: the weakness is **not** "heuristics aren't accurate
enough, so add ML." It is that the **structural feature we chose — the downstream service *set* — is
the wrong signal**: on real traffic it is saturated by the shared ingress/frontend prefix and carries
almost no discriminating power, so 100% of the real clustering work is done by a hand-coded,
demo-specific op-name lookup table (`op_stem()`). That is the opposite of "learned from data," and it
is exactly what will not generalize to a second application. The highest-leverage, determinism-safe
fix is to **change the feature from a set to an ordered sequence** and mine it with a *deterministic*
algorithm — not to bolt a trained model onto the engine. So: **hybrid, staged — ML (where it means
sequence/behavior mining) proposes; heuristic + human dispose; the engine stays a pure function.**

### 8.1 Where the heuristic is weak — grounded in a live probe

`clustering.py` reduces journeys to scenarios by: (1) bucketing on an op-name **stem** (hand-coded
string rules: `cart`/`checkout`/`browse`/`recommendations`/`home`, else first token), then (2) within
a stem bucket, merging iff **Jaccard over the downstream service *set* ≥ 0.6** against the most-similar
member; (3) high-reach journeys (reach ≥ 10, e.g. checkout) are isolated; (4) cap to ≤ 6 while
coverage ≥ 0.80. It is **set-based and order-blind** by construction.

**The probe (all 45 journey pairs in `fixtures/oat05854_extract.json`, live Jaccard):**

- **The set signal is saturated — it barely discriminates.** Every journey shares the same 3-service
  prefix (`frontend`, `load-generator`, `frontend-proxy`). With 4–5-service journeys that forces
  **3 shared / 4–5 union = 0.60–0.75 automatically**, so **every single-page pair clears the 0.6 gate**
  (23 of 45 pairs are ≥ 0.6; `browse_product` is ≥ 0.6 with 7 of its 9 peers). If you removed the
  op-stem gate, Jaccard alone collapses the whole shop into ~1 scenario. **→ The Jaccard gate is
  effectively a no-op for the common case; the taxonomy is produced entirely by the hand-coded stem
  table.** That table is tuned to this one demo (it literally special-cases `ads`, `product_reviews`,
  `ask_product` → "browse"); on any other app the rules miss and everything falls back to first-token
  buckets — unpredictable collapse or explosion.
- **Identical set, different load → silent over-merge (phantom).** `get_product_reviews` ×
  `ask_product_ai_assistant` have **J = 1.000** (identical service set) and the stem table maps both to
  "browse", so they merge — yet the AI-assistant path is a materially different, heavier operation
  (route p50 30 ms + an LLM call vs 12 ms review read). The merged scenario drives a load shape neither
  real flow has. Set + stem cannot see the difference; their **call sequences** can.
- **Conditional branches average into a union no real trace exhibits.** Because `_absorb()` unions
  service sets, a flow that branches (e.g. checkout that *sometimes* calls a fraud service) yields a
  cluster `svc_set` that is the union of both branches — the synthesized journey fans out to services
  that no single production trace touched together.
- **No notion of a session.** Each root trace is an independent journey. Real users chain traces
  (browse → browse → add → view cart → checkout) correlated by session id — the dominant *session*
  shape is invisible. The schema carries `correlationKeys.sessionId`, but clustering never stitches it.
  This is precisely the gap WESSBAS (§1.1) fills with Markov session models.
- **Order and multiplicity are discarded.** "add 3 items then checkout" vs "checkout then add" hit the
  same set → J = 1.0 → merged, despite different cache-key sequences and fan-out timing.
- **Async fan-out is dropped.** The noise classifier removes Kafka consumers / background work; the
  set-based synchronous tree never models producer→consumer causal edges.
- **Rare critical, low-reach flows fall off the ≤6 cap.** The reach ≥ 10 rescue only saves fan-out-heavy
  flows (checkout). A narrow but critical flow (login touching only `auth`: low reach, low weight) is
  silently dropped by `enforce_cap` even though it gates everything.
- **Threshold-cliff instability across windows.** A single hard 0.6 cut means near-boundary journeys
  flip cluster membership on tiny window-to-window traffic changes; determinism *within* a window is
  fine, but the scenario set is not *stable across re-extractions*.

**Honest scope note:** the oat05854 fixture is a *synthetic load-generator* workload (every root span is
pre-labeled `user_*` and single-shot) — the **easy** case, and the heuristic reproduces its golden
correctly. The weaknesses above bite on **real production traffic** (unlabeled root spans = raw routes;
multi-trace sessions; app-specific op names not in the table). A second, harder fixture is required to
regression-test any successor; recommend adding a **session-correlated** extract (group oat05854 root
traces by `session.id` over the same window — exposes the session gap using data we already hold) and,
as a public stress set, a **DeathStarBench social-network** or **Alibaba cluster-trace** sample (deep
branching + async fan-out). This is a follow-up fixture task, not done in this spike.

### 8.2 Candidate approaches and fit

| Approach | Input needed | Output shape | Beats heuristic on §8.1? | Deterministic + offline + golden-testable? |
|---|---|---|---|---|
| **(a) Sequence mining — PrefixSpan / SPADE** | per-session **ordered** call/route chains (needs session stitch) | frequent request subsequences + support → journey templates | **Yes** — order, multiplicity, phantom-branch, reviews-vs-AI, session chains | **Yes, fully.** Algorithmic frequent-pattern mining; given fixed input order + support threshold, output is a pure function. "ML-adjacent," not stochastic. **In-engine OK.** |
| **(b) Markov / behavior model — WESSBAS-style** | session-stitched state transitions | transition matrix + think-time → session behavior model | **Yes** for session modeling (the #1 gap); partial on branch discovery | **Fit = deterministic** (transition counting is closed-form MLE, no training loop). **Sampling is stochastic.** OK in-engine *only as a frozen descriptor* (read dominant paths), never sampled at inference. |
| **(c) Sequence-embedding clustering — trace2vec + k-means** | embedded trace sequences | dense vectors → k clusters | Sometimes — captures fuzzy similarity set+stem miss | **No (as-trained).** Random init + SGD + drift. Pure-function *only* if shipped as a **frozen, pre-trained** embedder + seeded k-means + fixed centroids — a heavy runtime (torch) dependency that fights "offline/no heavy deps." **Outside the engine.** |
| **(d) Process mining — inductive miner / HMM** | event log (session-grouped events) | process tree / Petri net (explicit choice, loop, concurrency) | **Yes** — models branching & concurrency explicitly, the union-phantom killer | **Inductive miner = deterministic** (algorithmic, no training) → in-engine candidate. **HMM (Baum-Welch/EM) = stochastic** → outside / frozen only. |

**Reading of the table:** the two determinism-safe, in-engine-eligible members are **(a) PrefixSpan**
and **(d) the inductive miner** — both are *algorithms*, not trained models. The two that must stay
outside are the *trainable* ones — **(c) embeddings** and **(d-HMM)**. **(b) Markov** sits on the
fence: deterministic to fit, stochastic to sample, so usable in-engine only as a read-only descriptor.
Crucially, **all four operate on sequences/event-logs, not service sets** — confirming §8.1's core
finding that the fix is the *feature*, not the model class.

### 8.3 The determinism tension — per-candidate verdict

The engine's contract (§3.2, §6): `build_model(interchange, *, now, seed) → model`, pure, no network,
no wall-clock, no unseeded RNG, byte-identical twice, order-invariant, golden-tested. Against that bar:

- **(a) PrefixSpan — PASSES, in-engine.** Deterministic given a total input order (we already mandate
  stable tie-breakers, §6.3) and a fixed `minSupport`. No RNG, no network, no model file. Golden test =
  same sessions → same frequent patterns → same scenarios. **This is the recommended successor signal.**
- **(d-inductive-miner) — PASSES, in-engine (stretch).** Deterministic algorithm; output process tree
  is a pure function of the event log. Heavier to implement and to golden-diff than PrefixSpan; park as
  a later add if branch/concurrency discovery proves necessary.
- **(b) Markov/WESSBAS — CONDITIONAL.** May live in-engine **only** as a *frozen, read-only* transition
  descriptor computed deterministically from the interchange (dominant-path extraction), never sampled
  at inference. If we ever want to *generate* sessions by sampling the chain, that sampling must be
  seeded and is better done in the renderer, not the engine.
- **(c) embeddings + (d-HMM) — FAIL in-engine.** Trainable, stochastic, drift-prone, heavy runtime.
  These **must live outside the engine boundary** as an *offline, human-reviewed scenario-proposal
  assist*: they run once offline, a human approves/edits the proposed journey groupings at the mandatory
  **VALIDATE gate**, and the approved grouping is frozen into a versioned fixture (shape: the existing
  `confirmed_groups` / stem-override map that `cluster()` already accepts) that is fed **into** the pure
  engine. **ML proposes; human disposes; the engine stays deterministic.** No trained model, no torch,
  no drift ever crosses the engine boundary.

### 8.4 Recommendation (slotted behind the existing scenario-reconstruction interface)

`cluster()` already has the right seam: it accepts `stem_fn` and `confirmed_groups`, i.e. the
scenario-reconstruction *strategy* is already injectable. Formalize that into a
`ScenarioReconstructor` strategy interface and ship **two implementations**:

1. **`HeuristicReconstructor` (v1, keep).** Today's set+stem+Jaccard. Remains the default and the
   zero-dependency fallback. **One immediate de-risk, cheap:** lift the hand-coded `op_stem()` rules
   into a **data-driven / config-supplied** stem map (the real fragility is the baked-in demo table,
   not the Jaccard math) so a new app supplies its grouping without editing engine code.
2. **`SequenceReconstructor` (v2, recommended build — ISI-5631 scope).** Session-stitch root traces by
   `correlationKeys.sessionId` (fallback: time-gap sessionization per client), then **PrefixSpan** over
   the ordered route chains to discover frequent journey templates. Deterministic, seedable, offline,
   golden-testable. Directly fixes the two biggest §8.1 weaknesses (order-blindness, no-session) and
   **removes the dependence on the hand-coded stem table** because grouping is learned from the actual
   call sequences. Keep the §6 determinism tests (byte-identical twice, order-invariance) as the gate.

**Outside the engine (optional, later):** an offline `ScenarioProposalAssist` (embeddings/HMM/Markov)
that emits *candidate* groupings for a human to approve at VALIDATE; its blessed output is frozen into
the config map consumed by `HeuristicReconstructor`/`SequenceReconstructor`. This is where genuinely
*trained* ML is allowed to help, without ever compromising engine purity.

**"Not now" for stochastic in-engine ML — explicit trigger to revisit:** only if, after shipping the
deterministic sequence miner, we onboard apps where even ordered-sequence mining under-discriminates
(e.g. very high-cardinality micro-operations or heavy semantic aliasing) **and** we can ship a
**frozen, seeded, CPU-only** model as a versioned fixture with a passing golden test. Until both hold,
no trainable model goes inside the engine.

**Determinism verdict, one line per candidate:** PrefixSpan ✅ in-engine · inductive miner ✅ in-engine
(stretch) · Markov ⚠️ in-engine only as frozen read-only descriptor · trace2vec embeddings ❌
engine, ✅ offline-assist · HMM ❌ engine, ✅ offline-assist.

---

## 9. k6-MCP capability note (ISI-5635 Q2)

Henrik suspected `grafana/mcp-k6` is launch-only. **Confirmed from the tool's actual surface** (repo
README, `github.com/grafana/mcp-k6`, fetched 2026-10-09): it is *not* strictly launch-only — it exposes
a validate tool, a run tool, docs browsing, **and** a script-generation *prompt* — but the generation
surface is an **LLM-authoring prompt, not a deterministic tool**, which is exactly why it cannot be our
generator. Classification:

| MCP surface | Kind | generate / validate / launch / docs | Usable by our engine? |
|---|---|---|---|
| `validate_script` | tool | **validate** — runs the script at 1 VU / 1 iteration, reports errors | Optional dev-loop smoke only (equivalent to `k6 --dry-run` on the binary) |
| `run_script` | tool | **launch** — executes a test with VUs/duration/stages, extracts metrics | Optional local dev inner-loop; **not** the scoped/delegated in-cluster run path |
| `list_sections` | tool | **docs** — hierarchical, depth-limited k6 docs navigation | Author-time convenience only |
| `get_documentation` | tool | **docs** — fetch full markdown for a doc slug | Author-time convenience only |
| `generate_script` | **prompt resource** (not a tool) | **generate** — AI-powered NL→k6 workflow (research → best-practices → validate → test) | **No.** It is an LLM-authoring *prompt*, inherently non-deterministic and non-golden-testable. |

**Conclusion (feeds the already-made plan decision):** Henrik's instinct is right in the way that
matters. `generate_script` exists, but it is a **stochastic LLM prompt**, so it **cannot** satisfy the
engine's determinism + golden non-negotiable — **we own generation regardless**, via our deterministic
renderer (`skills/k6-synthesis`). `grafana/mcp-k6` is therefore at most an **optional dev-loop
convenience**: `validate_script` / `run_script` for an ad-hoc smoke, docs browsing for authoring. It is
**not a dependency** of generation or of the scoped execution path (the k6 **binary** in the benchmark
harness is the engine). This confirms — with the tool surface as evidence — the `docs/skills-mcp-decisions.md`
rows (b) k6-synthesis and (c) loadtest-run, and resolves the open "launch-only vs more?" question left
there and in ISI-5622. **This is a note, not a build.**

---

*§8–§9 appended by Research Engineer for ISI-5635 (ISI-5622 research spike), 2026-10-09. Hand back to
BigBoss to fold §8.4 into `docs/methodology.md` §2.1/§3.1 (scenario-reconstruction strategy interface +
the data-driven stem-map de-risk) and to re-issue the Gate-V1 confirmation on ISI-5622. §8.4's
`SequenceReconstructor` is proposed ISI-5631 scope; the harder second fixture (§8.1) is a follow-up.*
