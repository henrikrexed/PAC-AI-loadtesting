# Escalation report — run 2026-10-09T13-00-00Z

**Decision:** `escalate` (iteration 1)
**Reason:** R5 infra cross-check FAILED — infra signal contradicts the telemetry load claim; escalate with diff + infra evidence

Baseline window: `2026-10-01T00:00Z/2026-10-08T00:00Z` · scalingFactor `0.25` · sampling prod `1.0` / test `1.0`

## Dimension verdicts

| Dimension | Pass | Key metric |
|---|---|---|
| arrivalShape | ✅ | {"metric": "wmape", "value": 0.0064, "tolerance": 0.2, "scalingFactor": 0.25, "alignedBins": 6} |
| latency | ✅ | {"p50Rel": 0.0667, "p95Rel": 0.1111, "p99Rel": 0.1333} |
| serviceFanout | ✅ | {"edgePresence": 1.0, "edgePresenceTolerance": 0.9, "rateRatioRange": [1.0, 1.04], "rateRatioBand": [0.5, 2.0]} |
| errorRate | ✅ | {"deltaPp": 0.2, "tolerancePp": 1.0} |
| journeyMix | ✅ | {"tvd": 0.01, "tolerance": 0.15} |

## R5 infra cross-check (non-telemetry ground truth)

- available: **True** · pass: **False**
- telemetry claims load but infra signal is flat — telemetry may be circular/misleading; do NOT accept
- metric `dt.kubernetes.container.cpu_usage` (infra (non-telemetry)) on workload `frontend`: idle 0.018 → run 0.019 (×1.056)
