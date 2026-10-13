"""ISI-5684 driver: wkf10640 astroshop frontend -> workload-model.json + proposal, G0-gated.

Validates the SCOPE stage end-to-end on a FRESH, board-provided Dynatrace tenant
(wkf10640, apps.dynatrace.com, readonly dt0s16 read token). Same deterministic pipeline
as build_example.py; the only inputs that change are the live-extraction facts in
fixtures/wkf10640_extract.json (every number captured from a real dtctl DQL run on the
new tenant). Target app = the OpenTelemetry Astroshop demo, the dominant workload in a
shared multi-app playground.

Run:  python3 build_wkf10640.py   (exit 0 iff G0 passes)
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import clustering as cl
import session_stitch as ss
import shaping as sh
from archetypes import to_archetypes, coverage as arch_coverage
from emit import build_model, render_proposal
from g0_gate import evaluate_g0

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
# FIXTURE can be overridden to a live-extracted file (see live_extract.py / ISI-5723 rev2
# full-live demo) without changing the deterministic build at all: same schema in, same
# G0-gated model out. Defaults to the captured 2026-10-12 extract.
FIXTURE = Path(os.environ.get("WKF10640_FIXTURE", HERE.parent / "fixtures" / "wkf10640_extract.json"))
SESSION_FIXTURE = HERE.parent / "fixtures" / "wkf10640_session_stitch.json"
OUT_DIR = ROOT / "loadtests" / "wkf10640-astroshop-frontend"
GENERATED_AT = os.environ.get("WKF10640_GENERATED_AT", "2026-10-12T00:00:00Z")

QUERIES = [
    "fetch spans | filter request.is_root_span==true | sort start_time asc | summarize takeFirst(service.name),takeFirst(span.name) by trace.id | summarize count() by entryService,entryOp  (G1-C front-end discovery -> frontend dominant)",
    "fetch logs | filter k8s.container.name=='istio-proxy' | summarize count()  (access-log availability probe -> 0 lines => spans-only)",
    "fetch spans | filter span.kind=='server' && service.name=='frontend' | summarize count() by span.name  (HTTP route surface recovered from server spans)",
    "fetch spans | filter request.is_root_span==true && service.name=='frontend' | summarize countDistinctExact(trace.id)  (total root traces = 306,033)",
    "fetch spans | filter service.name=='checkout' || service.name=='payment' | summarize countDistinctExact(trace.id)  (order-terminal reach -> buyer_traces = 2,810)",
    "fetch spans | filter span.kind=='server' && service.name=='frontend' | summarize percentile(duration,50/95/99),avg(duration),count(),countIf(is_failed) by span.name  (route + server baselines)",
    "fetch spans | filter request.is_root_span==true && service.name=='frontend' | makeTimeseries count() interval:1m  (G3-B per-minute arrival curve, 181 bins, CoV 0.29)",
    "fetch spans | filter span.kind=='server' && service.name=='frontend' | summarize sum(duration),count()  (observed concurrency busy-integral + server rate)",
    "fetch spans | filter service.name=='product-catalog' && isNotNull(app.product.id) | summarize countDistinctExact(app.product.id),count() by app.product.id  (G4 cache keyCardinality = 10)",
    "fetch events | filter event.type=='CUSTOM_DEPLOYMENT' | summarize count() by dt.entity.service  (window hygiene: frontend SERVICE-39720C1E0047A5C0 = 3 redeploys -> caveat)",
]

# Journey-level baseline: p50 from the entry step, p95/p99 from the defining step
# (Buyer: the order-placing checkout step; Browser: the slowest read step, recommendations).
BUYER_BASELINE = {"p50Ms": 3, "p95Ms": 236, "p99Ms": 364, "errorRate": 0.0}
BROWSER_BASELINE = {"p50Ms": 5, "p95Ms": 84, "p99Ms": 148, "errorRate": 0.0}


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
                "distributionAlpha": 0.05,
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


def main() -> int:
    fx = json.loads(FIXTURE.read_text())
    sfx = json.loads(SESSION_FIXTURE.read_text())

    # --- SCOPE §3.1 step 2c tier (ii) / Path B: OTel session.id session-stitch (ISI-5693) ---
    # Grail-native. We record session.id coverage so fidelity is auditable (R1-adjacent), but on
    # THIS tenant the signal is NOT usable as journey think-time (board review, 2026-10-12):
    # session.id is emitted ONLY on the homepage ad/recommendation data fetch (frontend
    # `/api/data` → `ad GetAds`), which repeats during a session. Verified read-only: ad-session
    # traces reach NONE of cart/checkout/payment/product-catalog, and 0 of 1.41M frontend spans
    # carry session.id. So Path B here sees a single use case (ad-fetch cadence), not the
    # multi-action user journey. We therefore DO NOT attach the ad cadence as Browser think-time
    # (that would overstate it); the Browser journey stays on span-order. See the R5 note and
    # docs/evidence/isi5693-session-stitch.md.
    session_cov = ss.session_coverage(sfx["coverage_rows"])

    # --- G1: behavioral archetypes (Buyer / Browser) by business outcome ---
    journeys = [cl.Journey(op=j["op"], traces=j["traces"], svc_set=j["svc_set"]) for j in fx["journeys"]]
    archetypes = to_archetypes(journeys, buyer_steps=fx["buyer_steps"], browser_steps=fx["browser_steps"])
    cov = arch_coverage(archetypes)

    # --- G3: arrival shaping from the live per-minute curve (CoV 0.29 -> ramped) ---
    stages, cov_ramp = sh.shape_ramp(fx["per_minute_counts"])

    # --- Little's Law (server span, not a driver wrapper) ---
    base = fx["server_baseline_frontend"]
    llc = sh.littles_law(fx["server_rate_tps"], base["mean_ms"], fx["observed_concurrency"])

    model_journeys = []
    for a in archetypes:
        model_journeys.append({
            "id": a.id,
            "description": f"{a.name} - {'places an order' if a.places_order else 'read-only, no order'}; "
                           f"reconstructed from the trace span-tree; folds entry ops: {', '.join(a.members)}",
            "weight": round(a.weight, 4),
            "entrypoint": a.steps[0]["operation"] if a.steps else a.members[0],
            "codeRef": a.steps[0].get("codeRef") if a.steps else None,
            "evidenceSource": "span",
            "steps": a.steps,
            "baseline": BUYER_BASELINE if a.places_order else BROWSER_BASELINE,
        })

    payloads = _payloads(fx)
    caps = {"maxRps": 60, "maxVus": 50, "maxDuration": "45m"}

    model = build_model(
        name="otel-astroshop-frontend-wkf10640",
        target_service="frontend",
        environment=fx["environment"],
        generated_at=GENERATED_AT,
        timeframe=fx["timeframe"],
        timeframe_notes="3h window on a shared demo playground; noise classifier dropped "
                        "health/metrics scrapes, flagd polling, Kafka consumers, and the "
                        "static image/_next asset routes; HTTP surface recovered from frontend "
                        "server-span routes (spans-only; access logs unavailable).",
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
        session_id_coverage=session_cov,
        revision=3,
    )

    proposal = render_proposal(
        model,
        exclusions="health/metrics scrapes, flagd polling, Kafka consumers, static image/_next asset routes (noise classifier)",
        target_env="staging / non-production allowlist (production forbidden without board approval); tenant wkf10640 kept isolated per methodology §7.1",
        abort_note="checkout is healthy on this tenant (POST /api/checkout p99 = 364 ms, errorRate 0). "
                   "Set p95 abort > 1000 ms and errorRate abort 2% (frontend overall errorRate 0.00093).",
        risks_extra=[
            "**Access logs unavailable -> spans-only extraction.** The istio-proxy access-log probe "
            "returned 0 lines; the HTTP surface was recovered from frontend server-span `span.name` "
            "routes. x-request-id chaining is therefore unavailable; journey steps are reconstructed "
            "from the trace span-tree.",
            "**Window hygiene caveat.** wkf10640 is a shared, continuously-deployed demo playground: "
            "the target service (SERVICE-39720C1E0047A5C0, astroshop frontend) saw 3 CUSTOM_DEPLOYMENT "
            "events and the tenant 31 Davis problems in the 3h window. Same-image demo redeploys; "
            "baselines are computed over 810,116 server spans so transient deploys do not dominate. "
            "A stricter run should shrink to a deploy-free sub-window.",
            "**Weights are per-outcome.** Buyer ~0.9%, Browser ~99.1% of entry traffic (2,810 vs "
            "303,223 of 306,033 frontend root traces that do / do not reach checkout/payment).",
            "**R1 sampling.** dt.system.sampling_ratio = 1.0 on frontend root spans (no sampling "
            "correction applied).",
            "**R5 session-chaining (Path B evaluated — NOT usable as journey think-time here).** "
            "An OTel `session.id` exists, but only on the homepage ad/recommendation data fetch "
            "(frontend `/api/data` -> `ad GetAds`), which repeats during a session (20.4% of ad "
            "spans; 5,241 sessions, mean 5.3 fetches each, ~7.2s median cadence). Verified read-only: "
            "ad-session traces reach NONE of cart/checkout/payment/product-catalog, and **0 of "
            "1.41M frontend spans carry `session.id`** — the id never tags a real user action "
            "(browse/cart/checkout all exist but are untagged). So Path B sees a single use case "
            "(ad-fetch cadence), not a multi-action user journey; the ~7.2s is page-refresh cadence, "
            "NOT per-action think-time, and is deliberately NOT attached to any journey. Both Browser "
            "and Buyer stay on span-order reconstruction. Coverage is still recorded on "
            "`source.sessionIdCoverage` for auditability. **To make Path B usable the app must "
            "propagate `session.id` as baggage onto the frontend entry spans of every action** "
            "(OTel session semconv), not just the ad call. Path A RUM fusion remains board-gated "
            "(ISI-5691).",
        ],
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "workload-model.json").write_text(json.dumps(model, indent=2) + "\n")
    (OUT_DIR / "scenario-proposal.md").write_text(proposal)

    g = evaluate_g0(model, dql_run_live=True, proposal_text=proposal)
    print(json.dumps(g.to_dict(), indent=2))
    print(f"\narchetypes: {[(a.id, round(a.weight, 4), len(a.steps)) for a in archetypes]}  coverage={cov:.3f}")
    print(f"ramp: {len(stages)} stages, CoV={cov_ramp:.4f}  littlesLaw ratio={llc.ratio}")
    print(f"wrote {OUT_DIR}/workload-model.json  and  scenario-proposal.md")
    return 0 if g.passed else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
