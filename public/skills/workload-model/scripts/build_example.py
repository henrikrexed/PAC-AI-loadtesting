"""End-to-end reference driver: example storefront extraction -> workload-model.json + proposal.

The skill's worked example. Consumes the SYNTHETIC extraction fixture
(`fixtures/example_extract.json` — every number invented for demonstration; no value was
measured from a real system), runs the deterministic SCOPE pipeline, self-validates with
G0, and writes the artifacts to `out/example-frontend/` (override with --out / WORKLOAD_OUT).

Against a real environment you replace the fixture with the live DQL results from the
query pack in SKILL.md (all queries parameterized by $entryService / $frontendServer /
$timeframe; authentication via the DT_ENDPOINT / DT_API_TOKEN environment variables or
your dtctl context).

Journeys are **behavioral archetypes** (Buyer / Browser) reconstructed from the trace
span-tree, not endpoint clusters — each journey is a real multi-step flow with its ordered
steps and (for the Buyer funnel) the G2 correlates chain. See archetypes.py for the rationale.

Run:  python3 build_example.py [--out DIR]   (exit 0 iff G0 passes)
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import clustering as cl
import shaping as sh
from archetypes import to_archetypes, coverage as arch_coverage
from emit import build_model, render_proposal
from g0_gate import evaluate_g0

HERE = Path(__file__).resolve().parent
FIXTURE = HERE.parent / "fixtures" / "example_extract.json"
DEFAULT_OUT = HERE.parent / "out" / "example-frontend"
GENERATED_AT = "2026-01-01T00:00:00Z"

QUERIES = [
    "fetch spans | filter request.is_root_span==true | sort start_time asc | summarize takeFirst(service.name),takeFirst(span.name) by trace.id | summarize count() by entryService,entryOp  (G1-C front-end discovery)",
    "fetch logs | filter k8s.container.name=='istio-proxy' | summarize count()  (access-log availability probe)",
    "fetch spans | filter is_root_span && service.name=='load-generator' && startsWith(span.name,'user_') | summarize count() by entryOp  (G3-A pace + order-split)",
    "fetch spans ... join collectDistinct(service.name) by trace.id ... summarize takeAny(services) by entryOp  (G1-E svcSet -> order-terminal classification)",
    "fetch spans | filter span.kind=='server' && service.name==$frontendServer | summarize percentile(duration,50/95/99),avg(duration) by span.name  (route baselines)",
    "fetch spans | join [spans|sort start_time asc|summarize collectArray(concat(service.name,span.name)) by trace.id] on trace.id  (JOURNEY STEP RECONSTRUCTION from trace span-tree)",
    "fetch spans | filter is_root_span && ... | summarize count() by bin(start_time,1m) | summarize avg,stddev  (G3-B CoV)",
    "fetch spans | filter span.kind=='server' && service.name==$frontendServer | summarize sum(duration)/window  (observed concurrency)",
    "fetch spans | filter service.name==$cacheService && isNotNull($keyAttr) | summarize countDistinctExact($keyAttr),count()  (G4 cache keyCardinality)",
]

# Journey-level baseline = the defining step of the archetype (Buyer: the order-placing
# checkout step, which carries the heavy tail driving abort thresholds; Browser: the slowest
# read step). p50 from the entry step, p95/p99 from the defining step. Synthetic values.
BUYER_BASELINE = {"p50Ms": 3, "p95Ms": 95000, "p99Ms": 140000, "errorRate": 0.0}
BROWSER_BASELINE = {"p50Ms": 3, "p95Ms": 38, "p99Ms": 45, "errorRate": 0.0}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=None, help="output dir (default: out/example-frontend; env WORKLOAD_OUT)")
    args = ap.parse_args()
    out_dir = Path(args.out or os.environ.get("WORKLOAD_OUT") or DEFAULT_OUT)

    fx = json.loads(FIXTURE.read_text())

    # --- G1: reconstruct behavioral archetypes (Buyer / Browser) from the trace span-tree ---
    journeys = [cl.Journey(op=j["op"], traces=j["traces"], svc_set=j["svc_set"]) for j in fx["journeys"]]
    archetypes = to_archetypes(
        journeys,
        buyer_steps=fx["buyer_steps"],
        browser_steps=fx["browser_steps"],
    )
    cov = arch_coverage(archetypes)

    # --- G3: arrival shaping from the per-minute curve (steady here; CoV < 0.15) ---
    pm = fx["per_minute_cov"]
    stages, _cov = sh.shape_ramp([pm["meanRpm"]] * pm["bins"])

    # --- Little's Law (server span, not the load-driver wrapper) ---
    base = fx["server_baseline_frontend"]
    llc = sh.littles_law(fx["server_rate_tps"], base["mean_ms"], fx["observed_concurrency"])

    # --- assemble 2 behavioral journeys, each a real multi-step flow ---
    model_journeys = []
    for a in archetypes:
        model_journeys.append({
            "id": a.id,
            "description": f"{a.name} — {'places an order' if a.places_order else 'read-only, no order'}; "
                           f"reconstructed from the trace span-tree; folds entry ops: {', '.join(a.members)}",
            "weight": round(a.weight, 4),
            "entrypoint": a.steps[0]["operation"] if a.steps else a.members[0],
            "codeRef": a.steps[0].get("codeRef") if a.steps else None,
            "evidenceSource": "span",
            "steps": a.steps,
            "baseline": BUYER_BASELINE if a.places_order else BROWSER_BASELINE,
        })

    payloads = _payloads(fx)
    caps = {"maxRps": 5, "maxVus": 50, "maxDuration": "45m"}

    model = build_model(
        name="example-frontend",
        target_service="frontend-proxy",
        environment=fx["environment"],
        generated_at=GENERATED_AT,
        timeframe=fx["timeframe"],
        timeframe_notes="deploy-free/incident-free 3h example window; noise classifier dropped "
                        "health/metrics, flagd polling, and Kafka consumers",
        queries=QUERIES,
        access_log_availability=fx["access_log_availability"],
        sampling_ratio=fx["sampling_ratio"],
        arrival_model="open",
        stages=[vars(s) for s in stages],
        littles_law=vars(llc),
        journeys=model_journeys,
        payloads=payloads,
        caps=caps,
        coverage=cov,
    )

    proposal = render_proposal(
        model,
        exclusions="health/metrics scrapes, flagd polling, Kafka consumers (noise classifier)",
        target_env="non-production allowlist (production forbidden without explicit approval)",
        abort_note="Abort thresholds set ABOVE the Buyer tail: `POST /api/checkout` p99 = 140000 ms "
                   "is real order-placing latency — set p95 abort > 100000 ms, errorRate abort 5%.",
        risks_extra=[
            "**Journeys are behavioral archetypes, not endpoints.** Steps were reconstructed from "
            "the trace span-tree (`collectArray` over `sort start_time asc`). The Buyer funnel's "
            "downstream fan-out (PlaceOrder → GetCart → GetProduct×N → Convert×N → shipping quote "
            "→ payment Charge → ship-order → EmptyCart → email) is captured as the checkout step's "
            "reach-12 signature; the driver replays the 4 user-facing HTTP steps and the backend "
            "funnel follows.",
            "**R5 / session-chaining limit.** In this example the load driver carries no persistent "
            "session id on browse spans (`app.user.id` appears only on cart/checkout), so "
            "browse→buy cannot be chained across independent tasks. The Buyer archetype is "
            "therefore reconstructed from the self-contained checkout_* traces (which internally "
            "browse→cart→checkout). A real production front-end with a `session.id` cookie lets "
            "SCOPE chain full sessions (see the session-stitch utility).",
            "**Weights are per-outcome.** Buyer ≈6.6%, Browser ≈93.4% of entry traffic (share of "
            "flows that place an order vs not), summed from the order-split query.",
        ],
    )

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "workload-model.json").write_text(json.dumps(model, indent=2) + "\n")
    (out_dir / "scenario-proposal.md").write_text(proposal)

    g = evaluate_g0(model, dql_run_live=True, proposal_text=proposal)
    print(json.dumps(g.to_dict(), indent=2))
    print(f"\narchetypes: {[(a.id, round(a.weight, 3), len(a.steps)) for a in archetypes]}  coverage={cov:.3f}")
    print(f"wrote {out_dir}/workload-model.json  and  scenario-proposal.md")
    return 0 if g.passed else 1


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
