---
name: locust-synthesis
description: Locust renderer (ISI-5657) for the AI load-testing loop. Renders an approved §4 workload-model.json to a locustfile.py + lib helpers + pre-generated feeders, conforming to the ISI-5655 Renderer interface. Honestly declares Locust's approximations in supports() — open arrival via LoadTestShape+pacing (G-O1), empirical think-time, body_html extraction — and emits synthetic=true baggage on every request. Use when rendering a workload model to Locust or validating the Locust renderer. Triggers "render to locust", "locustfile", "locust renderer", "workload model to locust".
---

# locust-synthesis (SYNTHESIZE → Locust renderer, ISI-5657)

The production Locust renderer. One pure function over an approved
`workload-model.json` → a runnable Locust project. Conforms to the
`renderer-kit` Renderer interface (ISI-5655) and the shared acceptance harness.
Grounded in `docs/workload-model-engine-research.md` §4.1 (capability table),
§4.2 (gaps G-O1/G-E1/G-X1), §4.3 (interface).

## Output layout (files[] paths relative to an outDir)

```
locust/
  <name>.py              # the locustfile: one HttpUser, @task(weight) per journey
  lib/
    synthetic.py         # synthetic=true baggage + best-effort OTel (P4/§7.7)
    chain.py             # correlation extract + fail-fast require_value (G2)
    think.py             # per-step think-time sampling incl. empirical (G-E1)
    pool.py              # feeder samplers: Zipf cache-key + record (G4)
    shape.py             # StagedShape base — open-arrival approximation (G-O1)
  feeders/<id>.json      # the SAME pre-generated pools the k6 renderer emits (G4)
  requirements.txt
```

## How the §4 model maps to Locust

| §4 construct | Locust rendering | Note |
|---|---|---|
| `journeys[].weight` | `@task(round(weight*100))` methods on one `HttpUser` | journey mix (G3-closed) |
| `arrivalProfile.model=open` | `GeneratedShape(StagedShape)` + `constant_pacing` | **approximation, G-O1** |
| `littlesLawCheck.expectedConcurrency` | per-stage user count = `L·rate/peakRate`, clamped to `caps.maxVus` | Little's Law → user ceiling |
| `steps[].correlates` extract→inject | `require_value(extract(responses[src], spec), step, as)` → path/query/body/header | fail-fast chain (G2) |
| `steps[].thinkTime` | `time.sleep(think_seconds(spec, random()))` | `empirical` = **approximation, G-E1** |
| `payloads[]` + `cacheProfile` | `feeders/<id>.json` sampled by `pick_key`/`pick_record` | cache-avoidance (G4) |
| non-http `callType` | omitted | topology/baseline only (G-X1) |

## `supports()` — declared approximations (drives VALIDATE warnings)

- **G-O1** `arrivalProfile.model=open` → *LoadTestShape + per-task constant_pacing*
  (Locust is user/closed-native: it controls concurrent users, not an arrival rate).
- **G-E1** `thinkTime.distribution=empirical` → sampled list in `think.py`.
- `correlates.extract.from=body_html` → marker/regex extraction in `chain.py`.
- **G-X1** non-http `callType` → omitted (driven indirectly via the HTTP edge).

## synthetic=true (board requirement, parity with k6)

Every generated request passes `headers=synthetic_headers(...)`, which always sets
the W3C `baggage: synthetic=true` header. The OTel collector/SDK baggage span
processor (§7.7) promotes it to the queryable span attribute `synthetic` that
ANALYZE and the G5 smoke filter on. `instrument_otel()` additionally emits OTel
client spans when the SDK is installed and `OTEL_EXPORTER_OTLP_ENDPOINT` is set
(best-effort; the baggage header rides regardless). This is the Locust equivalent
of k6's `syntheticParams()` + `instrumentHTTP()`.

## Own static check — V2a (the tool's own checker)

`lib/v2a.mjs` fail-closed gate. Locust has no standalone lint, so the "tool's own
checker" is the CPython compiler: `python3 -m py_compile` parses the locustfile +
every helper exactly as Locust imports them. On top of that it asserts: every
request carries synthetic=true; feeders exist + are well-formed; every `dependsOn`
step has a fail-fast chain guard; the open-model `LoadTestShape` is present and a
ramping schedule ends at 0 users; peak users ≤ `caps.maxVus`. Approval is advisory
(render emits an unapproved model for PREVIEW; the hard V1 gate is SYNTHESIZE/EXECUTE).

## Usage

```js
import { locustRenderer } from 'locust-synthesis';
const report = locustRenderer.supports(model);     // warn on approximations first
const { files, warnings } = locustRenderer.render(model);  // pure, deterministic
// or, with disk write + V2a static check:
import { synthesize } from 'locust-synthesis';
const { v2a } = await synthesize(model, outDir);
```

## Tests

`npm test` (= `node --test`). Renders the `shop-checkout` fixture AND the real
`loadtests/otel-astronomy-frontend` model; asserts conformance+determinism via the
shared harness, the declared approximations, synthetic=true on every request,
request chaining (step N consumes N-1), and that both locustfiles compile with
Python (V2a). Requires `python3` on PATH for the compile check.
