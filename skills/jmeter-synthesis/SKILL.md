---
name: jmeter-synthesis
description: JMeter renderer (ISI-5656) — approved workload-model.json -> Apache JMeter .jmx test plan + CSV data sets, behind the ISI-5655 Renderer interface.
---

# jmeter-synthesis — the JMeter output renderer (ISI-5656)

Renders an **approved** §4 `workload-model.json` into an Apache JMeter test plan
(`.jmx`) plus CSV data sets. It is a drop-in against the formal **Renderer**
interface + registry + acceptance harness from **ISI-5655** (`skills/renderer-kit`),
alongside `k6` (`skills/k6-synthesis`), the Locust stub, and the planned
Locust/Gatling renderers (ISI-5657/5658). Parent: **ISI-5622** (§8 renderer matrix).

## Dependencies — installed by setup

- Node.js >= 20 only — zero npm dependencies; lockfile verified by `skills/setup.sh` (`npm ci`).
- JMeter + Plugins Manager (Throughput Shaping Timer, OpenTelemetry listener) are EXECUTE-time requirements — probed by `skills/preflight.sh --require-tools` with install hints.


## Usage

```
node bin/synthesize.mjs <approved-model.json> <outDir>
```

Programmatic (Renderer interface):

```js
import { jmeterRenderer } from './lib/renderer.mjs';
jmeterRenderer.supports(model);     // CapabilityReport — call BEFORE rendering
jmeterRenderer.render(model);       // { files:[{path,content}], warnings:[] }
```

Output layout (paths relative to `outDir`):

```
jmeter/<name>.jmx                 # the JMeter test plan
jmeter/data/<pool>.csv            # one CSV Data Set per payload pool
jmeter/<name>.manifest.json       # provenance, capability report, pool + load summary
```

## §4 construct → JMeter mapping (research §4.1)

| §4 construct | JMeter element |
|---|---|
| `arrivalProfile.model=open` + stages | **Concurrency Thread Group** + **Throughput Shaping Timer** (jp@gc) |
| `arrivalProfile.model=closed` | native **Thread Group** (scheduler + looping Loop Controller) |
| `littlesLawCheck.expectedConcurrency` × `weight` | thread ceiling (clamped to `caps.maxVus`) |
| `journeys[].weight` | per-journey thread group + Throughput Shaping rate × weight |
| `correlates.extract body_json` | **JSON Extractor** (`JSONPostProcessor`) on the source sampler |
| `correlates.extract header` | **Regex Extractor** (`useHeaders=true`) — e.g. `set-cookie:session` |
| `correlates.extract body_regex` | **Regex Extractor** over the body |
| `correlates.extract body_html` | **Boundary Extractor** *(approximation — see `supports()`)* |
| `inject header / path_param / query_param / body_field` | Header Manager / path token / query string / raw JSON body |
| `thinkTime constant/uniform/gaussian/exponential` | Constant / Uniform / Gaussian / Poisson timer |
| `thinkTime empirical` | **JSR223 timer** sampling the pre-gen list *(approximation)* |
| `payloads[] + cacheProfile` (Zipf) | pre-generated key pool → **CSV Data Set Config** |
| `synthetic=true` (board mandate) | `baggage: synthetic=true` Header Manager on every request |

## Chaining (G2)

Correlation is wired **source → consumer**: the extractor is attached to the
sampler that *produces* the value (saving a deterministic `corr__<src>__<path>`
variable) and the consuming sampler references `${…}` in its URL token / query /
body / header. Identical extractions on one source are deduped to a single
variable; when a correlation and a payload field target the same name the
**correlation wins** (no duplicate JSON keys). A broken chain stores the
`__CHAIN_BROKEN__` sentinel default so it is observable at EXECUTE.

## synthetic=true + OpenTelemetry

`baggage: synthetic=true` is stamped on every request via a test-plan Header
Manager (the core board requirement, same as k6). Full W3C trace-context + span
export at EXECUTE requires the **JMeter OpenTelemetry listener plugin**; that is a
runtime dependency documented in the manifest, not a model-feature gap.

## `supports()` — declared approximations (drives VALIDATE warnings)

- `thinkTime.distribution=empirical` → JSR223 timer approximation
- `correlates.extract.from=body_html` → Boundary Extractor approximation
- non-http `callType` (grpc/db/mq/cache) → topology/baseline, not directly driven (G-X1)

Everything else (open/closed arrival, weight, body_json/header/body_regex
extraction, every injection target, constant/uniform/gaussian/exponential think,
Zipf cache pools) maps natively → `supports().ok === true` for an all-http model.

## Own static check (V2a-equivalent, `lib/check.mjs`)

The `jmeter` binary ships no offline lint mode and is not assumed present, so the
renderer self-validates the rendered plan fail-closed: **J1** well-formed XML +
balanced element tags, **J2** `<hashTree>` balance, **J3** required elements
(TestPlan + thread group + HTTP sampler), **J4** `synthetic=true` present, **J5**
G2 chaining wired, **J6** CSV data sets resolve + are consumed, **J7** declared
load within caps. `synthesize()` runs it after writing to disk.

## Determinism

Pure function of the model: no network, no wall-clock, no `Math.random`. Pool
generation reuses the seeded `skills/k6-synthesis` Zipf/field math (single source
of truth), so k6 and JMeter bake identical pools. `render()` files are
byte-identical to what `synthesize()` writes to disk and across repeated renders
(enforced by the shared acceptance harness).

## Runtime dependency (EXECUTE, not synthesis)

Open-model plans require the jp@gc plugins **Concurrency Thread Group** and
**Throughput Shaping Timer** (install via the JMeter Plugins Manager). Host/port/
protocol default to `localhost:8080/http`, overridable with `-Jhost= -Jport=
-Jprotocol=`.

## Tests

`node --test` — 24 tests: shared-harness conformance on the shop-checkout fixture
**and** the real `otel-astronomy-frontend` model, approximation declarations, the
V1 approval gate, render()==disk, chaining, synthetic baggage, cache CSV, open
executor, and the static-check gate. See `test/test-summary.md`.
