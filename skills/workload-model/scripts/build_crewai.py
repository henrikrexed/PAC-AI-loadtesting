"""Generalization driver (ISI-5630): crewai-deepseek-agent -> workload-model.json, G0-gated.

Runs the SAME skill engine against a CrewAI + DeepSeek agent app (deployed+loaded by ISI-5644),
proving it generalizes beyond the astronomy shop. Agentic archetypes (tool-using vs pure-LLM
turn) come from `classify_by_terminal` with AGENTIC_TOOL_PATTERNS — the identical engine the
commerce run uses with order-terminal patterns. This is the first run where the CoV ramp path
fires (CoV 0.233 >= 0.15).

Run:  python3 build_crewai.py   (exit 0 iff G0 passes)
"""

from __future__ import annotations

import json
from pathlib import Path

import shaping as sh
from archetypes import AGENTIC_TOOL_PATTERNS, Archetype
from emit import build_model, render_proposal
from g0_gate import evaluate_g0

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
FIXTURE = HERE.parent / "fixtures" / "crewai_deepseek_extract.json"
OUT_DIR = ROOT / "loadtests" / "crewai-deepseek-agent"
GENERATED_AT = "2026-10-09T09:05:00Z"

QUERIES = [
    "fetch spans | filter is_root_span && service.name=='crewai-deepseek-agent' | sort start_time asc | summarize takeFirst(span.name) by trace.id | summarize count() by entryOp  (front-end discovery -> single entry request)",
    "fetch logs | filter k8s.container.name=='istio-proxy' | summarize count()  (access-log probe -> 0, spans-only)",
    "fetch spans | join [spans|sort start_time asc|summarize collectArray(span.name) by trace.id] on trace.id  (JOURNEY reconstruction: ReAct loop vs single LLM round)",
    "fetch spans | filter request && summarize countIf(span.name=='execute_tool') by trace.id | summarize count() by usesTool  (archetype split via AGENTIC_TOOL_PATTERNS)",
    "fetch spans | filter request | summarize percentile(duration,50/95/99),avg by usesTool  (per-archetype baseline)",
    "fetch spans | filter request | summarize count() by bin(start_time,1m)  (G3-B arrival curve + CoV 0.233 -> ramp)",
    "fetch spans | filter request | summarize sum(duration) over active window  (observed concurrency)",
]


def _journey(a: dict, aid: str, name: str, places_order: bool, driver_op: str, flow: str,
             payload_ref: str) -> dict:
    return {
        "id": aid,
        "description": f"{name}. Reconstructed internal flow: {flow}",
        "weight": round(a["weight"], 4),
        "entrypoint": driver_op,
        "unlinked": True,  # crewai-deepseek-agent source not vendored in this repo (deployed via ISI-5644)
        "evidenceSource": "span",
        "steps": [{
            "id": "s1", "service": "crewai-deepseek-agent", "operation": driver_op,
            "callType": "http", "evidenceSource": "span", "payloadRef": payload_ref,
        }],
        "baseline": a["baseline"],
    }


