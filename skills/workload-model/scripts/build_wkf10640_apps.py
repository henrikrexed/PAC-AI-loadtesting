"""ISI-5690 driver: the OTHER wkf10640 apps (beyond astroshop) -> workload-model.json + proposal, G0-gated.

Parent ISI-5622; follow-up to ISI-5684 (astroshop frontend, done). The board asked to
(1) widen the window (24h vs ISI-5684's 3h, R1 — better represent rare journeys) and
(2) "analyze the rest of the traffic" — wkf10640 is a shared playground that hosts, beyond
astroshop: unguard, easytrade and an image-presign (Lambda/S3) pipeline, plus low-volume
cloudsreagents / tms / smartfreight A2A agents (documented in the per-app summary, not modeled:
cron-polling or statistically-thin agentic traffic with no sustained arrival curve — the
openclaw n~18 precedent, ISI-5630).

Same deterministic SCOPE pipeline as build_wkf10640.py (classify_by_terminal + shape_ramp +
littles_law + emit + G0); the only inputs that change are the live-extraction fixtures (every
number captured from a real dtctl DQL run on tenant 'tenant-b' = wkf10640, readonly). One model
per app under loadtests/wkf10640-<app>/. Extraction-only — STOP AT SCOPE (no SYNTHESIZE/EXECUTE).

Run:  python3 build_wkf10640_apps.py   (exit 0 iff every app passes G0)
"""

from __future__ import annotations

import json
from pathlib import Path

import clustering as cl
import shaping as sh
from archetypes import classify_by_terminal, coverage as arch_coverage
from emit import build_model, render_proposal
from g0_gate import evaluate_g0

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
FIX = HERE.parent / "fixtures"
GENERATED_AT = "2026-10-12T00:00:00Z"

FIXTURES = [
    "wkf10640_unguard_frontend_extract.json",
    "wkf10640_easytrade_frontendreverseproxy_extract.json",
    "wkf10640_image_provider_extract.json",
]


def build_one(fx: dict) -> tuple[bool, str]:
    journeys = [cl.Journey(op=j["op"], traces=j["traces"], svc_set=j["svc_set"]) for j in fx["journeys"]]
    archetypes = classify_by_terminal(
        journeys,
        patterns=tuple(fx["terminal_patterns"]),
        present=tuple(fx["present"]),
        absent=tuple(fx["absent"]),
        present_steps=fx["present_steps"],
        absent_steps=fx.get("absent_steps"),
    )
    cov = arch_coverage(archetypes)

    stages, cov_ramp = sh.shape_ramp(sh.trim_partial_bins(fx["per_minute_counts"]))
    llc = sh.littles_law(fx["server_rate_tps"], fx["server_mean_ms"], fx["observed_concurrency"])

    model_journeys = []
    for a in archetypes:
        base = fx["present_baseline"] if a.places_order else fx["absent_baseline"]
        entry = a.steps[0]["operation"] if a.steps else a.members[0]
        model_journeys.append({
            "id": a.id,
            "description": f"{a.name}; reconstructed from the trace span-tree over a 24h window. "
                           f"Folds entry ops: {', '.join(a.members)}.",
            "weight": round(a.weight, 4),
            "entrypoint": entry,
            "unlinked": True,  # non-astroshop apps: no source checkout on this tenant -> steps carry no codeRef
            "evidenceSource": "span",
            "steps": a.steps,
            "baseline": base,
        })

    model = build_model(
        name=fx["name"],
        target_service=fx["target_service"],
        environment=fx["environment"],
        generated_at=GENERATED_AT,
        timeframe=fx["timeframe"],
        timeframe_notes="24h peak-inclusive window on a shared demo playground (wider than "
                        "ISI-5684's 3h per R1); noise classifier dropped health/metrics scrapes, "
                        "background polling and static assets; HTTP surface recovered from "
                        "server-span routes (spans-only; access logs unavailable).",
        queries=fx["queries"],
        access_log_availability=fx["access_log_availability"],
        sampling_ratio=fx["sampling_ratio"],
        arrival_model="open",
        stages=[vars(s) for s in stages],
        littles_law=vars(llc),
        journeys=model_journeys,
        payloads={},
        caps=fx["caps"],
        coverage=cov,
    )

    proposal = render_proposal(
        model,
        exclusions=fx["exclusions"],
        target_env="staging / non-production allowlist (production forbidden without board "
                   "approval); tenant wkf10640 kept read-only + isolated per methodology §7.1",
        abort_note=fx["abort_note"],
        risks_extra=fx["risks_extra"],
    )

    out_dir = ROOT / "loadtests" / fx["out_dir"]
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "workload-model.json").write_text(json.dumps(model, indent=2) + "\n")
    (out_dir / "scenario-proposal.md").write_text(proposal)

    g = evaluate_g0(model, dql_run_live=True, proposal_text=proposal)
    summary = (f"{fx['target_service']:38s} G0={'PASS' if g.passed else 'FAIL'} "
               f"({sum(c.passed for c in g.checks)}/{len(g.checks)})  "
               f"archetypes={[(a.id, round(a.weight, 4), len(a.steps)) for a in archetypes]} "
               f"coverage={cov:.3f} ramp={len(stages)}st/CoV{cov_ramp:.3f} LLratio={llc.ratio}")
    if not g.passed:
        summary += "\n    FAILURES: " + "; ".join(f"{c.id}: {c.detail}" for c in g.failures)
    return g.passed, summary


def main() -> int:
    all_pass = True
    for fname in FIXTURES:
        fx = json.loads((FIX / fname).read_text())
        ok, summary = build_one(fx)
        all_pass = all_pass and ok
        print(summary)
    return 0 if all_pass else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
