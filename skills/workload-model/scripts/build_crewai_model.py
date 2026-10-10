"""Generalization driver: crewai-deepseek-agent (oat05854) -> workload-model.json + proposal, G0-gated.

Runs the SAME deterministic SCOPE pipeline as build_example.py (the astronomy-shop worked
example), but against the DeepSeek-backed CrewAI agent app deployed + loaded under ISI-5644
(parent ISI-5630 generalization test). The ONLY configuration difference is the terminal-action
pattern set: `AGENTIC_TOOL_PATTERNS` (did the agent turn invoke a tool?) instead of
`ORDER_TERMINAL_PATTERNS` (did the flow place an order?). Same `classify_by_terminal` engine ->
the §2.1 agnostic-engine thesis, now demonstrated on DeepSeek + sustained load (the gap the
openclaw-gateway probe, GLM / n~18, left open in GENERALIZATION.md).

Every number comes from fixtures/crewai_deepseek_extract.json, captured live from dtctl DQL over
the clean k6 window 2026-10-10T08:35:58Z -> 09:01:31Z.

Run:  python3 build_crewai_model.py   (exit 0 iff G0 passes)
"""

from __future__ import annotations

import json
from pathlib import Path

import shaping as sh
from archetypes import classify_by_terminal, coverage as arch_coverage, AGENTIC_TOOL_PATTERNS
from clustering import Journey
from emit import build_model, render_proposal
from g0_gate import evaluate_g0

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
FIXTURE = HERE.parent / "fixtures" / "crewai_deepseek_extract.json"
OUT_DIR = ROOT / "loadtests" / "crewai-deepseek-agent"
GENERATED_AT = "2026-10-10T09:10:00Z"

QUERIES = [
    "fetch spans | filter request.is_root_span==true | sort start_time asc | summarize takeFirst(service.name),takeFirst(span.name) by trace.id | summarize count() by entryService,entryOp  (G1-C front-end discovery -> crewai-deepseek-agent/request, 301 traces)",
    "fetch logs | filter k8s.container.name=='istio-proxy' | summarize count()  (access-log availability probe -> 0 lines => spans-only)",
    "fetch spans | filter is_root_span && service.name=='crewai-deepseek-agent' && span.name=='crewai-deepseek-agent/request' | join [spans|filter span.name=='execute_tool'|summarize count() by trace.id] leftOuter on trace.id | summarize count() by archetype  (behavioral split: Agentic 96 / Conversational 205)",
    "fetch spans | filter span.name=='execute_tool' | summarize n=count() by trace.id | limit 1 | join [spans] inner on trace.id | sort start_time asc  (JOURNEY STEP RECONSTRUCTION from the trace span-tree, both archetypes)",
    "fetch spans | filter span.name=='agent.turn' && service.name=='crewai-deepseek-agent' | summarize percentile(duration,50/95/99),avg(duration),sum(duration),count()  (per-turn baseline + Little's Law busy-time integral)",
    "fetch spans | filter span.name=='execute_tool' | summarize count() by tool.name  (tools observed: web_search 141, calculator 38)",
    "fetch spans | filter is_root_span && service.name=='crewai-deepseek-agent' | summarize count() by bin(start_time,1m) | summarize avg,stddev  (G3-B CoV: interior 0.016 steady)",
]


