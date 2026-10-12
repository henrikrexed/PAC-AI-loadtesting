# k6-synthesis

SYNTHESIZE stage of the AI-driven load-testing loop (skill-map row 3, SYNTHESIZE).

Approved `workload-model.json` → runnable `k6/` scripts + `payloads/` pools,
gated by the V2a static checker. See [`SKILL.md`](./SKILL.md) for the full
contract; this file is the developer quick-start.

## Layout

```
skills/k6-synthesis/
  SKILL.md              skill contract (invocation, gates, build-vs-buy)
  bin/synthesize.mjs    CLI: model.json + outDir -> k6/ + payloads/ + V2a report
  lib/
    model.mjs           load + V1-approval gate + pool-kind map
    arrival.mjs         arrivalProfile -> k6 executors (G3), ramp-down enforcement
    correlate.mjs       codegen-time extract/inject rendering (G2)
    payloads.mjs        Zipf cache-avoidance pools + sizing + α-fit (G4)
    codegen.mjs         model -> k6 script assembly
    v2a.mjs             V2a static checker (fail-closed)
    synthesize.mjs      orchestrator
  runtime/              pure-JS helpers copied into generated k6/lib/
    baggage.js          syntheticParams() — baggage synthetic=true + tag
    chain.js            extract() + fail-fast (BrokenChainError)
    session.js          per-iteration cookie isolation (k6-only)
    pool.js             pickKey()/pickRecord() runtime samplers
    think.js            think-time sampling
  test/                 node:test suite (44 tests, no external deps)
    fixtures/shop-checkout.workload-model.json
```

## Run

```bash
cd skills/k6-synthesis
node --test                                   # run the test suite
node bin/synthesize.mjs \
  test/fixtures/shop-checkout.workload-model.json /tmp/out   # generate + V2a
```

`node bin/synthesize.mjs` exits non-zero if V2a fails, so it gates the loop.

## Notes / honest limitations

- **When k6 is not installed**, V2a's
  parse check falls back to `node --check` (syntactic) and auto-upgrades to
  `k6 inspect` when k6 is on PATH. Generated scripts target the real k6 runtime.
- **Backend span verification is out of scope here.** This skill guarantees every
  request carries `synthetic=true` baggage and that trace-context propagation is
  enabled; that spans actually appear in Dynatrace with `synthetic=true` is the
  EXECUTE/G5 smoke-test's job (loadtest-run, V2b-smoke crit 5).
- **Cache-hit-ratio** is reproduced via a fitted Zipf working-set model
  (independent-reference approximation); the Monte-Carlo test confirms real draws
  match the analytic target within the §3.5 tolerance (0.10 absolute).
