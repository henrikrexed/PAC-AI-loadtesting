#!/usr/bin/env python3
"""workload-model engine — the SCOPE-stage CLI.

Consumes a generic **extract.json** (the telemetry-derived facts of one target
application over one clean window) and emits the two SCOPE artifacts:

  * ``workload-model.json``  — the schema-valid workload model (``engine/schema.json``)
  * ``scenario-proposal.md`` — the human VALIDATE / Gate-V1 input

The engine is deterministic and **telemetry-agnostic** (methodology §2.1): the same
pipeline — behavioral archetypes -> arrival shaping -> Little's Law -> G0 gate -> emit —
runs for any application. What differs per app is only the *extract* (and the terminal
signal its archetypes were split on), never the engine.

The CLI self-validates the emitted model with the G0 machine gate and **exits non-zero
if G0 fails**, so it is safe to wire into CI (the release build smoke-tests exactly this).

Usage::

    workload-engine --extract extract.json --out OUT_DIR --mode {agentic,commerce}

``--mode`` names the behavioral taxonomy the extract's archetypes were split on (same
engine, different terminal signal — methodology §2.1):

  * ``agentic``  — an agent/LLM app split on a tool-use terminal signal (``execute_tool``):
                   *Agentic* (tool-using ReAct turn) vs *Conversational* (pure-LLM turn).
                   This is the mode the release smoke test exercises against
                   ``examples/crewai-deepseek-agent/extract.json``.
  * ``commerce`` — a storefront split on an order-terminal signal (payment/checkout):
                   *Buyer* (places an order) vs *Browser* (read-only).

In both modes every archetype the extract carries is emitted as its own journey; the mode
selects the proposal narration and is recorded for auditability. The **extract.json
contract** is documented in ``examples/crewai-deepseek-agent/README.md`` and
``docs/engine.md``; it is a superset-friendly document — unknown keys are ignored.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Make the sibling pipeline modules importable by bare name under every invocation
# mode: `python -m engine.cli`, `python engine/cli.py`, and the PyInstaller one-file
# bundle (which collects them as top-level hidden-imports). Keep this before the
# pipeline imports below.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import shaping as sh  # noqa: E402
from emit import build_model, render_proposal  # noqa: E402
from g0_gate import evaluate_g0  # noqa: E402

DEFAULT_CAPS = {"maxRps": 2, "maxVus": 20, "maxDuration": "30m"}

# Default archetype narration per mode, used when the extract does not name one.
MODE_TERMINAL = {
    "agentic": "tool-use terminal signal (`execute_tool`): Agentic (tool-using) vs Conversational (pure-LLM)",
    "commerce": "order-terminal signal (payment/checkout): Buyer (places an order) vs Browser (read-only)",
}


def _baseline(b: dict) -> dict:
    """Normalize a per-archetype baseline to the schema's p50/p95/p99/errorRate shape."""
    return {
        "p50Ms": b["p50Ms"],
        "p95Ms": b["p95Ms"],
        "p99Ms": b["p99Ms"],
        "errorRate": b.get("errorRate", 0.0),
    }


def _journey(a: dict) -> dict:
    """Build a schema-shaped journey from one extract archetype."""
    return {
        "id": a["id"],
        "description": a.get("description") or a.get("name", a["id"]),
        "weight": round(a["weight"], 4),
        "entrypoint": a["entrypoint"],
        "codeRef": a.get("codeRef"),
        "evidenceSource": a.get("evidenceSource", "span"),
        "steps": a["steps"],
        "baseline": _baseline(a["baseline"]),
    }


def build(extract: dict, mode: str) -> tuple[dict, str]:
    """Run the deterministic SCOPE pipeline; return (model, proposal_text)."""
    archetypes = extract.get("archetypes") or []
    if not archetypes:
        raise ValueError("extract.archetypes is empty — nothing to model")

    # --- behavioral journeys (methodology §3.1 step 3, gate G1) ---
    journeys = [_journey(a) for a in archetypes]
    coverage = extract.get("coverage", round(sum(a["weight"] for a in archetypes), 4))

    # --- arrival shaping (§3.1 step 5, gate G3) ---
    per_minute = extract.get("perMinuteCounts") or []
    if not per_minute:
        raise ValueError("extract.perMinuteCounts is required to shape the arrival profile")
    stages, _cov = sh.shape_ramp([float(c) for c in per_minute])

    # --- Little's Law (server span, never the load-driver wrapper) ---
    arr = extract["arrival"]
    llc = sh.littles_law(
        arr["arrivalRateTps"], arr["meanServerResponseMs"], arr["observedConcurrency"]
    )

    model = build_model(
        name=extract["name"],
        target_service=extract.get("targetService", extract["name"]),
        environment=extract["environment"],
        generated_at=extract.get("generatedAt", ""),
        timeframe=extract["timeframe"],
        timeframe_notes=extract.get("timeframeNotes", ""),
        queries=extract.get("queries", []),
        access_log_availability=extract.get("accessLogAvailability", "unknown"),
        sampling_ratio=extract.get("samplingRatio", 1.0),
        arrival_model=extract.get("arrivalModel", "open"),
        stages=[vars(s) for s in stages],
        littles_law=vars(llc),
        journeys=journeys,
        payloads=extract.get("payloads", {}),
        caps=extract.get("caps", DEFAULT_CAPS),
        coverage=coverage,
        session_id_coverage=extract.get("sessionIdCoverage"),
    )

    risks_extra = list(extract.get("risks", []))
    risks_extra.append(
        f"**Engine mode: `{mode}`.** Archetypes were split on the {MODE_TERMINAL.get(mode, mode)} "
        "and assembled by the telemetry-agnostic engine (`python -m engine.cli`); the identical "
        "pipeline models commerce, agentic, and chat workloads — only the extract differs "
        "(methodology §2.1)."
    )
    proposal = render_proposal(
        model,
        exclusions=extract.get("exclusions", "none within service scope"),
        target_env=extract.get(
            "targetEnv", "non-production allowlist (production forbidden without explicit approval)"
        ),
        abort_note=extract.get(
            "abortNote",
            "Set abort thresholds ABOVE the observed tail (p95/p99 of the heaviest journey) and errorRate abort at 5%.",
        ),
        risks_extra=risks_extra,
    )
    return model, proposal


