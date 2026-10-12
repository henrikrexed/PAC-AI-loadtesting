---
name: loadtest-run
description: >-
  EXECUTE stage of the AI-driven load-testing loop (methodology §3.4). Runs a
  synthesized k6 test in a scoped, guard-railed way — mandatory small confirmation
  (smoke) test first, then the full delegated run — emitting runs/<ts>/ artifacts for
  ANALYZE. Use when the user says "run the load test", "execute loadtest-run", or asks
  to run a k6 test produced by k6-synthesis against an allowlisted environment.
---

# loadtest-run — scoped executor + caps/abort supervisor + G5 smoke gate

Implements the EXECUTE stage of the loop against **§3.4** (incl. §3.4.1 small
confirmation test), **§5.3 `run-config.json`**, and **§7 safety rules**. It is the
machine enforcer of gates **V2b-smoke** and **V2b** (§6).

## Contract

- **Input:** `run-config.json` (§5.3) + the approved `workload-model.json` (§4) + the
  `k6/` + `payloads/` produced by `k6-synthesis`.
- **Output:** `runs/<UTC-timestamp>/` — `run-config.json`, `smoke-result.json`,
  `run-report.json`, `run-report.md` (and `abort.log` on an aborted run). This feeds
  `baseline-diff` (ANALYZE).

## Strictly ordered, fail-closed procedure

The orchestration lives in `scripts/loadtest_run.py::execute`. It never reorders or
skips a step; any gate failure stops the loop and writes a report:

1. **Create** `runs/<UTC-ts>/` and pin the exact `run-config.json` used.
2. **SMOKE (§3.4.1, G5)** — run the small confirmation test: 3–5 min, 10–20% of target
   scale, all journeys in approved weight ratios.
3. **V2b-smoke gate** — evaluate the **six** pass criteria (`scripts/gates.py::evaluate_smoke`):
   1. Zero 5xx (or per-journey error rate ≤ model `baseline.errorRate`).
   2. Every step reaches a downstream span — no broken routes / 404s.
   3. Chain correlation succeeds — zero null-extract failures.
   4. Journey mix matches approved weights within TVD ≤ 0.30.
   5. **≥ 1 `synthetic == true` span visible in the backend** — proves baggage→attribute
      promotion (P4 / §7.7) is live *before* the full run.
   6. `dropped_iterations == 0` at target-scale rate.
   **If any criterion fails → STOP. The full run is refused.** Diagnose, revise the
   model (structural → VALIDATE; parameter-only → iterate per §3.5), re-run the smoke.
   Max 2 retries, then escalate to the human.
4. **V2b pre-flight gate (§3.4.2)** — `scripts/gates.py::preflight_v2b`: target ∈
   allowlist and ≠ production (P5); V2a passed on the exact commit; model approval
   valid (`decision==approved`, revision + hash match `run-config.modelRef.hash`); caps
   + abort thresholds armed with the p99 abort threshold ≥ `baseline.p99Ms`; smoke
   passed; run dir exists. Any failure → STOP.
5. **FULL run** under the caps/abort **Supervisor** (`scripts/supervisor.py`, §7):
   hard caps (max RPS / VUs / duration) and abort thresholds (error-rate / p95 / p99).
   First breach → latch abort, run **safe teardown exactly once**, record the cause.
6. **run-report** — `scripts/report.py` emits the `runs/<ts>/` artifact set with the
   achieved-vs-target arrival table and the verdict
   (`passed` | `smoke_failed` | `preflight_failed` | `aborted`).

## Running it

```bash
python3 scripts/loadtest_run.py \
  --run-config loadtests/<target>/runs/<ts>/run-config.json \
  --model      loadtests/<target>/workload-model.json \
  --runs-root  loadtests/<target>/runs \
  --run-id     "$(date -u +%Y%m%dT%H%M%SZ)" \
  --v2a-passed
```

The k6 engine and the Dynatrace synthetic-span probe are **injected adapters**
(`K6Runner`, `dtctl_synthetic_probe`) so the orchestration and all gates are
deterministic and unit-tested without a cluster. The commodity k6 engine is the deliberate choice; `K6Runner` is the seam to wire
**once k6 is installed on the execution host**.

## Safety invariants (§7)

- Non-production allowlist checked at V2b; production is refused (board exception only).
- Hard caps + automatic abort on every run; teardown is idempotent and logged.
- `synthetic=true` presence is a *gate*, not an assumption — criterion 5 fails closed.
- Everything committed (P2): config, smoke result, report, abort log.

## Tests

`python3 -m unittest discover -s tests -p 'test_*.py'` — 47 tests, all passing. The
`test_executor.py` cases map 1:1 to the issue acceptance criteria (AC1 refuse-until-smoke,
AC2 caps/abort + teardown, AC3 synthetic-span gating, AC4 achieved-vs-target report).

## Status

k6/dtctl adapters are stubbed pending S0 (k6 provisioning) and a live tenant; all
gate, supervisor, and report logic is complete and verified. See
`fixtures/example-runs/` for a rendered sample `run-report.md`.
