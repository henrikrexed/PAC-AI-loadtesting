"""run-report emission for the EXECUTE stage (methodology §3.4.2, §5.1 layout).

Produces the ``runs/<UTC-timestamp>/`` artifact set that feeds ANALYZE (baseline-diff):

    runs/<ts>/
      run-config.json     <- the exact scope contract used (§5.3)
      smoke-result.json   <- V2b-smoke gate breakdown (6 criteria)
      run-report.md       <- human-readable run metadata + achieved-vs-target + verdict
      run-report.json     <- machine-readable twin of the report

``target_rps`` is derived from the approved model's arrival profile (peak stage rate);
``achieved_rps`` is what the full run actually drove. The achieved-vs-target table is
the §3.4 AC4 deliverable.
"""

from __future__ import annotations

import json
import os
from typing import Any, Optional


def model_target_rps(model: dict[str, Any]) -> float:
    """Peak target arrival from the approved model (max stage rate), scaled to 1.0."""
    stages = model.get("spec", {}).get("arrivalProfile", {}).get("stages", [])
    rates = [float(s.get("rate", 0.0)) for s in stages]
    return max(rates) if rates else 0.0


def build_report(
    run_id: str,
    run_config: dict[str, Any],
    model: dict[str, Any],
    verdict: str,
    smoke: Optional[dict[str, Any]],
    preflight: Optional[dict[str, Any]],
    achieved_rps: Optional[float],
    abort_reason: Optional[str],
    samples: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    target = model_target_rps(model)
    achieved = achieved_rps if achieved_rps is not None else 0.0
    ratio = (achieved / target) if target else None
    return {
        "run": run_id,
        "verdict": verdict,  # passed | smoke_failed | preflight_failed | aborted
        "modelRef": run_config.get("modelRef"),
        "target": run_config.get("target"),
        "caps": run_config.get("caps"),
        "abort": run_config.get("abort"),
        "arrival": {
            "targetRps": target,
            "achievedRps": achieved,
            "achievedVsTarget": ratio,
        },
        "abortReason": abort_reason,
        "gates": {"smoke": smoke, "preflight": preflight},
        "sampleCount": len(samples) if samples else 0,
        "telemetry": run_config.get("telemetry"),
    }


def _md(report: dict[str, Any]) -> str:
    a = report["arrival"]
    ratio = a["achievedVsTarget"]
    ratio_s = f"{ratio:.2%}" if ratio is not None else "n/a"
    lines = [
        f"# Load-test run report: {report['run']}",
        "",
        f"**Verdict:** `{report['verdict']}`",
        "",
        "## Scope contract",
        f"- Model: `{report['modelRef']}`",
        f"- Target: `{report['target']}`",
        f"- Caps: `{report['caps']}`",
        f"- Abort thresholds: `{report['abort']}`",
        "",
        "## Achieved vs target arrival",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Target RPS (model peak) | {a['targetRps']:.2f} |",
        f"| Achieved RPS | {a['achievedRps']:.2f} |",
        f"| Achieved / target | {ratio_s} |",
        "",
    ]
    if report.get("abortReason"):
        lines += ["## Abort cause", "", f"`{report['abortReason']}`", ""]
    for gate_name in ("smoke", "preflight"):
        g = report["gates"].get(gate_name)
        if not g:
            continue
        lines += [
            f"## {g['gate']} gate — {'PASS' if g['passed'] else 'FAIL'}",
            "",
            "| Criterion | Result | Detail |",
            "|---|---|---|",
        ]
        for c in g["checks"]:
            lines.append(
                f"| `{c['id']}` | {'✅' if c['passed'] else '❌'} | {c['detail']} |"
            )
        lines.append("")
    lines += [
        "## Telemetry coordinates (for ANALYZE / baseline-diff)",
        "",
        f"`{report.get('telemetry')}`",
        "",
    ]
    return "\n".join(lines)


def write_run_dir(
    run_dir: str,
    run_config: dict[str, Any],
    report: dict[str, Any],
    smoke: Optional[dict[str, Any]] = None,
) -> dict[str, str]:
    """Write the full artifact set into ``run_dir`` (created if absent). Returns paths."""
    os.makedirs(run_dir, exist_ok=True)
    paths = {}

    cfg_path = os.path.join(run_dir, "run-config.json")
    with open(cfg_path, "w") as fh:
        json.dump(run_config, fh, indent=2, sort_keys=True)
    paths["run-config.json"] = cfg_path

    if smoke is not None:
        sp = os.path.join(run_dir, "smoke-result.json")
        with open(sp, "w") as fh:
            json.dump(smoke, fh, indent=2, sort_keys=True)
        paths["smoke-result.json"] = sp

    jp = os.path.join(run_dir, "run-report.json")
    with open(jp, "w") as fh:
        json.dump(report, fh, indent=2, sort_keys=True)
    paths["run-report.json"] = jp

    mp = os.path.join(run_dir, "run-report.md")
    with open(mp, "w") as fh:
        fh.write(_md(report))
    paths["run-report.md"] = mp

    return paths
