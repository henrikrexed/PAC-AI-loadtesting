"""Shared CLI for the workload-model engine — the entry point the released binary and the
Docker image invoke.

    workload-engine --extract <extract.json> --out <dir> [--mode commerce|agentic]
    workload-engine --demo --out <dir>          # synthetic example, EXPLICIT opt-in

Input: a **neutral telemetry extract** (JSON) produced by a backend adapter (the dtctl/DQL
query pack in SKILL.md, or any other backend). Output: `<dir>/workload-model.json` +
`<dir>/scenario-proposal.md`, self-validated by the G0 gate. Exit 0 iff G0 passes.

Real-scan integrity (ISI-5928) — fail-closed contract:
  - `--extract` has NO default. Running without it and without `--demo` exits 2 with
    guidance (never a silent synthetic fallback).
  - `--demo` is the explicit opt-in for the bundled synthetic fixture; its output is
    stamped `provenance.kind = "demo-sample"` and refused by consumers unless they also
    opt in. If the extract carries its own provenance, that wins over `--demo`.
  - Real extracts record a `provenance` block (kind=extracted, tenant, window, queryPack,
    dqlRunLive) — produce it via `env_probe.py`, which prints the template. A model with
    no provenance fails G0.
  - `dql_run_live` for the G0 gate is derived from provenance, never hardcoded.

The engine is backend- and tool-agnostic: it never talks to Dynatrace or to a load tool. It
turns neutral facts into a workload model and gates it. The behavioral split is the same
engine across domains — commerce (Buyer / Browser, split on the order-terminal service) and
agentic apps (Agentic / Conversational, split on the `execute_tool` tool-use signal); see
`archetypes.classify_by_terminal`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import shaping as sh                                            # noqa: E402
from archetypes import AGENTIC_TOOL_PATTERNS, classify_by_terminal  # noqa: E402
from build_example import build_commerce                       # noqa: E402
from clustering import Journey                                 # noqa: E402
from emit import build_model, make_demo_provenance, render_proposal  # noqa: E402
from g0_gate import evaluate_g0                                # noqa: E402


FAIL_CLOSED_MSG = (
    "no telemetry extract provided. The engine is fail-closed (ISI-5928): it will NOT\n"
    "silently fall back to the bundled synthetic example.\n"
    "  - Real run:   run scripts/env_probe.py --context <ctx> [--service <svc>], run the\n"
    "                SKILL.md DQL pack, record the probe's provenanceTemplate into your\n"
    "                extract JSON, then: workload-engine --extract <extract.json> --out <dir>\n"
    "  - Demo run:   workload-engine --demo --out <dir>\n"
    "                (output stamped provenance.kind=demo-sample; consumers refuse it\n"
    "                 unless explicitly opted in with --demo / WORKLOAD_MODEL_ALLOW_DEMO=1)"
)


def _default_fixture() -> Path:
    """Bundled synthetic commerce fixture. Works both from source (`fixtures/`) and inside a
    PyInstaller one-file binary (data files are unpacked to `sys._MEIPASS`)."""
    for cand in (Path(getattr(sys, "_MEIPASS", HERE)) / "example_extract.json",
                 HERE.parent / "fixtures" / "example_extract.json"):
        if cand.exists():
            return cand
    return HERE.parent / "fixtures" / "example_extract.json"


def _bl(d: dict) -> dict:
    return {"p50Ms": d["p50_ms"], "p95Ms": d["p95_ms"], "p99Ms": d["p99_ms"],
            "errorRate": d.get("errorRate", 0.0)}


def _build_agentic(fx: dict):
    """Agentic (Agentic / Conversational) SCOPE assembly from a neutral agentic extract.

    Expected `fx` keys: `service`, `environment`, `timeframe`, `front_end.resolved_op`,
    `code_refs{entry_handler,llm_call}`, `archetype_split{conversational_weight,
    agentic_weight,conversational_traces,agentic_traces,coverage,tools_observed}`,
    `turn_baseline_agent_turn{conversational,agentic}` (each p50_ms/p95_ms/p99_ms),
    `span_trees{conversational,agentic}`, `per_minute_cov.interior_counts`,
    `arrival{arrival_rate_tps,mean_server_response_ms,observed_concurrency}`,
    `access_log_availability`, `sampling_ratio`. Returns (model, proposal, coverage).
    """
    split = fx["archetype_split"]
    bl = fx["turn_baseline_agent_turn"]
    cr = fx.get("code_refs", {})
    entry_op = fx["front_end"]["resolved_op"]

    def journey(aid, name, weight, baseline, flow, payload_ref):
        return {
            "id": aid, "description": f"{name}. Reconstructed flow: {flow}",
            "weight": round(weight, 4), "entrypoint": entry_op,
            "codeRef": cr.get("entry_handler"), "evidenceSource": "span",
            "steps": [
                {"id": "s1", "service": fx["service"], "operation": "POST /request",
                 "callType": "http", "codeRef": cr.get("entry_handler"),
                 "evidenceSource": "span", "payloadRef": payload_ref},
                {"id": "s2", "service": fx["service"], "operation": "llm.call",
                 "callType": "http", "codeRef": cr.get("llm_call"), "evidenceSource": "span"},
            ],
            "baseline": _bl(baseline),
        }

    journeys = [
        journey("conversational", "Conversational — pure-LLM turn (no tool)",
                split["conversational_weight"], bl["conversational"],
                fx["span_trees"]["conversational"], "prompt_chat"),
        journey("agentic", "Agentic — tool-using ReAct turn (reaches execute_tool)",
                split["agentic_weight"], bl["agentic"],
                fx["span_trees"]["agentic"], "prompt_agentic"),
    ]
    # Prove the split is structural (not hardcoded): classify the member ops by tool-use.
    _demo = classify_by_terminal(
        [Journey(op="agentic.turn", traces=split["agentic_traces"],
                 svc_set={fx["service"], "execute_tool"}),
         Journey(op="chat.turn", traces=split["conversational_traces"], svc_set={fx["service"]})],
        patterns=AGENTIC_TOOL_PATTERNS,
        present=("agentic", "Agentic"), absent=("conversational", "Conversational"))
    assert {a.id for a in _demo} == {"agentic", "conversational"}

    stages, _cov = sh.shape_ramp(fx["per_minute_cov"]["interior_counts"])
    arr = fx["arrival"]
    llc = sh.littles_law(arr["arrival_rate_tps"], arr["mean_server_response_ms"],
                         arr["observed_concurrency"])

    model = build_model(
        name=fx["service"], target_service=fx["service"], environment=fx["environment"],
        generated_at=fx.get("generated_at", "1970-01-01T00:00:00Z"),
        timeframe=fx["timeframe"], timeframe_notes="agentic app; terminal signal = execute_tool",
        queries=["see the agentic query pack — adapter ran these live"],
        access_log_availability=fx["access_log_availability"],
        sampling_ratio=fx["sampling_ratio"], arrival_model="open",
        stages=[vars(s) for s in stages], littles_law=vars(llc),
        journeys=journeys,
        payloads={
            "prompt_agentic": {"fields": [{"name": "task", "type": "string",
                "generator": "const", "values": ["use a tool to answer"], "distribution": "uniform"}], "seed": 42},
            "prompt_chat": {"fields": [{"name": "task", "type": "string",
                "generator": "const", "values": ["answer from knowledge"], "distribution": "uniform"}], "seed": 42},
        },
        caps={"maxRps": 2, "maxVus": 20, "maxDuration": "30m"},
        coverage=split["coverage"],
        provenance=fx.get("provenance"),
    )
    proposal = render_proposal(
        model, exclusions="none within service scope",
        target_env=fx.get("deployment_environment", "non-production"),
        abort_note="abort above the agentic tail (tool turns run heavier than chat turns)",
        risks_extra=[f"Tools observed: {split.get('tools_observed')}.",
                     "Behavioral split via archetypes.classify_by_terminal "
                     "(terminal signal = execute_tool) — same engine as commerce (order-terminal)."],
    )
    return model, proposal, split["coverage"]


def run(extract: dict, out_dir: Path, mode: str) -> int:
    if mode == "commerce":
        model, proposal, _arch, _cov = build_commerce(extract)
    else:
        model, proposal, _cov = _build_agentic(extract)

    out_dir.mkdir(parents=True, exist_ok=True)
    # Pin UTF-8: the proposal contains non-ASCII (e.g. the `≈` sign); the platform default
    # is cp1252 on Windows, which would raise UnicodeEncodeError.
    (out_dir / "workload-model.json").write_text(json.dumps(model, indent=2) + "\n", encoding="utf-8")
    (out_dir / "scenario-proposal.md").write_text(proposal, encoding="utf-8")

    # dql_run_live is derived from the model's own provenance (ISI-5928), never hardcoded:
    # extracted models attest live DQL via provenance.dqlRunLive; demo-sample models make
    # no live claim (the gate records n/a, not a silent pass).
    prov = model.get("metadata", {}).get("source", {}).get("provenance") or {}
    live = prov.get("kind") == "extracted" and bool(prov.get("dqlRunLive"))
    g = evaluate_g0(model, dql_run_live=live, proposal_text=proposal)
    print(json.dumps(g.to_dict(), indent=2))
    print(f"\nG0 {'PASS' if g.passed else 'FAIL'} ({sum(c.passed for c in g.checks)}/{len(g.checks)})"
          f"  -> {out_dir}/workload-model.json")
    return 0 if g.passed else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="workload-engine", description="workload-model engine CLI (SCOPE)")
    ap.add_argument("--extract", type=Path, default=None,
                    help="neutral telemetry extract JSON (REQUIRED unless --demo)")
    ap.add_argument("--out", required=True, type=Path, help="output directory")
    ap.add_argument("--mode", default="commerce", choices=["commerce", "agentic"],
                    help="behavioral split: commerce (Buyer/Browser) or agentic (Agentic/Conversational)")
    ap.add_argument("--demo", action="store_true",
                    help="explicit opt-in: use the bundled synthetic fixture when no --extract "
                         "is given, and stamp the output provenance.kind=demo-sample if the "
                         "extract carries no provenance of its own")
    a = ap.parse_args(argv)

    if a.extract is None:
        if not a.demo:
            print(f"workload-engine: {FAIL_CLOSED_MSG}", file=sys.stderr)
            return 2
        extract_path = _default_fixture()
    else:
        extract_path = a.extract

    extract = json.loads(extract_path.read_text(encoding="utf-8"))
    # Provenance precedence (ISI-5928): the extract's own provenance wins; --demo stamps a
    # demo-sample only when the caller provided none (e.g. the bundled synthetic fixture).
    if extract.get("provenance") is None and a.demo:
        extract["provenance"] = make_demo_provenance(
            "bundled synthetic fixture / examples data (--demo explicit opt-in); "
            "not extracted from any tenant"
        )

    return run(extract, a.out, a.mode)


if __name__ == "__main__":
    raise SystemExit(main())
