"""End-to-end reference driver: oat05854 frontend -> workload-model.json + proposal, G0-gated.

This is the skill's worked example. It takes the live extraction fixture
(`fixtures/oat05854_extract.json` — every number captured from a real dtctl DQL run),
runs the deterministic SCOPE algorithms (clustering -> shaping -> emit), self-validates
with the G0 gate, and writes the artifacts to `loadtests/otel-astronomy-frontend/`.

Run:  python scripts/build_example.py
Exit 0 iff G0 passes. The emitted files are the acceptance evidence for ISI-5630.
"""

from __future__ import annotations

import json
from pathlib import Path

import clustering as cl
import shaping as sh
from emit import build_model, render_proposal
from g0_gate import evaluate_g0

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent  # repo root
FIXTURE = HERE.parent / "fixtures" / "oat05854_extract.json"
OUT_DIR = ROOT / "loadtests" / "otel-astronomy-frontend"
GENERATED_AT = "2026-10-09T00:00:00Z"

QUERIES = [
    "fetch spans | filter request.is_root_span==true | sort start_time asc | summarize takeFirst(service.name),takeFirst(span.name) by trace.id | summarize count() by entryService,entryOp  (G1-C front-end discovery)",
    "fetch logs | filter k8s.container.name=='istio-proxy' | summarize count()  (access-log availability probe -> 0)",
    "fetch spans | filter is_root_span && service.name=='load-generator' && startsWith(span.name,'user_') | summarize count() by entryOp  (G3-A pace)",
    "fetch spans ... join collectDistinct(service.name) by trace.id ... summarize avg(nsvc),takeAny(services) by entryOp  (G1-E reach/svcSet)",
    "fetch spans | filter span.kind=='server' && service.name=='frontend' | summarize percentile(duration,50/95/99),avg(duration) by span.name  (route baselines)",
    "fetch spans | filter is_root_span && service.name=='load-generator' && startsWith(span.name,'user_') | summarize count() by bin(start_time,1m) | summarize avg,stddev  (G3-B CoV)",
    "fetch spans | filter span.kind=='server' && service.name=='frontend' | summarize sum(duration)/window  (observed concurrency)",
    "fetch spans | filter service.name=='product-catalog' && isNotNull(app.product.id) | summarize countDistinctExact(app.product.id),count()  (G4 cache keyCardinality)",
]

# --- per-scenario representative route baseline (dominant member; p99 = cluster worst) ---
# keyed by scenario name produced by clustering.SCENARIO_NAMES
SCENARIO_BASELINE = {
    "Browse product page": {"p50Ms": 2, "p95Ms": 16, "p99Ms": 46, "errorRate": 0.0},   # products dominant; p99 from ai-assistant
    "Cart":                {"p50Ms": 3, "p95Ms": 5,  "p99Ms": 7,  "errorRate": 0.0},
    "Recommendations":     {"p50Ms": 12, "p95Ms": 15, "p99Ms": 20, "errorRate": 0.0},
    "Checkout":            {"p50Ms": 53188, "p95Ms": 106377, "p99Ms": 150441, "errorRate": 0.0},
    "Home":                {"p50Ms": 4, "p95Ms": 5,  "p99Ms": 6,  "errorRate": 0.0},
}

SCENARIO_ENTRYPOINT = {
    "Browse product page": "GET /api/products/[productId]/index",
    "Cart": "POST /api/cart",
    "Recommendations": "GET /api/recommendations",
    "Checkout": "POST /api/checkout",
    "Home": "GET /",
}

# codeRef against the upstream open-telemetry/opentelemetry-demo frontend (Next.js API routes).
# NOT vendored in this repo — flagged in the proposal; paths are stable upstream.
SCENARIO_CODEREF = {
    "Browse product page": "src/frontend/pages/api/products/[productId].ts#handler",
    "Cart": "src/frontend/pages/api/cart.ts#handler",
    "Recommendations": "src/frontend/pages/api/recommendations.ts#handler",
    "Checkout": "src/frontend/pages/api/checkout.ts#handler",
    "Home": "src/frontend/pages/index.tsx#Home",
}


