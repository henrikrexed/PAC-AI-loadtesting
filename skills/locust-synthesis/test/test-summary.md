# locust-synthesis — test summary (ISI-5657)

Framework: `node --test` (zero-dep, matches renderer-kit / k6-synthesis).
Static check: `python3 -m py_compile` (the Locust runtime's own parser).

**Result: 11/11 pass.** (renderer-kit 25/25 and k6-synthesis 49/49 unaffected — this
skill only imports from them.)

| # | Test | Covers |
|---|---|---|
| 1 | conforms to shared acceptance harness (shop-checkout) | interface shape + determinism (byte-identical double render) + expected files |
| 2 | conforms when rendering the real astronomy model | ISI-5657 acceptance: renders `loadtests/otel-astronomy-frontend`; unapproved → PREVIEW warning |
| 3 | `supports()` declares open-arrival (G-O1) for both fixtures | approximation = LoadTestShape + pacing, declared before render |
| 4 | `supports()` declares empirical think-time, body_html, non-http | G-E1 / body_html / G-X1 honesty |
| 5 | every generated request carries synthetic=true | board requirement; `synthetic_headers()` on every `self.client.*` |
| 6 | request chaining wired + fail-fast guard | G2: `require_value(extract(...))`, injected into next request |
| 7 | real-model header correlation + path-token feeder binding | `set-cookie:session` → cookie header; `[productId]` → `pick_key` feeder |
| 8 | produced locustfile compiles with Python — shop-checkout | V2a parse (py_compile) + all semantic checks + approved |
| 9 | produced locustfile compiles with Python — astronomy | V2a parse for the real model; approval advisory=false |
| 10 | render() files == synthesize() on-disk bytes | render/synthesize share `buildArtifacts()` — no drift |
| 11 | resolves from a registry | tool selection by name |

## Acceptance (ISI-5657) — all met

- ✅ renders `shop-checkout` fixture AND the real `otel-astronomy-frontend` model
- ✅ produced script validates/compiles with the tool's own checker (`py_compile`; Locust has no standalone lint)
- ✅ request chaining works (step N consumes an id from N-1) — body_json, header/set-cookie
- ✅ `synthetic=true` present on every request (OTel baggage header + best-effort client spans)
- ✅ `supports()` lists the approximations: open-model LoadTestShape+pacing (G-O1), empirical think-time (G-E1), body_html, non-http (G-X1)
- ✅ implements the ISI-5655 `Renderer` interface (`supports()` + `render()`); own static check (V2a-equivalent)

## Known approximations (surfaced by supports(), confirm at VALIDATE)

- **G-O1 open arrival**: Locust is closed-native. Modeled as a `StagedShape`
  (users = Little's-Law `expectedConcurrency·rate/peakRate`, clamped to
  `caps.maxVus`) + `constant_pacing(meanServiceSec)`. Aggregate tracks the target
  arrival rate; it is not a hard arrival-rate executor like k6's.
- **G-E1 empirical think-time**: sampled from the pre-generated list in `think.py`.
- **cache-key feeder on a body (POST) step**: bound to a path token only; mirrors
  k6 (the key is unused in the body unless a `body_field` correlation injects it).
- **locust not installed in this env**: `py_compile` is the compile gate; a live
  `locust -f … --headless` dry-run is the EXECUTE-time check (G5), out of scope here.