def _run_init(sub_argv: list[str]) -> int:
    import driver  # noqa: E402  (stdlib-only sibling)

    ap = argparse.ArgumentParser(
        prog="workload-engine init",
        description="Install this repo's skills into a coding agent's skills directory and verify them.",
    )
    ap.add_argument("--dest", default=None,
                    help="skills destination (default ~/.claude/skills; see docs/skills-install.md)")
    ap.add_argument("--from", dest="from_dir", default=None,
                    help="source skills/ directory (default: auto-detect next to the engine)")
    return driver.cmd_init(ap.parse_args(sub_argv))


def _run_guided(sub_argv: list[str]) -> int:
    import driver  # noqa: E402

    ap = argparse.ArgumentParser(
        prog="workload-engine guided",
        description="Drive the engine through the gated 4-step flow: propose+confirm -> choose -> generate -> try.",
    )
    ap.add_argument("--extract", required=True, help="path to the extract.json telemetry facts")
    ap.add_argument("--out", required=True, help="output directory for the project artifacts")
    ap.add_argument("--mode", required=True, choices=("agentic", "commerce"),
                    help="behavioral taxonomy the extract's archetypes were split on")
    ap.add_argument("--renderers", default="k6",
                    help="comma-list of renderers: k6 (default), jmeter, locust, gatling")
    ap.add_argument("--yes", action="store_true",
                    help="confirm the V1 human gate non-interactively (CI / scripted)")
    ap.add_argument("--try", dest="try_run", action="store_true",
                    help="opt-in: run a few seconds of a real k6 smoke after generating")
    ap.add_argument("--by", default="operator (guided flow)", help="approval attribution")
    ap.add_argument("--at", default="", help="approval timestamp (ISO-8601); default now")
    args = ap.parse_args(sub_argv)
    if not args.at:
        from datetime import datetime, timezone
        args.at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return driver.run_guided(args, build)


def _force_utf8_io() -> None:
    """Make stdout/stderr UTF-8 regardless of the host console encoding.

    The engine prints and writes non-ASCII glyphs (``→ ≈ ✓ § — …``) that are not
    representable in the Windows ANSI code page (cp1252), so an un-pinned console
    would raise ``UnicodeEncodeError`` on a Windows runner — exactly what sank the
    release smoke. Every file write already pins ``encoding="utf-8"``; this pins
    the two standard streams to match (idempotent, no-op where already UTF-8)."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8")
            except (ValueError, OSError):
                pass


def main(argv: list[str] | None = None) -> int:
    _force_utf8_io()
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "init":
        return _run_init(argv[1:])
    if argv and argv[0] == "guided":
        return _run_guided(argv[1:])

    ap = argparse.ArgumentParser(
        prog="workload-engine",
        description="SCOPE-stage workload-model engine: extract.json -> workload-model.json + scenario-proposal.md (G0-gated). "
                    "Subcommands: `init` (install skills), `guided` (4-step driver).",
    )
    ap.add_argument("--extract", required=True, help="path to the extract.json telemetry facts")
    ap.add_argument("--out", required=True, help="output directory for the two artifacts")
    ap.add_argument(
        "--mode",
        required=True,
        choices=("agentic", "commerce"),
        help="behavioral taxonomy the extract's archetypes were split on",
    )
    args = ap.parse_args(argv)

    extract = json.loads(Path(args.extract).read_text(encoding="utf-8"))
    model, proposal = build(extract, args.mode)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "workload-model.json").write_text(json.dumps(model, indent=2) + "\n", encoding="utf-8")
    (out_dir / "scenario-proposal.md").write_text(proposal, encoding="utf-8")

    gate = evaluate_g0(
        model,
        dql_run_live=bool(extract.get("dqlRunLive", True)),
        proposal_text=proposal,
    )
    print(json.dumps(gate.to_dict(), indent=2))
    print(f"\nwrote {out_dir}/workload-model.json  and  scenario-proposal.md")
    if not gate.passed:
        print("\nG0 FAILED — see failing checks above.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
