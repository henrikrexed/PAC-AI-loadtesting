"""Gate checkers for the EXECUTE stage (methodology §3.4, §6).

Two machine-enforced gates live here:

* ``evaluate_smoke`` — the **V2b-smoke** gate: the six §3.4.1 pass criteria for the
  mandatory small confirmation test. The full run is refused until all six hold.
* ``preflight_v2b`` — the **V2b** pre-flight gate run immediately before the full
  run start (§3.4.2 exit criteria).

Both return a :class:`GateResult` with a per-check breakdown so the run-report can
cite exactly which criterion failed. Neither performs I/O — callers inject the
metrics, the model, and the synthetic-span probe count.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

PRODUCTION_NAMES = {"production", "prod", "prd"}


@dataclass
class Check:
    id: str
    passed: bool
    detail: str


@dataclass
class GateResult:
    name: str
    checks: list[Check] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    @property
    def failures(self) -> list[Check]:
        return [c for c in self.checks if not c.passed]

    def add(self, cid: str, passed: bool, detail: str) -> None:
        self.checks.append(Check(cid, bool(passed), detail))

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate": self.name,
            "passed": self.passed,
            "checks": [
                {"id": c.id, "passed": c.passed, "detail": c.detail} for c in self.checks
            ],
        }


def total_variation_distance(observed: dict[str, float], target: dict[str, float]) -> float:
    """TVD over the union of journey ids = 0.5 * sum |obs_i - tgt_i| of normalized mass."""
    keys = set(observed) | set(target)
    obs_sum = sum(observed.values()) or 1.0
    tgt_sum = sum(target.values()) or 1.0
    return 0.5 * sum(
        abs(observed.get(k, 0.0) / obs_sum - target.get(k, 0.0) / tgt_sum) for k in keys
    )


def _journey_weights(model: dict[str, Any]) -> dict[str, float]:
    return {j["id"]: float(j.get("weight", 0.0)) for j in model["spec"]["journeys"]}


def _journey_baseline_error(model: dict[str, Any]) -> dict[str, float]:
    out = {}
    for j in model["spec"]["journeys"]:
        out[j["id"]] = float(j.get("baseline", {}).get("errorRate", 0.0))
    return out


# §3.4.1 default confirmation-test bounds
SMOKE_MIX_TVD_MAX = 0.30  # criterion 4 (relaxed from V3's 0.15 at reduced scale)


def evaluate_smoke(metrics: dict[str, Any], model: dict[str, Any]) -> GateResult:
    """V2b-smoke gate — the six §3.4.1 criteria. All must hold to allow the full run.

    ``metrics`` is the merged result of the k6 smoke run plus the Dynatrace
    synthetic-span probe. Expected keys::

        http_5xx_count, http_404_count, steps_missing_downstream_span,
        null_extract_failures, dropped_iterations, synthetic_span_count,
        journey_counts: {journey_id: observed_iterations},
        error_counts_per_journey: {journey_id: {"errors": n, "total": n}}
    """
    g = GateResult("V2b-smoke")
    mix_tvd_max = float(
        (model.get("spec", {}).get("caps", {}) or {}).get("smokeMixTvdMax", SMOKE_MIX_TVD_MAX)
    )

    # Criterion 1 — zero 5xx, or per-journey error rate <= model baseline.errorRate.
    fivexx = int(metrics.get("http_5xx_count", 0))
    if fivexx == 0:
        g.add("1-no-5xx", True, "0 5xx responses")
    else:
        baselines = _journey_baseline_error(model)
        per = metrics.get("error_counts_per_journey", {})
        offenders = []
        for jid, b in baselines.items():
            seen = per.get(jid, {})
            total = float(seen.get("total", 0)) or 1.0
            rate = float(seen.get("errors", 0)) / total
            if rate > b + 1e-9:
                offenders.append(f"{jid} {rate:.3f}>{b:.3f}")
        g.add(
            "1-no-5xx",
            not offenders,
            f"{fivexx} 5xx; per-journey breaches: {offenders or 'none'}",
        )

    # Criterion 2 — every step reaches a downstream span; no broken routes / 404s.
    missing = int(metrics.get("steps_missing_downstream_span", 0))
    notfound = int(metrics.get("http_404_count", 0))
    g.add(
        "2-routes-reachable",
        missing == 0 and notfound == 0,
        f"{missing} steps without downstream span, {notfound} 404s",
    )

    # Criterion 3 — chain correlation succeeds: zero null-extract failures.
    nulls = int(metrics.get("null_extract_failures", 0))
    g.add("3-correlation", nulls == 0, f"{nulls} null-extract failures")

    # Criterion 4 — journey mix matches approved weights within TVD <= 0.30.
    observed = {k: float(v) for k, v in metrics.get("journey_counts", {}).items()}
    weights = _journey_weights(model)
    tvd = total_variation_distance(observed, weights)
    g.add(
        "4-journey-mix",
        tvd <= mix_tvd_max + 1e-9,
        f"TVD={tvd:.3f} (max {mix_tvd_max:.2f})",
    )

    # Criterion 5 — at least one synthetic==true span visible in Dynatrace.
    syn = int(metrics.get("synthetic_span_count", 0))
    g.add(
        "5-synthetic-visible",
        syn >= 1,
        f"{syn} synthetic==true spans in backend (baggage promotion {'confirmed' if syn else 'MISSING'})",
    )

    # Criterion 6 — dropped_iterations == 0 at target-scale rate.
    dropped = int(metrics.get("dropped_iterations", 0))
    g.add("6-no-dropped", dropped == 0, f"{dropped} dropped iterations")

    return g


def _max_baseline_p99(model: dict[str, Any]) -> float:
    vals = [
        float(j.get("baseline", {}).get("p99Ms", 0.0)) for j in model["spec"]["journeys"]
    ]
    return max(vals) if vals else 0.0


def preflight_v2b(
    run_config: dict[str, Any],
    model: dict[str, Any],
    smoke: GateResult,
    v2a: dict[str, Any],
    current_commit: str,
    run_dir_exists: bool,
) -> GateResult:
    """V2b pre-flight gate (§3.4.2 exit criteria), enforced immediately before full run.

    ``v2a`` records the upstream static-check gate: ``{"passed": bool, "commit": str}``.
    """
    g = GateResult("V2b")

    target = run_config.get("target", {})
    env = str(target.get("environment", "")).lower()
    on_allowlist = bool(target.get("allowlist", False))
    not_prod = env not in PRODUCTION_NAMES
    g.add(
        "allowlist-nonprod",
        on_allowlist and not_prod,
        f"env={env or '<unset>'} allowlist={on_allowlist} nonprod={not_prod}",
    )

    v2a_ok = bool(v2a.get("passed")) and v2a.get("commit") == current_commit
    g.add(
        "v2a-passed-on-commit",
        v2a_ok,
        f"v2a.passed={v2a.get('passed')} v2a.commit={v2a.get('commit')} current={current_commit}",
    )

    status = model.get("status", {})
    approval = status.get("approval", {}) or {}
    approved = approval.get("decision") == "approved"
    rev_match = approval.get("revision") == status.get("revision")
    hash_match = status.get("hash") and status.get("hash") == run_config.get("modelRef", {}).get(
        "hash"
    )
    g.add(
        "approval-valid",
        approved and rev_match and bool(hash_match),
        f"decision={approval.get('decision')} approvalRev={approval.get('revision')} "
        f"modelRev={status.get('revision')} hashMatch={bool(hash_match)}",
    )

    abort = run_config.get("abort", {})
    caps = run_config.get("caps", {})
    caps_armed = all(k in caps for k in ("maxRps", "maxVus", "maxDuration")) and bool(abort)
    base_p99 = _max_baseline_p99(model)
    p99_threshold = abort.get("p99MsGt")
    # p99 abort threshold MUST be >= baseline.p99Ms when set (§3.4.2 / §3.4 rule 2).
    p99_ok = p99_threshold is None or float(p99_threshold) >= base_p99
    g.add(
        "caps-abort-armed",
        caps_armed and p99_ok,
        f"caps={caps} abort={abort} baselineP99={base_p99} p99ThresholdOk={p99_ok}",
    )

    g.add("smoke-passed", smoke.passed, f"smoke gate passed={smoke.passed}")
    g.add("run-dir", run_dir_exists, f"runs/<ts>/ exists={run_dir_exists}")

    return g
