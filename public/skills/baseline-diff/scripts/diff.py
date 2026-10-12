"""Shape-diff engine for the ANALYZE stage (methodology §3.5, §5.4, §6 gate V3).

This module is **pure logic**: callers inject the already-extracted measurements
(from the synthetic-filtered DQL pack in ``dql/``) and it returns the tolerance
evaluation, the iteration classification, and the R5 infra cross-check verdict.
It performs **no I/O** — the DQL extraction and file writing live in
``build_shape_diff.py`` so the math here is deterministic and unit-testable.

What it implements, straight from §3.5:

* the six shape-diff **dimensions** with their default tolerances (arrival shape,
  latency, service fan-out, error rate, journey mix, and the G4 cache-hit-ratio
  dimension);
* **sampling parity + explicit scale factor** normalization (§3.5 prerequisites 2
  and 3) — rates are sampling-corrected and the baseline is divided by the
  recorded ``scalingFactor`` before any comparison, never inferred silently;
* the **iteration classifier** (§3.5 decision rule): accept / iterate / escalate,
  with the ≤3 iteration cap and a parameter-vs-structural call per miss;
* the **R5 infra cross-check** (§11 R5): validate at least one run dimension
  against an infra-plane signal (CPU / network from Dynatrace Kubernetes
  monitoring), *not* telemetry alone — the mitigation for circular ground truth,
  and **not optional**;
* the **R8 governance flag** (§11 R8): warn when run-config tolerances have been
  loosened relative to the §3.5 defaults ("tolerances look gamed").
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Default tolerances — the §3.5 table. Overridable via run-config.tolerances,
# but any loosening is surfaced by the R8 governance check below.
# ---------------------------------------------------------------------------
DEFAULT_TOLERANCES: dict[str, float] = {
    "arrivalWmape": 0.20,       # arrival shape: WMAPE ≤ 0.20
    "p50Rel": 0.25,             # latency |Δp50| ≤ 25%
    "p95Rel": 0.30,             # latency |Δp95| ≤ 30%
    "p99Rel": 0.35,             # latency |Δp99| ≤ 35%
    "edgePresence": 0.90,       # fan-out: ≥ 90% of baseline edges present
    "edgeRatioLo": 0.50,        # per-edge rate ratio lower bound
    "edgeRatioHi": 2.00,        # per-edge rate ratio upper bound
    "errorDeltaPp": 1.0,        # error rate: Δ ≤ +1.0 pp
    "journeyTvd": 0.15,         # journey mix: total variation distance ≤ 0.15
    "cacheHitAbs": 0.10,        # cache hit ratio: |Δ| ≤ 0.10 absolute
}

# Tolerances where a LARGER configured value means a LOOSER gate (the R8 risk).
# edgeRatioLo is inverted (smaller = looser); handled explicitly below.
_LOOSER_WHEN_LARGER = {
    "arrivalWmape", "p50Rel", "p95Rel", "p99Rel",
    "errorDeltaPp", "journeyTvd", "cacheHitAbs", "edgeRatioHi",
}

MAX_ITERATIONS_DEFAULT = 3


@dataclass
class Dimension:
    """One shape-diff dimension's verdict."""

    name: str
    passed: bool
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = dict(self.detail)
        d["pass"] = self.passed
        return d


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def total_variation_distance(observed: dict[str, float], target: dict[str, float]) -> float:
    """TVD = 0.5 * Σ|obs_i − tgt_i| over the union of keys, each normalized to a
    probability mass. Matches the EXECUTE skill's smoke-gate TVD so the mix
    metric is identical across §3.4.1 and §3.5."""
    keys = set(observed) | set(target)
    obs_sum = sum(observed.values()) or 1.0
    tgt_sum = sum(target.values()) or 1.0
    return 0.5 * sum(
        abs(observed.get(k, 0.0) / obs_sum - target.get(k, 0.0) / tgt_sum) for k in keys
    )


def _sampling_corrected(value: float, sampling_ratio: float) -> float:
    """True rate from an observed, sampled count/rate. ``sampling_ratio`` is the
    fraction retained (e.g. 0.05 = 5% head/tail sampling); 1.0 = unsampled."""
    if sampling_ratio <= 0:
        raise ValueError("sampling_ratio must be > 0")
    return value / sampling_ratio


