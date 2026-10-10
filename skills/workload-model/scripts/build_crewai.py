"""Generalization driver (ISI-5630): crewai-deepseek-agent -> workload-model.json, G0-gated.

Runs the SAME skill engine against a CrewAI + DeepSeek agent app (deployed + k6-loaded by
ISI-5644), proving it generalizes beyond the astronomy shop. Agentic archetypes (tool-using vs
pure-LLM turn) come from `classify_by_terminal` with AGENTIC_TOOL_PATTERNS — the identical
engine the commerce run uses with order-terminal patterns.

Consumes `fixtures/crewai_deepseek_extract.json` (live, re-captured with the exact k6 window,
driver config, and deployed source paths). Arrival is STEADY: the k6 driver is
constant-arrival-rate; the interior per-minute CoV is 0.016 (the full-window 0.166 is a
partial-boundary-bin artifact that `shaping.trim_partial_bins` removes).

Run:  python3 build_crewai.py   (exit 0 iff G0 passes)
"""

from __future__ import annotations

import json
from pathlib import Path

import shaping as sh
from emit import build_model, render_proposal
from g0_gate import evaluate_g0

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
FIXTURE = HERE.parent / "fixtures" / "crewai_deepseek_extract.json"
OUT_DIR = ROOT / "loadtests" / "crewai-deepseek-agent"
GENERATED_AT = "2026-10-10T09:05:00Z"

QUERIES = [
    "fetch spans | filter is_root_span && service.name=='crewai-deepseek-agent' | sort start_time asc | summarize takeFirst(span.name) by trace.id | summarize count() by entryOp  (front-end discovery -> single entry request, 301 traces)",
    "fetch logs | filter k8s.container.name=='istio-proxy' over window -> 0 lines  (access-log probe, spans-only)",
    "fetch spans | join [spans|sort start_time asc|summarize collectArray(span.name) by trace.id] on trace.id  (JOURNEY reconstruction: ReAct loop vs single LLM round)",
    "fetch spans | summarize countIf(span.name=='execute_tool') by trace.id | summarize count() by usesTool  (archetype split via AGENTIC_TOOL_PATTERNS -> 96 agentic / 205 conversational)",
    "fetch spans | filter span.name=='agent.turn' | summarize percentile(duration,50/95/99),avg by usesTool  (per-archetype baseline)",
    "fetch spans | filter request | summarize count() by bin(start_time,1m)  (G3-B arrival curve; interior CoV 0.016 -> steady)",
    "fetch spans | filter span.name=='agent.turn' | summarize sum(duration) / window  (observed concurrency 0.448)",
]


def _journey(aid: str, name: str, weight: float, baseline: dict, flow: str, payload_ref: str,
             code_refs: dict) -> dict:
    return {
        "id": aid,
        "description": f"{name}. Reconstructed internal flow: {flow}",
        "weight": round(weight, 4),
        "entrypoint": "crewai-deepseek-agent/request",
        "codeRef": code_refs["entry_handler"],
        "evidenceSource": "span",
        "steps": [
            {"id": "s1", "service": "crewai-deepseek-agent", "operation": "POST /request",
             "callType": "http", "codeRef": code_refs["entry_handler"],
             "evidenceSource": "span", "payloadRef": payload_ref},
            {"id": "s2", "service": "crewai-deepseek-agent", "operation": "llm.call (deepseek-chat via LiteLLM)",
             "callType": "http", "codeRef": code_refs["llm_call"], "evidenceSource": "span"},
        ],
        "baseline": {k: baseline[k] for k in ("p50Ms", "p95Ms", "p99Ms", "errorRate")},
    }


def _bl(d: dict) -> dict:
    return {"p50Ms": d["p50_ms"], "p95Ms": d["p95_ms"], "p99Ms": d["p99_ms"],
            "errorRate": d.get("errorRate", 0.0)}


def main() -> int:
    fx = json.loads(FIXTURE.read_text())
    split = fx["archetype_split"]
    bl = fx["turn_baseline_agent_turn"]
    cr = fx["code_refs"]

    journeys = [
        _journey("conversational",
                 "Conversational — pure-LLM turn (single round); no tool",
                 split["conversational_weight"], _bl(bl["conversational"]),
                 fx["span_trees"]["conversational"], "prompt_chat", cr),
        _journey("agentic",
                 "Agentic — tool-using turn (ReAct: LLM -> tool -> LLM); reaches execute_tool",
                 split["agentic_weight"], _bl(bl["agentic"]),
                 fx["span_trees"]["agentic"], "prompt_agentic", cr),
    ]
    coverage = split["coverage"]

    # G3: steady. Interior CoV 0.016; trim_partial_bins removes the two partial boundary bins
    # that inflate the raw full-window figure. Feed the interior curve.
    stages, cov = sh.shape_ramp(fx["per_minute_cov"]["interior_counts"])

    arr = fx["arrival"]
    llc = sh.littles_law(arr["arrival_rate_tps"], arr["mean_server_response_ms"],
                         arr["observed_concurrency"])

    tools = fx["archetype_split"]["tools_observed"]
    payloads = {
        "prompt_agentic": {"fields": [
            {"name": "task", "type": "string", "generator": "const",
             "values": ["search the web for the latest OTel release and summarize",
                        "calculate the 95th percentile of these latencies"],
             "distribution": "weighted"}], "seed": 42},
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
        timeframe_notes="deploy-free/incident-free k6 window; single-service agent app, entry "
                        "scoped to crewai-deepseek-agent (co-tenant astronomy-shop dropped by scope)",
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
        exclusions="none within service scope — all 301 entry traces are application traffic",
        target_env=f"{fx.get('deployment_environment', 'agentapp')} ns on the memory-benchmark cluster (non-production)",
        abort_note="Abort ABOVE the agentic tail: tool-using turns reach p99 35061 ms (ReAct + 2nd "
                   "LLM round) vs conversational p99 16350 ms — set p95 abort > 8000 ms, errorRate 5%.",
        risks_extra=[
            "**GENERALIZATION RUN (ISI-5630).** Same skill, different app: CrewAI + DeepSeek "
            "(`deepseek/deepseek-chat` via LiteLLM), zero code changes. Behavioral split via the "
            "identical `classify_by_terminal` engine, terminal signal = `execute_tool` instead of "
            "`payment`/`checkout`. Conclusion shape matches the astronomy shop: two archetypes "
            f"distinguished by whether the flow reaches a terminal action. Tools: {tools}.",
            "**Arrival is STEADY (corrected).** The k6 driver is constant-arrival-rate; the interior "
            "per-minute CoV is 0.016. The raw full-window CoV (0.166) was a partial-boundary-bin "
            "artifact — `shaping.trim_partial_bins` now drops those edge buckets before the CoV "
            "gate, so the model correctly emits one steady stage + ramp-down tail (R2: still mean, "
            "no production diurnal envelope).",
            "**Tool-using turns are ~2.3x heavier** (mean 3714 ms vs 1611 ms) — modeled as separate "
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
          f"CoV(interior,trimmed)={cov:.3f} stages={[(s.shape, s.rate) for s in stages]}")
    print(f"Little's Law ratio={llc.ratio}")
    print(f"wrote {OUT_DIR}")
    return 0 if g.passed else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