def main() -> int:
    fx = json.loads(FIXTURE.read_text())
    split = fx["archetype_split"]

    # --- behavioral archetypes (agentic vs conversational) from the SAME engine ---
    journeys = [
        _journey(split["agentic_tool_using"], "agentic",
                 "Agentic — tool-using turn (ReAct: LLM -> tool -> LLM); reaches execute_tool",
                 True, "crewai-deepseek-agent/request", fx["reconstructed_flows"]["agentic"],
                 "prompt_agentic"),
        _journey(split["conversational_pure_llm"], "conversational",
                 "Conversational — pure-LLM turn (single round); no tool",
                 False, "crewai-deepseek-agent/request", fx["reconstructed_flows"]["conversational"],
                 "prompt_chat"),
    ]
    journeys.sort(key=lambda j: j["weight"], reverse=True)
    coverage = sum(j["weight"] for j in journeys)

    # --- G3: CoV 0.233 >= 0.15 -> the ramp path fires (first time across all tenants) ---
    stages, cov = sh.shape_ramp([float(x) for x in fx["per_minute_curve_rpm"]])

    # --- Little's Law over the active window (server-side request span) ---
    llc = sh.littles_law(fx["arrival_rate_tps_active"], fx["blended_mean_ms"],
                         fx["observed_concurrency_active"])

    payloads = {
        "prompt_agentic": {"fields": [
            {"name": "task", "type": "string", "generator": "const",
             "values": ["search the web for the latest OTel release and summarize",
                        "look up the current time in Tokyo and convert to UTC"],
             "distribution": "uniform"}], "seed": 42},
        "prompt_chat": {"fields": [
            {"name": "task", "type": "string", "generator": "const",
             "values": ["explain distributed tracing in one paragraph",
                        "what is Little's Law"], "distribution": "uniform"}], "seed": 42},
    }

    model = build_model(
        name="crewai-deepseek-agent",
        target_service="crewai-deepseek-agent",
        environment=fx["environment"],
        generated_at=GENERATED_AT,
        timeframe=fx["timeframe"],
        timeframe_notes="active load window (ramp-up -> plateau 12rpm -> ramp-down); single-service "
                        "agent app, no noise classifier hits",
        queries=QUERIES,
        access_log_availability=fx["access_log_availability"],
        sampling_ratio=fx["sampling_ratio"],
        arrival_model="open",
        stages=[vars(s) for s in stages],
        littles_law=vars(llc),
        journeys=journeys,
        payloads=payloads,
        caps={"maxRps": 2, "maxVus": 20, "maxDuration": "30m"},
        coverage=coverage,
    )

    proposal = render_proposal(
        model,
        exclusions="none — single-service agent app; all 303 entry traces are application traffic",
        target_env="agentapp ns on the memory-benchmark cluster (non-production)",
        abort_note="Abort ABOVE the agentic tail: tool-using turns reach p99 35061 ms (ReAct + 2nd "
                   "LLM round) vs conversational p99 16350 ms — set p95 abort > 8000 ms, errorRate 5%.",
        risks_extra=[
            "**GENERALIZATION RUN (ISI-5630).** Same skill, different app: CrewAI + DeepSeek "
            "(`deepseek/deepseek-chat` via LiteLLM), zero code changes. Behavioral split via the "
            "identical `classify_by_terminal` engine, terminal signal = `execute_tool` instead of "
            "`payment`/`checkout`. Conclusion shape matches the astronomy shop: two archetypes "
            "distinguished by whether the flow reaches a terminal action.",
            "**Ramp path fired for the first time.** CoV 0.233 ≥ 0.15 → the arrival curve was "
            "segmented into ramp-up → plateau (12 rpm) → ramp-down stages (vs the flat astronomy / "
            "openclaw tenants that emitted a single steady stage). Note: this ramp is driver-induced "
            "(load on/off), not a production diurnal curve — R2 still applies.",
            "**Tool-using turns are ~2.3× heavier** (mean 3695 ms vs 1612 ms) — modeled as separate "
            "baselines so a load test exercises both the cheap conversational path and the expensive "
            "ReAct path at their true 32/68 mix.",
        ],
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "workload-model.json").write_text(json.dumps(model, indent=2) + "\n")
    (OUT_DIR / "scenario-proposal.md").write_text(proposal)

    g = evaluate_g0(model, dql_run_live=True, proposal_text=proposal)
    print(json.dumps(g.to_dict(), indent=2))
    print(f"\narchetypes: {[(j['id'], j['weight']) for j in journeys]}  coverage={coverage:.3f}  "
          f"CoV={cov:.3f} stages={[(s.shape, s.rate) for s in stages]}")
    print(f"Little's Law ratio={llc.ratio}")
    print(f"wrote {OUT_DIR}")
    return 0 if g.passed else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