def wmape(test: list[float], expected: list[float]) -> float:
    """Weighted mean absolute percentage error = Σ|t−e| / Σe, aligned pairwise
    over the shorter of the two curves (per-minute bins). Σe == 0 → returns 0.0
    for an all-zero expected curve (nothing to miss)."""
    n = min(len(test), len(expected))
    denom = sum(expected[:n])
    if denom == 0:
        return 0.0
    return sum(abs(test[i] - expected[i]) for i in range(n)) / denom


# ---------------------------------------------------------------------------
# Per-dimension evaluators
# ---------------------------------------------------------------------------
def eval_arrival_shape(data: dict[str, Any], scaling: float, sampling: dict[str, float],
                       tol: dict[str, float]) -> Dimension:
    """Per-minute RPS curve, test (sampling-corrected) vs baseline (sampling-
    corrected, then multiplied by ``scalingFactor`` to the reduced test scale)."""
    base = [_sampling_corrected(x, sampling["prod"]) * scaling for x in data["baselinePerMin"]]
    test = [_sampling_corrected(x, sampling["test"]) for x in data["testPerMin"]]
    value = wmape(test, base)
    limit = tol["arrivalWmape"]
    return Dimension(
        "arrivalShape",
        value <= limit,
        {"metric": "wmape", "value": round(value, 4), "tolerance": limit,
         "scalingFactor": scaling, "alignedBins": min(len(test), len(base))},
    )


def eval_latency(data: dict[str, Any], tol: dict[str, float]) -> Dimension:
    """|Δp50|/|Δp95|/|Δp99| relative, per journey entry op. Passes iff every
    journey is within every percentile tolerance; reports the worst journey."""
    worst = {"p50Rel": 0.0, "p95Rel": 0.0, "p99Rel": 0.0}
    per_journey: dict[str, Any] = {}
    ok = True
    for jid, pair in data.items():
        b, t = pair["baseline"], pair["test"]
        row = {}
        for pct, key in (("p50", "p50Rel"), ("p95", "p95Rel"), ("p99", "p99Rel")):
            base_v = b[pct]
            rel = abs(t[pct] - base_v) / base_v if base_v else (0.0 if t[pct] == 0 else float("inf"))
            row[key] = round(rel, 4)
            worst[key] = max(worst[key], rel)
            if rel > tol[key]:
                ok = False
        per_journey[jid] = row
    return Dimension(
        "latency",
        ok,
        {**{k: round(v, 4) for k, v in worst.items()},
         "tolerances": {k: tol[k] for k in ("p50Rel", "p95Rel", "p99Rel")},
         "perJourney": per_journey},
    )


def eval_service_fanout(data: dict[str, Any], scaling: float, sampling: dict[str, float],
                        tol: dict[str, float]) -> Dimension:
    """Baseline downstream edges present during the test + per-edge rate ratio in
    band. Baseline edge rates are sampling-corrected and scaled; test rates are
    sampling-corrected."""
    base_edges = {k: _sampling_corrected(v, sampling["prod"]) * scaling
                  for k, v in data["baselineEdges"].items()}
    test_edges = {k: _sampling_corrected(v, sampling["test"]) for k, v in data["testEdges"].items()}
    present = [e for e in base_edges if e in test_edges]
    presence = len(present) / len(base_edges) if base_edges else 1.0
    ratios = []
    out_of_band = []
    for e in present:
        exp = base_edges[e]
        if exp == 0:
            continue
        r = test_edges[e] / exp
        ratios.append(r)
        if r < tol["edgeRatioLo"] or r > tol["edgeRatioHi"]:
            out_of_band.append({"edge": e, "ratio": round(r, 3)})
    rng = [round(min(ratios), 3), round(max(ratios), 3)] if ratios else [None, None]
    passed = presence >= tol["edgePresence"] and not out_of_band
    missing = sorted(set(base_edges) - set(test_edges))
    return Dimension(
        "serviceFanout",
        passed,
        {"edgePresence": round(presence, 4), "edgePresenceTolerance": tol["edgePresence"],
         "rateRatioRange": rng, "rateRatioBand": [tol["edgeRatioLo"], tol["edgeRatioHi"]],
         "missingEdges": missing, "outOfBandEdges": out_of_band},
    )


def eval_error_rate(data: dict[str, Any], tol: dict[str, float]) -> Dimension:
    """Signed Δ in percentage points, per journey. The risk is the test erroring
    *more* than production, so the gate is one-sided: max signed Δpp ≤ tolerance."""
    deltas = {jid: round((p["test"] - p["baseline"]) * 100.0, 3) for jid, p in data.items()}
    worst = max(deltas.values()) if deltas else 0.0
    return Dimension(
        "errorRate",
        worst <= tol["errorDeltaPp"],
        {"deltaPp": worst, "tolerancePp": tol["errorDeltaPp"], "perJourney": deltas},
    )


