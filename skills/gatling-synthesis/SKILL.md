---
name: gatling-synthesis
description: Gatling renderer for the AI load-testing loop (ISI-5658). Turns an approved §4 workload-model.json into a Gatling Scala Simulation + JSON feeders, conforming to the renderer-kit Renderer interface (ISI-5655). Maps arrivalProfile→injection profile (G3), journey mix→randomSwitch, correlation→.check(saveAs)/session attrs (G2), payload pools→Zipf feeders (G4), and emits synthetic=true baggage on every request. Use when rendering a workload model to Gatling or picking the gatling target tool. Triggers "render workload model to gatling", "gatling simulation", "gatling renderer".
---

# gatling-synthesis (SYNTHESIZE → Gatling renderer, ISI-5658)

The Gatling output renderer. One of the four tool renderers planned under ISI-5622;
gated on and built against the `renderer-kit` foundation (ISI-5655). Grounded in
`docs/workload-model-engine-research.md` §4.1 (capability table) and §4.3 (interface).

## What it produces

`render(model)` → `{ files, warnings }`:

| Path | Content |
|---|---|
| `gatling/<Name>Simulation.scala` | one `Simulation` class: protocol + one `ChainBuilder` per journey + a `randomSwitch` journey-mix scenario + `setUp().inject(...)` |
| `gatling/feeders/<pool>.json` | a flat JSON feeder array per referenced payload pool (G4) |

## §4 → Gatling mapping

| §4 construct | Gatling | Notes |
|---|---|---|
| `arrivalProfile` open (G3) | `constantUsersPerSec` / `rampUsersPerSec` | `shape` authoritative; first ramp starts 0; ramp_down → 0 (G-D1) |
| `arrivalProfile` closed | `constantConcurrentUsers` / `rampConcurrentUsers` | max concurrent from Little's Law (`expectedConcurrency`) |
| journey `weight` | `.randomSwitch(pct -> chain, …)` | weights × 100, sum ≤ 100 |
| `correlates` (G2) | source step `.check(jsonPath/header/headerRegex/regex .saveAs)` → `#{attr}` at consumer | saveAs attaches to the PRODUCER (unlike k6) |
| `payloads` (G4) | `jsonFile("feeders/<id>.json").random` + `feed(...)` | cache-key pool materialized as a Zipf multiset so `.random` reproduces the hit ratio |
| think-time | `.pause(d)` / `.pause(min,max)` | uniform native; exponential/empirical → mean pause (declared) |
| `synthetic=true` | `httpProtocol.header("baggage","synthetic=true")` | board requirement; + W3C trace-context propagation |

## supports() — declared approximations

- `thinkTime.distribution=empirical` — no native sampled pause (mean approximation). **[issue-mandated declaration]**
- `thinkTime.distribution=exponential` — Gatling per-step exponential is not native (`exponentialPauses` is global).
- `correlates.extract.from=body_html` — no native HTML-DOM extractor → regex.
- non-http `callType` (grpc/db/mq/cache) — topology/baseline only, not directly driven (G-X1).

## Own static check (V2a-equivalent)

`lintSimulation(render, model)` fails closed on: bracket imbalance, missing
`synthetic=true` header, missing feeder files, a broken correlation chain (dangling
`saveAs`/ref), a ramping profile that never reaches 0, `caps.maxRps` exceeded, or
randomSwitch weights > 100. Full `scalac`/`gatling.sh` compilation is the EXECUTE-time
gate (needs a JVM + the Gatling bundle); this lint is the renderer's static smoke.

## Reuse

Imports the renderer interface + §4 v1.1 accessors from `renderer-kit`, and the
validated Zipf cache-pool math (`generatePool`) from `k6-synthesis/lib/payloads.mjs`
so Gatling feeders reproduce the SAME production skew/hit-ratio as the k6 renderer.

## Tests

`npm test` (= `node --test`). 29 tests: shared acceptance harness on the shop-checkout
fixture AND the real `loadtests/otel-astronomy-frontend` model, synthetic header,
chaining, injection mapping, randomSwitch, think-time, capability report, and the lint.
