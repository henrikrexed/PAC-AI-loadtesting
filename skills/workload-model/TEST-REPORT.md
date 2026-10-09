# workload-model skill — test evidence (ISI-5630)

*Produced 2026-10-09 in response to board request "we need to test the model skills to approve it."
Every result below is reproducible: `cd skills/workload-model && python3 -m pytest tests/ -v`,
and the live runs use `dtctl` against tenant **oat05854** (`dynatrace-dev` context).*

## 1. Unit + gate test suite — 27 passed

```
python3 -m pytest tests/ -v   →   27 passed in 0.18s
```
Covers: clustering (5-scenario merge, checkout-never-merges, Jaccard=0.6 boundary, coverage,
≤6 cap + the raise-when-coverage-unmet path), shaping (pace, sampling correction, Little's Law
server-vs-wrapper, think-time, CoV steady/ramp, ≤6 stage bound, per-second rates), and G0
(real artifact passes + 8 negative blocks).

## 2. Fresh live end-to-end run — proves the skill is live, not a canned artifact

Re-pulled a **new -6h window** (16,178 journeys vs the committed fixture's -3h/7,996) and ran the
engine end-to-end on it:

| scenario | -3h committed weight | -6h fresh-live weight |
|---|---|---|
| Browse product page | 0.521 | 0.519 |
| Cart | 0.286 | 0.287 |
| Recommendations | 0.097 | 0.099 |
| Checkout (reach 12, unmerged) | 0.067 | 0.064 |
| Home | 0.029 | 0.031 |

- Same 5-scenario structure, window-appropriate weights, **coverage 1.000**.
- CoV 0.1018 (< 0.15) → one `steady` stage @ 0.749/s + mandatory `ramp_down` tail.
- Little's Law ratio **1.0035** (server mean 2018 ms, not the 15 s driver wrapper).
- **G0 on the fresh model: 12/12 checks PASS.**

Conclusion: the skill extracts, clusters, shapes, and self-validates on live telemetry
deterministically across windows — the committed artifact is one instance of its output, not a
hand-authored file.

## 3. G0 gate — passes on good, blocks on bad (the gate is real)

```
PASS   real committed artifact (good)
BLOCK  ACCEPTANCE #4: accesslog unknown + no spans-only caveat   -> accesslog-availability
BLOCK  too many journeys (8 > 6 cap)                             -> journey-count
BLOCK  Little's Law from driver wrapper (ratio 7.4)              -> littles-law
BLOCK  dependsOn edge without correlates (G2)                    -> correlates
BLOCK  cacheProfile targetHitRatio>0 missing keyCardinality (G4) -> cache-profile
BLOCK  coverage below 0.80 floor                                 -> coverage
BLOCK  DQL not attested run-live                                 -> dql-live
```

Acceptance criterion 4 is demonstrated directly: the gate refuses emission when access-log
availability is unknown and no spans-only caveat is recorded.

## 4. Acceptance criteria — mapped to evidence

1. **Schema-valid model for a real service** → `loadtests/otel-astronomy-frontend/workload-model.json`, G0 schema check PASS (§1, §3).
2. **Front-end auto-resolved** → `frontend-proxy`/`ingress` + `load-generator` driver, reach-confirmed. Access logs **confirmed absent** on this tenant (`istio-proxy` log probe = 0 lines, no mesh) → ingress-gateway cross-check N/A, handled as the spans-only path per §3.1.
3. **1–6 scenarios, weights sum to coverage %** → 5 scenarios, weights sum 1.0, coverage 100% (§2).
4. **G0 blocks on accesslog-unknown + no caveat** → §3 line 2, and test `test_blocks_when_accesslog_unknown_and_no_caveat`.