def eval_journey_mix(data: dict[str, Any], tol: dict[str, float]) -> Dimension:
    """Distribution over journeys (observed run counts) vs approved model weights."""
    tvd = total_variation_distance(data["observed"], data["weights"])
    return Dimension(
        "journeyMix",
        tvd <= tol["journeyTvd"],
        {"tvd": round(tvd, 4), "tolerance": tol["journeyTvd"]},
    )


def eval_cache_hit_ratio(data: dict[str, Any], tol: dict[str, float]) -> Dimension:
    """G4 dimension — per-endpoint |Δ hit-ratio| absolute. Only evaluated when the
    model carried a cacheProfile.targetHitRatio (caller gates on presence)."""
    per_ep = {}
    ok = True
    worst = 0.0
    for ep, pair in data.items():
        delta = abs(pair["test"] - pair["baseline"])
        per_ep[ep] = round(delta, 4)
        worst = max(worst, delta)
        if delta > tol["cacheHitAbs"]:
            ok = False
    return Dimension(
        "cacheHitRatio",
        ok,
        {"maxDeltaAbs": round(worst, 4), "tolerance": tol["cacheHitAbs"], "perEndpoint": per_ep},
    )


# ---------------------------------------------------------------------------
# R5 infra cross-check (§11 R5) — non-telemetry ground truth
# ---------------------------------------------------------------------------
@dataclass
class CrossCheckResult:
    available: bool
    passed: bool
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = dict(self.detail)
        d["available"] = self.available
        d["pass"] = self.passed
        return d


def eval_r5_crosscheck(data: dict[str, Any] | None,
                       min_rise_ratio: float = 2.0) -> CrossCheckResult:
    """Validate one run dimension against an **infra-plane** signal (CPU / pod
    network from Dynatrace Kubernetes monitoring — a different data plane than the
    app's OTLP spans), to break the circular-ground-truth blind spot (§11 R5).

    Logic: if the telemetry claims synthetic load was applied, the target
    workload's infra signal MUST rise materially between the idle window and the
    run window. ``duringRun / idleBaseline >= min_rise_ratio`` confirms the load
    was *physically* real, not just a telemetry artifact. A telemetry claim with a
    flat infra signal FAILS — telemetry is not trustworthy for this run.

    When infra metrics are unavailable, ``available=False`` and ``passed=False``:
    the cross-check is **not optional**, so the caller must not let the run ACCEPT
    clean on telemetry alone (see :func:`classify`)."""
    if not data or not data.get("available", False):
        return CrossCheckResult(
            False, False,
            {"reason": "infra metrics unavailable — R5 circular-ground-truth risk "
                       "unmitigated; wire Dynatrace Kubernetes monitoring "
                       "(dt.kubernetes.container.cpu_usage) or kubeletstats before relying "
                       "on the telemetry-only diff"},
        )
    idle = float(data["idleBaseline"])
    during = float(data["duringRun"])
    claims = bool(data.get("telemetryClaimsLoad", True))
    rise_ratio = (during / idle) if idle > 0 else float("inf")
    # Load claimed → infra must corroborate; no load claimed → infra must stay flat.
    if claims:
        passed = rise_ratio >= min_rise_ratio
        reason = ("infra signal corroborates telemetry load" if passed
                  else "telemetry claims load but infra signal is flat — telemetry "
                       "may be circular/misleading; do NOT accept")
    else:
        passed = rise_ratio < min_rise_ratio
        reason = "no load claimed; infra signal flat as expected" if passed else \
                 "infra signal rose without a telemetry load claim — investigate"
    return CrossCheckResult(
        True, passed,
        {"metric": data.get("metric", "dt.kubernetes.container.cpu_usage"),
         "source": data.get("source", "dynatrace-kubernetes-monitoring"),
         "plane": "infra (non-telemetry)", "workload": data.get("workload"),
         "idleBaseline": idle, "duringRun": during, "riseRatio": round(rise_ratio, 3),
         "minRiseRatio": min_rise_ratio, "telemetryClaimsLoad": claims, "reason": reason},
    )


