# jmeter-synthesis — test summary (ISI-5656)

Framework: `node:test` (zero deps). Run: `cd skills/jmeter-synthesis && node --test`.

**Result: 24/24 pass.** No regressions in `skills/k6-synthesis` (49/49) or
`skills/renderer-kit` (25/25), both imported by this renderer.

## Coverage vs the ISI-5656 acceptance criteria

| Acceptance criterion | Test(s) |
|---|---|
| Renders the `shop-checkout` fixture | `renderer.test.mjs` harness + `acceptance.test.mjs` AC |
| Renders one **real** model (`loadtests/otel-astronomy-frontend`) | `renderer.test.mjs` real-model harness + `acceptance.test.mjs` |
| Produced script validates with the tool's own checker | `acceptance.test.mjs` (both models pass J1–J7) + `check.test.mjs` |
| Request chaining — step N consumes an id from N-1 | `acceptance.test.mjs` (JSON + header extractor → `${var}`) |
| `synthetic=true` present | `acceptance.test.mjs` baggage Header Manager + J4 |
| `supports()` lists the approximations (empirical, body_html) | `renderer.test.mjs` supports() |
| Implements the ISI-5655 Renderer interface + registry + harness | `renderer.test.mjs` `assertRendererConformance` + registry |

## Test files

- `renderer.test.mjs` (7) — shared acceptance-harness conformance (shop-checkout +
  real model), approximation declarations, G-X1 non-http, V1 approval gate,
  render()==disk byte-identity, 3-tool registry (k6 + jmeter + locust).
- `acceptance.test.mjs` (8) — end-to-end on both models: own static check passes,
  well-formed + balanced hashTrees, JSON + header chaining, synthetic baggage,
  Zipf→CSV Data Set, open→Concurrency TG + Throughput Shaping Timer, V1 gate.
- `check.test.mjs` (5) — well-formedness scanner accept/reject, full gate green,
  fail-closed on stripped baggage / missing CSV / caps breach.
- `csv.test.mjs` (4) — cache-key Zipf sample, record pool columns (PII-free),
  determinism, variable-name namespacing.

## Notes / approximations surfaced

- `body_html` → Boundary Extractor and `empirical` → JSR223 timer are declared in
  `supports()` (agent warns the human at VALIDATE); neither fixture exercises them,
  so both models render with `supports().ok === true`.
- Open-model plans require jp@gc Concurrency Thread Group + Throughput Shaping
  Timer at EXECUTE (runtime dependency, documented in the manifest).
- `jmeter` binary absent in CI → the own static check is a structural XML/JMX
  validator (J1–J7), not a `jmeter -n` load; documented in SKILL.md.
