# k6-synthesis — test summary (ISI-5631)

Framework: `node:test` (Node ≥18 built-in; zero external deps). Run: `node --test`.
Result: **44 passing / 0 failing** (2026-10-09).

## Acceptance-criteria coverage (ISI-5631)

| AC | Criterion | Test(s) |
|----|-----------|---------|
| 1 | Multi-step chained scenario; step N consumes id from N-1; broken chain fails fast with clear error | `acceptance.test.mjs` AC1 (×2), `codegen.test.mjs` chained-step, `correlate.test.mjs`, `runtime.test.mjs` failChain/requireValue |
| 2 | Emitted scripts carry `synthetic=true` on every request + OTel propagation | `acceptance.test.mjs` AC2, `codegen.test.mjs` http-routing, `runtime.test.mjs` syntheticParams/mergeBaggage |
| 3 | Payload pool reproduces target `cacheProfile` hit ratio within tolerance (0.10) | `acceptance.test.mjs` AC3, `payloads.test.mjs` (analytic fit + Monte-Carlo validation) |
| 4 | Passes V2a static checks | `acceptance.test.mjs` AC4, `v2a.test.mjs` (5 adversarial negative tests) |

## Additional guarantees tested

- **V1 gate:** synthesis refuses an unapproved / revision-mismatched model.
- **G3 ramp-down:** synthesized when the model omits it; steady single-stage maps
  to a constant executor (no spurious ramp-down); VU ceilings clamp to caps.
- **Determinism (P2):** same seed → identical pools.
- **PII-free payloads:** record pools use `@synthetic.invalid` + bounded enums.
- **Adversarial V2a:** each check (baggage, caps, ramp-down, pools, correlation)
  is proven to FAIL on a real injected violation — not just pass on good input.

## Honest limitations

- k6 not installed on host → V2a parse uses `node --check` (syntactic) and
  auto-upgrades to `k6 inspect` when available.
- Backend `synthetic=true` span visibility is asserted downstream at EXECUTE/G5
  (loadtest-run, ISI-5632), not in this skill.