# ---------------------------------------------------------------------------
# R8 governance — tolerance-drift / anti-gaming flag (§11 R8)
# ---------------------------------------------------------------------------
def governance_tolerance_drift(tol: dict[str, float]) -> list[dict[str, Any]]:
    """Flag any tolerance that has been LOOSENED relative to the §3.5 defaults.
    Does not change the decision — it surfaces potential gaming for the human."""
    drift = []
    for key, default in DEFAULT_TOLERANCES.items():
        configured = tol.get(key, default)
        if configured == default:
            continue
        if key == "edgeRatioLo":
            looser = configured < default  # smaller lower-bound = wider band
        elif key in _LOOSER_WHEN_LARGER:
            looser = configured > default
        else:
            continue
        if looser:
            drift.append({"dimension": key, "default": default, "configured": configured,
                          "direction": "looser"})
    return drift


# ---------------------------------------------------------------------------
# Iteration classifier (§3.5 decision rule)
# ---------------------------------------------------------------------------
# Which classification a failed dimension maps to, and whether the typical fix is
# parameter-only (iterate in place) or structural (→ back to VALIDATE, §3.2.2).
_CLASSIFICATION = {
    "arrivalShape": ("shape", False, "re-segment ramp stages / adjust per-stage rate (parameter)"),
    "latency": ("latency", False, "adjust think-time & pacing; confirm target not under-provisioned (parameter)"),
    "serviceFanout": ("fan-out", True, "missing/attenuated downstream edges usually mean a missing or mis-weighted journey step → VALIDATE"),
    "errorRate": ("error", True, "test erroring above baseline — check correlation chain & target health; may be structural"),
    "journeyMix": ("mix", False, "retune per-journey pacing within ±10% of approved weights (parameter); beyond ±10% → VALIDATE"),
    "cacheHitRatio": ("cache", False, "resize key pool / refit Zipf α to hit target cache ratio (parameter); seed backing store"),
}


@dataclass
class Decision:
    decision: str                 # accept | iterate | escalate
    iteration: int
    failed_dimensions: list[str] = field(default_factory=list)
    classifications: list[dict[str, Any]] = field(default_factory=list)
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "iteration": self.iteration,
            "failedDimensions": self.failed_dimensions,
            "classifications": self.classifications,
            "reason": self.reason,
        }


def classify(dimensions: list[Dimension], crosscheck: CrossCheckResult,
             iteration_index: int, max_iterations: int = MAX_ITERATIONS_DEFAULT,
             require_r5: bool = True) -> Decision:
    """Combine the dimension verdicts, the R5 cross-check, and the iteration cap
    into the §3.5 accept / iterate / escalate decision.

    Order of precedence:
      1. R5 available **and failing** → escalate immediately (infra contradicts
         telemetry; nothing downstream can be trusted).
      2. All dimensions pass:
         - R5 satisfied (or not required) → accept;
         - R5 required but unavailable → escalate (clean accept is blocked so the
           circular-ground-truth residual is never silently waved through).
      3. Any dimension fails:
         - iteration_index > max_iterations → escalate (the 4th miss, §3.5 cap);
         - else → iterate, with a per-miss classification.
    """
    failed = [d for d in dimensions if not d.passed]
    failed_names = [d.name for d in failed]

    if crosscheck.available and not crosscheck.passed:
        return Decision("escalate", iteration_index, failed_names, [],
                        "R5 infra cross-check FAILED — infra signal contradicts the "
                        "telemetry load claim; escalate with diff + infra evidence")

    if not failed:
        if crosscheck.available and crosscheck.passed:
            return Decision("accept", iteration_index, [], [],
                            "all dimensions within tolerance; R5 infra cross-check corroborates")
        if not require_r5:
            return Decision("accept", iteration_index, [], [],
                            "all dimensions within tolerance (R5 cross-check not required)")
        return Decision("escalate", iteration_index, [], [],
                        "all telemetry dimensions pass but R5 infra cross-check is "
                        "unavailable — clean accept blocked to avoid circular ground truth")

    classifications = []
    for d in failed:
        kind, structural, fix = _CLASSIFICATION.get(d.name, ("unknown", True, "inspect"))
        classifications.append({"dimension": d.name, "classification": kind,
                                "structural": structural, "suggestedAction": fix})

    if iteration_index > max_iterations:
        return Decision("escalate", iteration_index, failed_names, classifications,
                        f"{len(failed)} dimension(s) still out of tolerance after "
                        f"{max_iterations} iterations — escalate to human with diff evidence")
    return Decision("iterate", iteration_index, failed_names, classifications,
                    f"{len(failed)} dimension(s) out of tolerance — "
                    "adjust parameters and re-run SYNTHESIZE→EXECUTE→ANALYZE")