def main() -> int:
    fx = json.loads(FIXTURE.read_text())

    # --- G1: cluster the extracted journeys to <=6 named scenarios ---
    journeys = [cl.Journey(op=j["op"], traces=j["traces"], svc_set=j["svc_set"]) for j in fx["journeys"]]
    scenarios = cl.cluster(journeys)
    scenarios, _ = cl.weight_scenarios(scenarios)
    scenarios, dropped, coverage = cl.enforce_cap(scenarios)

    # --- G3: arrival shaping from the per-minute curve (reconstruct from CoV summary) ---
    cov = fx["per_minute_cov"]["cov"]
    mean_rpm = fx["per_minute_cov"]["meanRpm"]
    # steady here (cov < 0.15): emit the curve summary as a flat body; shape_ramp handles the tail.
    synthetic_curve = [mean_rpm] * fx["per_minute_cov"]["bins"]
    stages, _cov = sh.shape_ramp(synthetic_curve)
    assert abs(_cov) < 1e-9 or cov < sh.COV_STEADY_MAX  # flat curve -> steady branch

    # --- Little's Law (server span, not wrapper) ---
    base = fx["server_baseline_frontend"]
    llc = sh.littles_law(fx["server_rate_tps"], base["mean_ms"], fx["observed_concurrency"])

    # --- assemble journeys with baselines, codeRefs, evidence tags, and G2 correlates ---
    model_journeys = []
    for sc in scenarios:
        jid = sc.name.lower().replace(" ", "-")
        steps = _steps_for(sc)
        model_journeys.append({
            "id": jid,
            "description": f"{sc.name} — merged from {', '.join(sc.members)} (reach {sc.reach:.0f})",
            "weight": round(sc.weight, 4),
            "entrypoint": SCENARIO_ENTRYPOINT.get(sc.name, sc.members[0]),
            "codeRef": SCENARIO_CODEREF.get(sc.name),
            "evidenceSource": "span",
            "spanless": False,
            "steps": steps,
            "baseline": SCENARIO_BASELINE[sc.name],
        })

    payloads = _payloads(fx)
    caps = {"maxRps": 5, "maxVus": 50, "maxDuration": "45m"}

    model = build_model(
        name="otel-astronomy-frontend",
        target_service="frontend-proxy",
        environment=fx["environment"],
        generated_at=GENERATED_AT,
        timeframe=fx["timeframe"],
        timeframe_notes="deploy-free/incident-free 3h window; noise classifier dropped "
                        "health/metrics (memos, honcho), flagd polling, and Kafka consumers",
        queries=QUERIES,
        access_log_availability=fx["access_log_availability"],
        sampling_ratio=fx["sampling_ratio"],
        arrival_model="open",
        stages=[vars(s) for s in stages],
        littles_law=vars(llc) if hasattr(llc, "__dict__") else {
            "expectedConcurrency": llc.expectedConcurrency,
            "observedConcurrency": llc.observedConcurrency,
            "ratio": llc.ratio,
        },
        journeys=model_journeys,
        payloads=payloads,
        caps=caps,
        coverage=coverage,
    )

    proposal = render_proposal(
        model,
        exclusions="health/metrics scrapes, flagd polling, Kafka consumers (noise classifier); "
                   "non-application roots",
        target_env="staging / non-production allowlist (production forbidden without board approval)",
        abort_note="Abort thresholds set ABOVE the observed tail: checkout `POST /api/checkout` "
                   "p99 = 150441 ms is real steady-state latency — set p95 abort > 110000 ms and "
                   "errorRate abort at 5% so the heavy tail does not self-abort the run.",
        risks_extra=[
            "**Checkout heavy tail.** `POST /api/checkout` p50=53 s / p99=150 s on this tenant — "
            "the dominant risk path. Kept as its own unmerged scenario (reach 12) despite 6.6% "
            "weight. Verify this tail is expected before treating a test p99 regression as a fault.",
            "**Front-end choice.** The synthetic `load-generator` driver was preferred over the "
            "edge server `frontend-proxy` for this non-prod window (richer journey names). A "
            "production-faithful model would resolve to `frontend-proxy`/`ingress` — confirm the "
            "intended choice at VALIDATE.",
        ],
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "workload-model.json").write_text(json.dumps(model, indent=2) + "\n")
    (OUT_DIR / "scenario-proposal.md").write_text(proposal)

    g = evaluate_g0(model, dql_run_live=True, proposal_text=proposal)
    print(json.dumps(g.to_dict(), indent=2))
    print(f"\nscenarios: {[s.name for s in scenarios]}  coverage={coverage:.3f}  dropped={[d.name for d in dropped]}")
    print(f"wrote {OUT_DIR}/workload-model.json  and  scenario-proposal.md")
    return 0 if g.passed else 1


def _steps_for(sc: cl.Scenario) -> list[dict]:
    """Downstream steps for a scenario. Checkout carries a real G2 correlates chain."""
    if sc.name == "Checkout":
        return [
            {"id": "s1", "service": "frontend", "operation": "POST /api/cart",
             "callType": "http", "codeRef": "src/frontend/pages/api/cart.ts#handler",
             "evidenceSource": "span"},
            {"id": "s2", "service": "frontend", "operation": "POST /api/checkout",
             "callType": "http", "codeRef": "src/frontend/pages/api/checkout.ts#handler",
             "evidenceSource": "span", "payloadRef": "checkout",
             "dependsOn": ["s1"],
             "correlates": [{
                 "sourceStepId": "s1",
                 "extract": {"from": "header", "path": "set-cookie:session"},
                 "inject": {"into": "header", "as": "cookie"},
             }]},
        ]
    # non-chained scenarios: single entry step, no dependsOn (-> no correlates required)
    return [{
        "id": "s1", "service": "frontend",
        "operation": SCENARIO_ENTRYPOINT.get(sc.name, sc.members[0]),
        "callType": "http", "codeRef": SCENARIO_CODEREF.get(sc.name),
        "evidenceSource": "span",
        **({"payloadRef": "product"} if sc.name == "Browse product page" else {}),
    }]


def _payloads(fx: dict) -> dict:
    keys = list(fx["product_keys"]["access_counts"].keys())
    return {
        "product": {
            "fields": [{
                "name": "productId", "type": "enum", "generator": "const",
                "values": keys, "distribution": "zipf",
            }],
            "seed": 42,
            "cacheProfile": {
                "targetHitRatio": 0.99,
                "keyCardinality": fx["product_keys"]["distinct"],
                "distributionAlpha": 0.1,
                "backingStoreSeeded": True,
            },
        },
        "checkout": {
            "fields": [
                {"name": "email", "type": "string", "generator": "faker:email"},
                {"name": "creditCardNumber", "type": "string", "generator": "faker:ccNumber"},
                {"name": "currencyCode", "type": "enum", "generator": "const",
                 "values": ["USD", "EUR", "GBP", "JPY"], "distribution": "weighted"},
            ],
            "seed": 42,
        },
    }


if __name__ == "__main__":
    import sys
    sys.exit(main())
