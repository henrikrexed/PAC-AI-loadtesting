#!/usr/bin/env python3
"""ANALYZE-stage orchestrator (methodology §3.5, gate V3).

Reads a ``diff-input.json`` — the measurements the agent extracts from the
synthetic-filtered DQL pack (``dql/diff.dql``) and the R5 infra cross-check
(``dql/r5-infra-crosscheck.dql``) — runs the pure :mod:`diff` engine, validates
the result against ``schema/shape-diff.schema.json``, and writes
``runs/<ts>/shape-diff.json`` plus, when the decision is ``escalate``, an
``escalation-report.md``.

The split is deliberate: all non-determinism (DQL extraction) happens upstream in
dtctl and is captured verbatim in ``diff-input.json``; everything this script does
is a deterministic, reviewable function of that file — observability as code.

Usage:
    build_shape_diff.py --input runs/<ts>/diff-input.json [--out runs/<ts>/shape-diff.json]
                        [--report runs/<ts>/escalation-report.md] [--no-validate]

Exit codes: 0 accept · 10 iterate · 20 escalate · 2 bad input / schema failure.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import diff  # noqa: E402  (local module, path injected above)

_EXIT = {"accept": 0, "iterate": 10, "escalate": 20}


def build(inp: dict) -> dict:
    """Assemble a schema-shaped shape-diff dict from a diff-input dict."""
    tol = {**diff.DEFAULT_TOLERANCES, **(inp.get("tolerances") or {})}
    scaling = float(inp["scalingFactor"])
    sampling = inp["samplingFactor"]
    max_iter = int(inp.get("maxIterations", diff.MAX_ITERATIONS_DEFAULT))
    iteration = int(inp.get("iterationIndex", 1))
    require_r5 = bool(inp.get("requireR5", True))

    dims: list[diff.Dimension] = [
        diff.eval_arrival_shape(inp["arrivalShape"], scaling, sampling, tol),
        diff.eval_latency(inp["latency"], tol),
        diff.eval_service_fanout(inp["serviceFanout"], scaling, sampling, tol),
        diff.eval_error_rate(inp["errorRate"], tol),
        diff.eval_journey_mix(inp["journeyMix"], tol),
    ]
    if inp.get("cacheHitRatio"):
        dims.append(diff.eval_cache_hit_ratio(inp["cacheHitRatio"], tol))

    crosscheck = diff.eval_r5_crosscheck(inp.get("r5CrossCheck"))
    decision = diff.classify(dims, crosscheck, iteration, max_iter, require_r5)
    drift = diff.governance_tolerance_drift(tol)

    caveats: list[str] = list(inp.get("caveats", []))
    probe = int(inp.get("syntheticProbeCount", 0))
    if probe <= 0:
        caveats.append("syntheticProbeCount == 0 — baggage→attribute promotion likely "
                       "missing; the synthetic filter matches nothing and the diff is "
                       "meaningless (§3.5 prereq 1).")
    if not crosscheck.available:
        caveats.append(crosscheck.detail.get("reason", "R5 infra cross-check unavailable."))
    if drift:
        caveats.append(f"R8 governance: {len(drift)} tolerance(s) loosened vs §3.5 defaults "
                       "— verify the gate was not weakened to force a pass.")

    out = {
        "run": inp["run"],
        "baselineTimeframe": inp["baselineTimeframe"],
        "scalingFactor": scaling,
        "samplingFactor": sampling,
        "syntheticProbeCount": probe,
        "dimensions": {d.name: d.to_dict() for d in dims},
        "r5CrossCheck": crosscheck.to_dict(),
        "decision": decision.decision,
        "iteration": decision.iteration,
        "failedDimensions": decision.failed_dimensions,
        "classifications": decision.classifications,
        "reason": decision.reason,
    }
    if inp.get("runTimeframe"):
        out["runTimeframe"] = inp["runTimeframe"]
    if drift:
        out["governance"] = {"toleranceDrift": drift}
    if caveats:
        out["caveats"] = caveats
    return out


def validate(doc: dict) -> None:
    schema_path = Path(__file__).resolve().parent.parent / "schema" / "shape-diff.schema.json"
    try:
        import jsonschema
    except ImportError:
        print("WARNING: jsonschema not installed; skipping schema validation", file=sys.stderr)
        return
    schema = json.loads(schema_path.read_text())
    jsonschema.validate(doc, schema)


def escalation_report(doc: dict) -> str:
    lines = [
        f"# Escalation report — run {doc['run']}",
        "",
        f"**Decision:** `{doc['decision']}` (iteration {doc['iteration']})",
        f"**Reason:** {doc.get('reason', '')}",
        "",
        f"Baseline window: `{doc['baselineTimeframe']}` · scalingFactor "
        f"`{doc['scalingFactor']}` · sampling prod `{doc['samplingFactor']['prod']}` / "
        f"test `{doc['samplingFactor']['test']}`",
        "",
        "## Dimension verdicts",
        "",
        "| Dimension | Pass | Key metric |",
        "|---|---|---|",
    ]
    for name, d in doc["dimensions"].items():
        metric = {k: v for k, v in d.items() if k not in ("pass", "perJourney", "perEndpoint",
                  "tolerances", "missingEdges", "outOfBandEdges")}
        lines.append(f"| {name} | {'✅' if d['pass'] else '❌'} | {json.dumps(metric)} |")
    cc = doc["r5CrossCheck"]
    lines += [
        "",
        "## R5 infra cross-check (non-telemetry ground truth)",
        "",
        f"- available: **{cc['available']}** · pass: **{cc['pass']}**",
        f"- {cc.get('reason', '')}",
    ]
    if cc.get("metric"):
        lines.append(f"- metric `{cc['metric']}` ({cc.get('plane', '')}) on workload "
                     f"`{cc.get('workload')}`: idle {cc.get('idleBaseline')} → run "
                     f"{cc.get('duringRun')} (×{cc.get('riseRatio')})")
    if doc.get("classifications"):
        lines += ["", "## Miss classification", ""]
        for c in doc["classifications"]:
            kind = "STRUCTURAL → VALIDATE" if c["structural"] else "parameter-only"
            lines.append(f"- **{c['dimension']}** ({c['classification']}, {kind}): "
                         f"{c['suggestedAction']}")
    if doc.get("caveats"):
        lines += ["", "## Caveats", ""] + [f"- {c}" for c in doc["caveats"]]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build shape-diff.json from diff-input.json")
    ap.add_argument("--input", required=True, type=Path)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--report", type=Path, default=None)
    ap.add_argument("--no-validate", action="store_true")
    args = ap.parse_args(argv)

    inp = json.loads(args.input.read_text())
    doc = build(inp)

    if not args.no_validate:
        try:
            validate(doc)
        except Exception as e:  # jsonschema.ValidationError or file issues
            print(f"SCHEMA VALIDATION FAILED: {e}", file=sys.stderr)
            return 2

    out_path = args.out or args.input.parent / "shape-diff.json"
    out_path.write_text(json.dumps(doc, indent=2) + "\n")
    print(json.dumps(doc, indent=2))
    print(f"\nwrote {out_path}", file=sys.stderr)

    if doc["decision"] == "escalate":
        report_path = args.report or args.input.parent / "escalation-report.md"
        report_path.write_text(escalation_report(doc))
        print(f"wrote {report_path}", file=sys.stderr)

    return _EXIT.get(doc["decision"], 2)


if __name__ == "__main__":
    raise SystemExit(main())
