# loadtest-run — test summary

*ISI-5632 · EXECUTE stage (`loadtest-run`) · Testing Architect · 2026-10-09*

**Framework:** Python `unittest` (stdlib — no test framework pre-existed in this
docs/methodology repo; Python 3.12 is the only runtime present, so it is the detected
default). k6 and a live Dynatrace tenant are absent (S0 provisioning backlog), so the
k6 engine (`K6Runner`) and the synthetic-span probe (`dtctl_synthetic_probe`) are
injected adapters and the suite runs fully offline and deterministically.

**Run:** `python3 -m unittest discover -s tests -p 'test_*.py'`
**Result:** **47 tests, 47 passing, 0 failures.**

## Coverage by acceptance criterion

| AC | Requirement | Proving test(s) |
|---|---|---|
| **1** | Refuses the full run until the smoke test passes all 6 §3.4.1 criteria | `test_executor::test_ac1_full_run_refused_until_smoke_passes`, `test_ac1_happy_path_runs_full`, `test_preflight_failure_blocks_full_run`; full criterion matrix in `test_gates::SmokeGateTest` (6 pass + each failure mode) |
| **2** | Enforces caps/abort — exceeding run aborted and torn down cleanly | `test_executor::test_ac2_abort_and_teardown_on_cap_breach`, `test_ac2_abort_on_threshold_breach`; `test_supervisor::SupervisorTest` (caps rps/vus/duration, abort errorRate/p95/p99, teardown-exactly-once, latch) |
| **3** | Smoke confirms synthetic spans arrive before the full run | `test_executor::test_ac3_no_synthetic_span_blocks_full_run`; `test_gates::test_crit5_no_synthetic_span_fails` |
| **4** | Produces a `runs/<ts>/` report with achieved-vs-target arrival | `test_executor::test_ac4_run_dir_has_achieved_vs_target`; `test_report::ReportTest` (target=peak stage, achieved/target ratio, artifact emission, abort-cause capture) |

## Test inventory (47)

- `test_gates.py` (24) — V2b-smoke 6 criteria incl. every failure mode, TVD math,
  V2b pre-flight (prod refusal, allowlist, V2a-commit binding, approval hash/revision,
  p99-abort-below-baseline refusal, smoke-gate dependency, run-dir presence).
- `test_supervisor.py` (14) — duration parsing (`30m`/`1h30m`/bare/numeric/invalid),
  hard caps, abort thresholds, single safe teardown, abort latching.
- `test_report.py` (4) — peak-stage target derivation, achieved-vs-target ratio,
  artifact set emission, abort-cause recording.
- `test_executor.py` (7) — end-to-end orchestration mapped to AC1–AC4 + preflight block.

## Residual / handoff notes

- **k6 engine + dtctl probe adapters are stubbed** (`NotImplementedError` with wiring
  guidance) pending S0 (k6 provisioning) and a live tenant. All gate/supervisor/report
  logic — the bespoke, safety-critical part — is complete and verified. Wiring the
  adapters is a mechanical follow-up once k6 lands; it does not change the gate logic.
- §11 residual **R5** (observability as circular ground truth): criterion 5 proves the
  synthetic tag is *visible*, but a live run should still cross-check at least one infra
  metric (owned by `baseline-diff`, ISI-5633).
