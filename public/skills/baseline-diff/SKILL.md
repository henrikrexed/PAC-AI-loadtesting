---
name: baseline-diff
description: ANALYZE stage of the AI load-testing loop — compare a completed synthetic run against the production baseline in Dynatrace DQL, evaluate the six shape-diff dimensions against model tolerances, run the mandatory R5 infra (non-telemetry) cross-check, and classify the next iteration as accept / iterate / escalate. Emits a schema-valid shape-diff.json (§5.4). Use when a loadtest-run has completed and you need the V3 shape-tolerance verdict.
---

# baseline-diff — ANALYZE / shape-diff against production (methodology §3.5)

Implements **§8 skill-map row 5 (ANALYZE → `baseline-diff`)** of the board-approved
the loop methodology, against **§3.5** and the **§5.4 `shape-diff.json`**
contract. It is the ANALYZE half of the Dynatrace-grounded loop: SCOPE
(`workload-model`) and ANALYZE (`baseline-diff`) are the bespoke skills; k6 is a
commodity.

**What it decides:** did the synthetic load faithfully reproduce the production
*shape*, and what happens next — `accept`, `iterate` (parameter-only, ≤3×), or
`escalate` to the human with diff evidence.

## Inputs → outputs (contract)

- **Input:** `runs/<ts>/` (from `loadtest-run`) + a production baseline window.
- **Output:** `runs/<ts>/shape-diff.json` (schema §5.4, validated) + an
  iterate/approve/escalate decision; `escalation-report.md` when escalating.

## The split that keeps this deterministic

All the non-determinism — the DQL extraction against the live tenant — happens in
`dtctl` and is captured verbatim in an intermediate **`diff-input.json`**. The
math (tolerance eval, classifier, R5 gate) is then a pure, reviewable function of
that file (`scripts/diff.py` → `scripts/build_shape_diff.py`). Observability as
code: same `diff-input.json` ⇒ same `shape-diff.json`, every time.

## Procedure

### 1. Telemetry prerequisites — enforce BEFORE trusting any diff (§3.5)

1. **Synthetic tag is queryable.** Run probe `(0)` in `dql/diff.dql`. The
   `synthetic == "true"` count MUST be > 0. Zero means the baggage→attribute
   promotion is missing (see `deploy/otel-demo/pac-lt-collector.yaml`
   `transform/baggage`), **not** that shapes match. Record it as
   `syntheticProbeCount`; the skill caveats a zero and the diff is meaningless.
2. **Sampling parity.** Compare *rates*, not raw counts. Record
   `samplingFactor = { prod, test }` (fraction retained). Rates are
   sampling-corrected before any comparison. Unrecorded sampling is the most
   common false "out of tolerance".
3. **Scale factor is explicit.** Record `scalingFactor = test target RPS ÷
   baseline RPS`. The baseline is divided to the reduced test scale before the
   arrival-shape and fan-out comparisons — never inferred silently.

> **DQL field names** are validated against a live tenant:
> `request.is_root_span`, `span.kind`, `request.is_failed`, `duration` in **ns**
> (÷ 1e6 for ms), `start_time`. Re-confirm on any new tenant before running live.

### 2. Extract the six dimensions (synthetic filter) — `dql/diff.dql`

Within the isolating `deployment.environment == $env`: **TEST** traffic is
`synthetic == "true"`; **BASELINE** is `isNull(synthetic)`. Extract into
`diff-input.json`:

| # | Dimension | Default tolerance |
|---|---|---|
| 1 | Arrival shape (per-min RPS curve, test vs scaled baseline) | WMAPE ≤ 0.20 |
| 2 | Latency p50/p95/p99 per journey (**server span**, not driver wrapper) | \|Δp50\|≤25%, \|Δp95\|≤30%, \|Δp99\|≤35% |
| 3 | Service fan-out (baseline edges present + per-edge rate ratio) | ≥90% present; ratio ∈ [0.5, 2.0] |
| 4 | Error rate (test vs baseline, per journey) | Δ ≤ +1.0 pp |
| 5 | Journey mix (observed vs approved **model weights**) | TVD ≤ 0.15 |
| 6 | **Cache hit ratio** (G4, when `cacheProfile.targetHitRatio` set) | \|Δ\| ≤ 0.10 absolute |

