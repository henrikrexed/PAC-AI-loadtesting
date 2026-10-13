# Load-test run report: 20261009T120000Z

**Verdict:** `passed`

## Scope contract
- Model: `{'name': 'checkout', 'revision': 3, 'hash': 'sha256:deadbeef'}`
- Target: `{'baseUrl': 'https://staging.internal', 'environment': 'staging', 'allowlist': True}`
- Caps: `{'maxRps': 400, 'maxVus': 200, 'maxDuration': '30m'}`
- Abort thresholds: `{'errorRateGt': 0.05, 'p95MsGt': 2500, 'p99MsGt': 4000}`

## Achieved vs target arrival

| Metric | Value |
|---|---|
| Target RPS (model peak) | 200.00 |
| Achieved RPS | 190.00 |
| Achieved / target | 95.00% |

## V2b-smoke gate — PASS

| Criterion | Result | Detail |
|---|---|---|
| `1-no-5xx` | ✅ | 0 5xx responses |
| `2-routes-reachable` | ✅ | 0 steps without downstream span, 0 404s |
| `3-correlation` | ✅ | 0 null-extract failures |
| `4-journey-mix` | ✅ | TVD=0.000 (max 0.30) |
| `5-synthetic-visible` | ✅ | 42 synthetic==true spans in backend (baggage promotion confirmed) |
| `6-no-dropped` | ✅ | 0 dropped iterations |

## V2b gate — PASS

| Criterion | Result | Detail |
|---|---|---|
| `allowlist-nonprod` | ✅ | env=staging allowlist=True nonprod=True |
| `v2a-passed-on-commit` | ✅ | v2a.passed=True v2a.commit=abc123 current=abc123 |
| `approval-valid` | ✅ | decision=approved approvalRev=3 modelRev=3 hashMatch=True |
| `caps-abort-armed` | ✅ | caps={'maxRps': 400, 'maxVus': 200, 'maxDuration': '30m'} abort={'errorRateGt': 0.05, 'p95MsGt': 2500, 'p99MsGt': 4000} baselineP99=1500.0 p99ThresholdOk=True |
| `smoke-passed` | ✅ | smoke gate passed=True |
| `run-dir` | ✅ | runs/<ts>/ exists=True |

## Telemetry coordinates (for ANALYZE / baseline-diff)

`{'environment': 'staging-dt-tenant', 'timeframe': '-15m', 'filter': 'synthetic == true'}`