def main() -> int:
    fx = json.loads(FIXTURE.read_text())
    sp = fx["archetype_split"]
    tb = fx["turn_baseline_agent_turn"]
    ar = fx["arrival"]
    cr = fx["code_refs"]

    # --- G1: two agent-turn archetypes, split by the terminal signal execute_tool ---
    # Each archetype is fed as a Journey whose svc_set carries the terminal marker (or not),
    # so the SAME classify_by_terminal engine folds them -- identical to to_archetypes() for
    # commerce, only the pattern set differs (AGENTIC_TOOL_PATTERNS). The per-trace split was
    # already resolved live in DQL (96 / 205); here we reproduce the fold deterministically.
    journeys = [
        Journey(op="crewai-deepseek-agent/request [tool-using]", traces=sp["agentic_traces"],
                svc_set=["crewai-deepseek-agent", "execute_tool", "web_search", "calculator"]),
        Journey(op="crewai-deepseek-agent/request [pure-llm]", traces=sp["conversational_traces"],
                svc_set=["crewai-deepseek-agent"]),
    ]

    agentic_steps = [{
        "id": "s1", "service": "crewai-deepseek-agent", "operation": "POST /request {turn_type:tool}",
        "callType": "http", "codeRef": cr["entry_handler"], "evidenceSource": "span",
        "payloadRef": "tool_prompt",
        "baseline": {"p50Ms": tb["agentic"]["p50_ms"], "p95Ms": tb["agentic"]["p95_ms"],
                     "p99Ms": tb["agentic"]["p99_ms"], "errorRate": tb["agentic"]["errorRate"]},
    }]
    conversational_steps = [{
        "id": "s1", "service": "crewai-deepseek-agent", "operation": "POST /request {turn_type:chat}",
        "callType": "http", "codeRef": cr["entry_handler"], "evidenceSource": "span",
        "payloadRef": "chat_prompt",
        "baseline": {"p50Ms": tb["conversational"]["p50_ms"], "p95Ms": tb["conversational"]["p95_ms"],
                     "p99Ms": tb["conversational"]["p99_ms"], "errorRate": tb["conversational"]["errorRate"]},
    }]

    archetypes = classify_by_terminal(
        journeys,
        patterns=AGENTIC_TOOL_PATTERNS,
        present=("agentic", "Agentic — tool-using turn (ReAct loop: execute_tool)"),
        absent=("conversational", "Conversational — pure-LLM turn (no tool call)"),
        present_steps=agentic_steps,
        absent_steps=conversational_steps,
    )
    cov = arch_coverage(archetypes)

    # --- G3: arrival shaping from the real interior per-minute curve (steady; CoV 0.016 < 0.15) ---
    stages, cov_arrival = sh.shape_ramp([float(c) for c in fx["per_minute_cov"]["interior_counts"]])

    # --- Little's Law: server(turn)-side agent.turn span, NOT the k6 wrapper ---
    llc = sh.littles_law(ar["arrival_rate_tps"], ar["mean_server_response_ms"], ar["observed_concurrency"])

    model_journeys = []
    for a in archetypes:
        model_journeys.append({
            "id": a.id,
            "description": (
                f"{a.name}. Reconstructed from the trace span-tree: "
                f"{fx['span_trees']['agentic' if a.places_order else 'conversational']}. "
                f"One HTTP driver step (POST /request); the internal span tree runs server-side "
                f"within that request. Terminal signal = execute_tool "
                f"({'present' if a.places_order else 'absent'})."
            ),
            "weight": round(a.weight, 4),
            "entrypoint": fx["front_end"]["resolved_op"],
            "codeRef": cr["entry_handler"],
            "evidenceSource": "span",
            "steps": a.steps,
            "baseline": a.steps[0]["baseline"],
        })

    payloads = {
        "tool_prompt": {
            "fields": [{
                "name": "prompt", "type": "enum", "generator": "const",
                "values": [
                    "What is 3 * (47 + 19)? Show the result.",
                    "Search for the latest on OpenTelemetry gen_ai semantic conventions and summarize.",
                    "Compute (1024 / 8) + 256 and explain the result briefly.",
                    "What is 15% of 2480? Use the calculator.",
                    "Search for the definition of the ReAct agent pattern and summarize it.",
                ],
                "distribution": "uniform",
            }, {
                "name": "turn_type", "type": "enum", "generator": "const",
                "values": ["tool"], "distribution": "weighted",
            }],
            "seed": 42,
        },
        "chat_prompt": {
            "fields": [{
                "name": "prompt", "type": "enum", "generator": "const",
                "values": [
                    "In one sentence, what is observability?",
                    "Explain the difference between a trace and a span briefly.",
                    "What is a load test? Answer in two sentences.",
                    "What is Little's Law? One sentence.",
                    "Define 'p95 latency' in one sentence.",
                ],
                "distribution": "uniform",
            }, {
                "name": "turn_type", "type": "enum", "generator": "const",
                "values": ["chat"], "distribution": "weighted",
            }],
            "seed": 42,
        },
    }

    caps = {"maxRps": 2, "maxVus": 40, "maxDuration": "30m"}

    model = build_model(
        name="crewai-deepseek-agent",
        target_service="crewai-deepseek-agent",
        environment=fx["environment"],
        generated_at=GENERATED_AT,
        timeframe=fx["timeframe"],
        timeframe_notes=(
            "clean deploy-free/incident-free k6 window (25m33s). Co-tenant astronomy-shop / honcho "
            "/ memos / flagd entries excluded by service scope; front-end discovery resolved "
            "crewai-deepseek-agent/request (301 root spans) unambiguously. CoV on the two partial "
            "boundary minutes is an edge artifact (0.166); true interior arrival is steady (0.016)."
        ),
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
        exclusions="co-tenant astronomy-shop / honcho / memos / flagd entries (out of service scope); health probes",
        target_env="staging / non-production (ns agentapp on the memory-benchmark cluster; production forbidden without board approval)",
        abort_note=(
            "Abort thresholds set ABOVE the Agentic tail: agent.turn Agentic p99 = 35061 ms is the "
            "real ReAct-loop latency (web_search/calculator + multiple llm.call round-trips) — set "
            "p95 abort > 8000 ms, errorRate abort 5% (observed span errorRate 0.0; k6 http_req_failed 0.99%)."
        ),
        risks_extra=[
            "**Agentic/Conversational is the same engine as Buyer/Browser.** The split is "
            "`classify_by_terminal()` with terminal signal = `execute_tool` (AGENTIC_TOOL_PATTERNS) "
            "instead of order-terminal — zero code change from the astronomy-shop example. This is the "
            "definitive DeepSeek + sustained-load generalization the GLM / n~18 openclaw-gateway probe "
            "could not provide (see GENERALIZATION.md).",
            "**Weights ≈ driver TOOL_RATIO.** Agentic 0.319 / Conversational 0.681 over 301 turns "
            "(coverage 1.0) reproduce the k6 driver's TOOL_RATIO=0.30 — the skill recovers the injected "
            "behavioral mix from telemetry alone.",
            "**Single-step driver journey.** Each turn is one HTTP POST /request; the server-side ReAct "
            "loop (agent.turn → llm.call → chat → execute_tool×N → finalize) is internal to that request, "
            "so there is no multi-step correlates chain to carry (unlike the Buyer funnel). Baselines are "
            "per-archetype agent.turn percentiles, not route fan-out.",
            "**R5 cross-check.** Tools are hermetic (no outbound network); execute_tool latency reflects "
            "in-process work, not real third-party calls. A production agent with live tool backends would "
            "show heavier, more variable Agentic tails — cross-check against infra metrics on any real run.",
        ],
    )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "workload-model.json").write_text(json.dumps(model, indent=2) + "\n")
    (OUT_DIR / "scenario-proposal.md").write_text(proposal)

    g = evaluate_g0(model, dql_run_live=True, proposal_text=proposal)
    print(json.dumps(g.to_dict(), indent=2))
    print(f"\narchetypes: {[(a.id, round(a.weight, 3), len(a.steps)) for a in archetypes]}  coverage={cov:.3f}")
    print(f"arrival CoV (interior) = {cov_arrival:.4f}  stages={[(s.duration, s.rate, s.shape) for s in stages]}")
    print(f"Little's Law: expected {llc.expectedConcurrency} ≈ observed {llc.observedConcurrency} -> ratio {llc.ratio}")
    print(f"wrote {OUT_DIR}/workload-model.json  and  scenario-proposal.md")
    return 0 if g.passed else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