Tolerances are overridable via `run-config.tolerances`; any loosening is flagged
(R8, below).

### 3. R5 infra cross-check — mandatory, not optional (§11 R5) — `dql/r5-infra-crosscheck.dql`

Telemetry is circular ground truth: we extract *and* validate from the same
spans, so shared blind spots (async fan-out, websockets, fire-and-forget) are
invisible on both sides. **Cross-check at least one run dimension against an infra
signal from a different data plane** — Dynatrace **Kubernetes monitoring**
(`dt.kubernetes.container.cpu_usage`, `dt.kubernetes.pod.network_*`; verified live
on the edge server), independent of the app's OTLP spans. (The app collector is
OTLP-only with zero RBAC — it carries no infra metrics; the infra plane must come
from K8s monitoring.)

The check PASSES when a telemetry load claim is corroborated by a material CPU
rise between an idle window and the run window (`duringRun / idleBaseline ≥ 2.0`).
A load claim with a **flat** infra signal FAILS → **escalate**, regardless of how
clean the telemetry dimensions look. If infra metrics are unavailable, record
`available: false`; the skill then **blocks a clean accept** (`requireR5` default
true) so the residual is never silently waved through.

### 4. Build the verdict

```bash
python3 skills/baseline-diff/scripts/build_shape_diff.py \
  --input runs/<ts>/diff-input.json
# writes runs/<ts>/shape-diff.json (+ escalation-report.md on escalate)
# exit 0 accept · 10 iterate · 20 escalate · 2 bad input/schema
```

**Decision rule (§3.5):**
- **R5 available & failing →** `escalate` first (infra contradicts telemetry).
- **All dimensions pass →** `accept` if R5 corroborates; else `escalate` (R5
  unavailable blocks clean accept).
- **Any dimension fails →** `iterate` with a per-miss classification
  (parameter-only tweaks: think-time, pacing, payload pools, per-journey pacing
  within ±10% of weights). Structural misses (fan-out gaps, error spikes,
  mix beyond ±10%) are flagged `structural: true` → back to **VALIDATE** (§3.2.2).
- **Iteration cap:** max **3**; the 4th miss → `escalate` with diff evidence.

### 5. Governance — R8 anti-gaming (§11 R8)

The skill flags any tolerance loosened relative to the §3.5 defaults in
`governance.toleranceDrift` and adds a caveat. Do not weaken a gate to force a
pass; surface it for the human.

## Files

- `scripts/diff.py` — pure tolerance/classifier/cross-check engine (no I/O).
- `scripts/build_shape_diff.py` — CLI: `diff-input.json` → schema-valid `shape-diff.json` + escalation report.
- `scripts/test_baseline_diff.py` — 20 tests mapping to AC1/AC2/AC3 + mechanics.
- `schema/shape-diff.schema.json` — §5.4 contract (+ cache dim, R5 block, governance).
- `dql/diff.dql` — synthetic-filtered six-dimension extraction pack.
- `dql/r5-infra-crosscheck.dql` — infra-plane cross-check (K8s-monitoring CPU/net).
- `fixtures/` — worked examples: `accept`, `iterate`, `r5-contradiction`.

## Residual caveats honored

- **R5** — telemetry is circular ground truth; the infra cross-check is the
  mitigation and is enforced, not optional (clean accept blocked when absent).
- **R8** — tolerance drift vs §3.5 defaults is flagged; do not overfit/game V3.
- **R1** (extraction-side sampling blindness) — surfaced upstream in SCOPE; this
  skill records `samplingFactor` so under-sampled rare/error journeys are at least
  visible in the normalization, but cannot resurrect tail-sampled-away traffic.
