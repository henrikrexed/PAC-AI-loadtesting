#!/usr/bin/env python3
"""loadtest-run — the EXECUTE stage of the AI-driven load-testing loop (methodology §3.4).

Orchestration contract (strictly ordered, fail-closed):

    1. create runs/<UTC-ts>/ and pin the run-config there
    2. SMOKE   — run the small confirmation test (§3.4.1), evaluate the V2b-smoke gate
    3. refuse  — if any of the 6 smoke criteria fail, STOP (no full run) and report
    4. PREFLIGHT — evaluate the V2b gate (§3.4.2): allowlist, approval, caps, smoke
    5. refuse  — if pre-flight fails, STOP and report
    6. FULL    — run the full test under the caps/abort Supervisor (§7)
    7. report  — emit achieved-vs-target arrival + verdict into runs/<ts>/

The k6 runner and the Dynatrace synthetic-span probe are injected (``Runner`` /
``probe``) so the orchestration is deterministic and unit-testable without a cluster
or k6 installed. ``K6Runner`` / ``dtctl_synthetic_probe`` are the real adapters.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Protocol

try:  # support both "run as script" and "import as module"
    from . import gates, report
    from .supervisor import Sample, Supervisor
except ImportError:  # pragma: no cover - exercised via CLI
    import gates  # type: ignore
    import report  # type: ignore
    from supervisor import Sample, Supervisor  # type: ignore


@dataclass
class FullResult:
    achieved_rps: float
    samples: list[Sample] = field(default_factory=list)


class Runner(Protocol):
    def run_smoke(self, run_config: dict, model: dict, run_dir: str) -> dict:
        """Run the §3.4.1 confirmation test; return merged smoke metrics (see gates.evaluate_smoke)."""

    def run_full(
        self, run_config: dict, model: dict, run_dir: str, supervisor: Supervisor
    ) -> FullResult:
        """Run the full test, feeding each sample to ``supervisor.observe`` until done/aborted."""


@dataclass
class ExecuteOutcome:
    verdict: str  # passed | smoke_failed | preflight_failed | aborted
    run_dir: str
    report: dict
    smoke: Optional[dict]
    preflight: Optional[dict]
    paths: dict[str, str]


def execute(
    run_config: dict[str, Any],
    model: dict[str, Any],
    runner: Runner,
    *,
    runs_root: str,
    run_id: str,
    v2a: dict[str, Any],
    current_commit: str,
) -> ExecuteOutcome:
    import os

    run_dir = os.path.join(runs_root, run_id)
    os.makedirs(run_dir, exist_ok=True)

    # ---- 2/3. SMOKE + V2b-smoke gate -------------------------------------------------
    smoke_metrics = runner.run_smoke(run_config, model, run_dir)
    smoke_gate = gates.evaluate_smoke(smoke_metrics, model)
    smoke_dict = smoke_gate.to_dict()

    if not smoke_gate.passed:
        rpt = report.build_report(
            run_id, run_config, model, "smoke_failed", smoke_dict, None, None, None
        )
        paths = report.write_run_dir(run_dir, run_config, rpt, smoke_dict)
        return ExecuteOutcome("smoke_failed", run_dir, rpt, smoke_dict, None, paths)

    # ---- 4/5. V2b pre-flight gate ----------------------------------------------------
    pre = gates.preflight_v2b(
        run_config, model, smoke_gate, v2a, current_commit, run_dir_exists=True
    )
    pre_dict = pre.to_dict()
    if not pre.passed:
        rpt = report.build_report(
            run_id, run_config, model, "preflight_failed", smoke_dict, pre_dict, None, None
        )
        paths = report.write_run_dir(run_dir, run_config, rpt, smoke_dict)
        return ExecuteOutcome("preflight_failed", run_dir, rpt, smoke_dict, pre_dict, paths)

    # ---- 6. FULL run under the caps/abort supervisor ---------------------------------
    supervisor = Supervisor(
        caps=run_config.get("caps", {}),
        abort=run_config.get("abort", {}),
        teardown=_make_teardown(run_dir),
    )
    full = runner.run_full(run_config, model, run_dir, supervisor)

    verdict = "aborted" if supervisor.aborted else "passed"
    rpt = report.build_report(
        run_id,
        run_config,
        model,
        verdict,
        smoke_dict,
        pre_dict,
        full.achieved_rps,
        supervisor.abort_reason,
        samples=[s.__dict__ for s in full.samples],
    )
    paths = report.write_run_dir(run_dir, run_config, rpt, smoke_dict)
    return ExecuteOutcome(verdict, run_dir, rpt, smoke_dict, pre_dict, paths)


def _make_teardown(run_dir: str) -> Callable[[str], None]:
    import os

    def _teardown(reason: str) -> None:
        # Safe teardown (§7.5): record the abort cause; the real adapter also deletes
        # the scoped k6 Job / kills the local process group.
        with open(os.path.join(run_dir, "abort.log"), "a") as fh:
            fh.write(f"ABORT {reason}\n")

    return _teardown


# --------------------------------------------------------------------------------------
# Real adapters (used outside tests; require k6 + dtctl in the environment).
# --------------------------------------------------------------------------------------

def dtctl_synthetic_probe(run_config: dict, dtctl: str = "dtctl") -> int:
    """Count ``synthetic == true`` spans in the backend (smoke criterion 5, §3.4.1).

    Proves baggage->attribute promotion (P4/§7.7) is live before the full run.
    """
    tf = run_config.get("telemetry", {}).get("timeframe", "-15m")
    dql = (
        f"fetch spans, from: {tf} | filter synthetic == true | summarize c = count()"
    )
    out = subprocess.run(
        [dtctl, "query", dql, "-o", "json"], capture_output=True, text=True, check=True
    )
    rows = json.loads(out.stdout or "[]")
    if isinstance(rows, dict):
        rows = rows.get("records", rows.get("result", []))
    return int(rows[0].get("c", 0)) if rows else 0


class K6Runner:
    """Real k6 adapter. Requires k6 (with xk6-output-opentelemetry) on PATH.

    Not exercised by the offline unit tests (k6 absent). Present so the skill runs
    end-to-end once k6 is provisioned.
    """

    def __init__(self, k6: str = "k6", dtctl: str = "dtctl"):
        self.k6 = k6
        self.dtctl = dtctl

    def _invoke(self, script: str, run_dir: str, extra: list[str]) -> dict:
        import os

        summary = os.path.join(run_dir, "k6-summary.json")
        cmd = [self.k6, "run", "--summary-export", summary, *extra, script]
        subprocess.run(cmd, check=False)
        with open(summary) as fh:
            return json.load(fh)

    def run_smoke(self, run_config: dict, model: dict, run_dir: str) -> dict:  # pragma: no cover
        raise NotImplementedError(
            "K6Runner.run_smoke: wire k6 smoke invocation + dtctl_synthetic_probe once "
            "k6 is provisioned (S0). Must return gates.evaluate_smoke's expected keys."
        )

    def run_full(self, run_config, model, run_dir, supervisor):  # pragma: no cover
        raise NotImplementedError(
            "K6Runner.run_full: stream k6 metrics into supervisor.observe(Sample(...))."
        )


def _git_commit() -> str:
    try:
        return (
            subprocess.run(
                ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
            ).stdout.strip()
        )
    except Exception:  # pragma: no cover
        return "unknown"


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="loadtest-run EXECUTE stage")
    ap.add_argument("--run-config", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--runs-root", required=True, help="e.g. loadtests/<target>/runs")
    ap.add_argument("--run-id", required=True, help="UTC timestamp directory name")
    ap.add_argument("--v2a-passed", action="store_true")
    ap.add_argument("--v2a-commit", default=None)
    args = ap.parse_args(argv)

    with open(args.run_config) as fh:
        rc = json.load(fh)
    with open(args.model) as fh:
        model = json.load(fh)

    commit = _git_commit()
    outcome = execute(
        rc,
        model,
        K6Runner(),
        runs_root=args.runs_root,
        run_id=args.run_id,
        v2a={"passed": args.v2a_passed, "commit": args.v2a_commit or commit},
        current_commit=commit,
    )
    print(json.dumps({"verdict": outcome.verdict, "runDir": outcome.run_dir}, indent=2))
    return 0 if outcome.verdict == "passed" else 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
