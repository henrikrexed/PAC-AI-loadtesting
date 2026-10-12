---
name: k6-synthesis
description: SYNTHESIZE stage of the AI load-testing loop . Turns an approved workload-model.json into runnable k6 scripts + synthetic payload pools — model→k6 codegen with G3 ramping executors, G2 request chaining/correlation with fail-fast, G4 cache-avoidance payload pools (Zipf, cache-hit-ratio targeting), and synthetic=true OTel baggage/span emission — then enforces the V2a static checker. Use when a workload model has passed the V1 human gate and needs test code generated before EXECUTE. Triggers: "synthesize k6", "generate k6 from workload model", "run k6-synthesis", "build the load test scripts".
---

# k6-synthesis (SYNTHESIZE)

Generates versioned, reviewable k6 load-test code from an **approved** workload model.
Turns the approved workload model into runnable, reviewable test code.

## Contract

- **Input:** an approved `workload-model.json` (§4 schema). The model MUST carry
  `status.approval.decision == "approved"` for its current `status.revision`
  (the §3.2 V1 human gate). Synthesis **refuses** otherwise — fail closed.
- **Output:** `<outDir>/k6/<model>.js` + `<outDir>/k6/lib/*.js` helpers +
  `<outDir>/payloads/<pool>.json`. Downstream `loadtest-run` consumes
  these via `run-config.json` (§5.3).
- **Gate:** V2a static checks (§3.3). Exit code 0 iff V2a passes.

## Build-vs-buy (per §8)

**Use `grafana/mcp-k6` for the commodity k6 engine** (`validate_script` /
`run_script`) and **this thin skill** for the bespoke, PII-sensitive glue — model→k6 mapping, correlation,
cache-avoidance payloads, synthetic tagging, and the V2a gate. This skill emits
scripts that `mcp-k6 validate_script` can additionally smoke; `node --check`
is used as the always-available syntactic fallback when k6/MCP is absent.

## Usage

```bash
# from skills/k6-synthesis/
node bin/synthesize.mjs <approved-workload-model.json> <outDir> [--ttl <sec>]
```

Then commit the generated `k6/` + `payloads/` (tests are code, P2). For the real
loop, emit into `loadtests/<target>/` so the layout matches §5.1.

## What it generates

- **Executors (G3, §3.3 rule 2).** One k6 scenario per journey; `arrivalProfile.stages`
  → `ramping-arrival-rate`/`ramping-vus` (or `constant-arrival-rate`/`constant-vus`
  for a single `steady` stage). Rates are scaled by journey weight so the journey
  mix is reproduced. Ramping scenarios always end at `rate/target: 0`; a ramp-down
  is synthesized if the model omits it. VU ceilings come from Little's Law
  (`littlesLawCheck.expectedConcurrency`) and are clamped to `spec.caps`.
- **Request chaining (G2, §3.3 rule 3).** One correlated session per VU-iteration;
  cookie jar reset each iteration (fresh user). Each `correlates` edge → extract
  (`body_json`/`header`/`body_html`/`body_regex`) → inject (`header`/`path_param`/
  `query_param`/`body_field`). **Fail-fast:** a null extract calls k6 `fail()` and
  bumps the `chain_broken` counter (thresholded `count==0`).
- **Cache-avoidance payloads (G4, §3.3 rule 4).** Pools with a `cacheProfile`
  become Zipf-popularity key sets sized + shaped to **reproduce** the production
  cache hit ratio (not eliminate caching). The Zipf α is fitted to hit
  `targetHitRatio` at the endpoint's rate×TTL window; the achieved ratio, α, seed,
  and `backingStoreSeeded` flag are recorded in the pool JSON. Pools without a
  cacheProfile become PII-free synthetic record sets.
- **Synthetic identity + OTel (P4, §7.7).** Every request routes through
  `syntheticParams()` → W3C `baggage: synthetic=true` header + a `synthetic=true`
  metric tag. `instrumentHTTP({propagator:'w3c'})` propagates trace context so
  backend spans join the synthetic trace; the collector/SDK baggage processor
  promotes `synthetic` to a queryable span attribute. Backend span visibility is
  asserted at EXECUTE/G5 (loadtest-run), not here.

## Renderer-interface conformance

k6 is the reference renderer for the formal `Renderer` interface
(the interface definition is vendored at `lib/vendor/renderer.mjs`). `lib/renderer.mjs` exports `k6Renderer`
(`name:"k6"`, `targetTool:"Grafana k6"`, `schemaRange:">=1.0 <2.0"`) with:

- **`supports(model)`** — capability report; k6 natively honors every §4 construct,
  so a well-formed model yields `ok:true` (the only caveat surfaced is G-X1:
  non-http steps are topology/baseline, not directly driven).
- **`render(model, opts)`** — deterministic, network-free, returns
  `{ files:[{path,content}], warnings:[] }`. It shares `buildArtifacts()` with
  `synthesize()`, so `render()`'s files are byte-identical to what `synthesize()`
  writes to disk. `render()` still enforces the V1 approval gate (fail-closed).
  The V2a static gate stays in `synthesize()` (it inspects files on disk / parses
  with `k6 inspect`), not in the pure `render()` surface.

Conformance is pinned by `test/renderer.test.mjs` via the vendored
`assertRendererConformance()` harness (`test/vendor/`).

## V2a checks (§3.3 exit criteria)

1. script parses (`k6 inspect` when present, else `node --check`)
2. every request carries baggage `synthetic=true`
3. referenced payload pools exist and match their specs
4. declared max rate/VU ≤ `spec.caps`
5. every `dependsOn` step extracts a correlation and fails fast on null
6. all ramping scenarios end with a ramp-down to 0
7. scripts + helpers present on disk

## Tests

`npm test` (= `node --test`). 44 tests, zero external deps. Acceptance tests map
1:1 to the acceptance criteria (chained-scenario fail-fast, synthetic=true on every
request, cache-hit-ratio reproduction within tolerance, V2a pass) plus adversarial
negative tests proving each V2a check fails on a real violation.
