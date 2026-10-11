# gatling-synthesis — test summary (ISI-5658)

Framework: `node --test` (Node built-in, zero external deps). Conforms to the shared
renderer acceptance harness from `renderer-kit` (ISI-5655).

## Acceptance criteria → tests

| ISI-5658 acceptance criterion | Evidence |
|---|---|
| implements the `Renderer` interface (`supports()`+`render()`) | `test/renderer.test.mjs` — shared `assertRendererConformance` |
| renders the `shop-checkout` fixture | `renderer.test.mjs` "conforms … shop-checkout fixture" |
| renders one real model (`loadtests/otel-astronomy-frontend/workload-model.json`) | `renderer.test.mjs` "conforms + renders the REAL otel-astronomy-frontend model" |
| request chaining (step N consumes an id from N-1) | `renderer.test.mjs` "request chaining…", "header-cookie correlation…"; `chain.test.mjs` |
| `synthetic=true` present on all generated traffic | `renderer.test.mjs` "emits synthetic=true baggage…"; `lint.test.mjs` |
| injection profiles from `arrivalProfile.stages`+`shape` (G3) | `injection.test.mjs` (open/closed, G-D1 ramp-from-prev, ramp-down) |
| journey mix via `.randomSwitch` weights | `renderer.test.mjs` "journey mix uses .randomSwitch…" |
| cache-avoidance feeder from the Zipf pool (G4) | feeder files emitted + lint `feeders` check |
| `supports()` declares `empirical` think-time approximation | `renderer.test.mjs` "empirical think-time is declared…" |
| own static check (V2a-equivalent) | `lint.test.mjs` (synthetic / chain / feeders / caps failures) |

## Suite totals

| Suite | Tests | Result |
|---|---|---|
| gatling-synthesis (`node --test`) | 29 | PASS |
| renderer-kit (regression) | 25 | PASS |
| k6-synthesis (regression) | 49 | PASS |

## What the lint (V2a-equivalent) enforces

1. brackets/braces balance (strings + comments stripped)
2. `synthetic=true` baggage header set on the protocol
3. every referenced feeder file is present in the artifact set
4. correlation chain is closed — no dangling `saveAs` or `#{c_…}` reference
5. a ramping injection profile cools down to 0 (G3)
6. peak injection rate within `caps.maxRps`
7. `randomSwitch` journey-mix weights sum to ≤ 100

Full `scalac` / `gatling.sh` compilation is the EXECUTE-time gate (JVM + Gatling bundle),
not run by this pure renderer.

Run all:

```bash
(cd skills/gatling-synthesis && node --test)
(cd skills/renderer-kit && node --test)
(cd skills/k6-synthesis && node --test)
```
