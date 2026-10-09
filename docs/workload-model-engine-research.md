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
