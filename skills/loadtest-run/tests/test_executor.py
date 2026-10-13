"""End-to-end EXECUTE orchestration tests — maps 1:1 to the 4 issue acceptance criteria.

AC1: refuses the full run until the smoke test passes all 6 §3.4.1 criteria.
AC2: enforces caps/abort — a run exceeding thresholds is aborted and torn down cleanly.
AC3: smoke confirms synthetic spans arrive in the backend before the full run.
AC4: produces a runs/<ts>/ report with achieved-vs-target arrival numbers.
"""

import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
FIX = os.path.join(HERE, "..", "fixtures")

import loadtest_run  # noqa: E402
from supervisor import Sample  # noqa: E402


def load(name):
    with open(os.path.join(FIX, name)) as fh:
        return json.load(fh)


def passing_smoke_metrics(synthetic=42):
    return {
        "http_5xx_count": 0,
        "http_404_count": 0,
        "steps_missing_downstream_span": 0,
        "null_extract_failures": 0,
        "dropped_iterations": 0,
        "synthetic_span_count": synthetic,
        "journey_counts": {"browse": 160, "checkout": 40},
        "error_counts_per_journey": {
            "browse": {"errors": 0, "total": 160},
            "checkout": {"errors": 0, "total": 40},
        },
    }


class FakeRunner:
    """Injectable runner so orchestration is deterministic without k6/cluster."""

    def __init__(self, smoke_metrics, full_samples, achieved_rps):
        self.smoke_metrics = smoke_metrics
        self.full_samples = full_samples
        self.achieved_rps = achieved_rps
        self.full_ran = False

    def run_smoke(self, run_config, model, run_dir):
        return self.smoke_metrics

    def run_full(self, run_config, model, run_dir, supervisor):
        self.full_ran = True
        emitted = []
        for s in self.full_samples:
            emitted.append(s)
            if supervisor.observe(s) == "abort":
                break
        return loadtest_run.FullResult(self.achieved_rps, emitted)


class ExecutorTest(unittest.TestCase):
    def setUp(self):
        self.model = load("workload-model.sample.json")
        self.rc = load("run-config.sample.json")
        self.commit = "abc123"
        self.v2a = {"passed": True, "commit": "abc123"}

    def _execute(self, runner, run_id="20261009T120000Z", root=None):
        return loadtest_run.execute(
            self.rc, self.model, runner,
            runs_root=root, run_id=run_id,
            v2a=self.v2a, current_commit=self.commit,
        )

    def test_ac1_full_run_refused_until_smoke_passes(self):
        # Smoke fails criterion 6 (dropped iterations) -> full run must NOT execute.
        m = passing_smoke_metrics()
        m["dropped_iterations"] = 5
        runner = FakeRunner(m, [ok_sample()], 190.0)
        with tempfile.TemporaryDirectory() as d:
            outcome = self._execute(runner, root=d)
        self.assertEqual(outcome.verdict, "smoke_failed")
        self.assertFalse(runner.full_ran, "full run executed despite failing smoke gate")

    def test_ac1_happy_path_runs_full(self):
        runner = FakeRunner(passing_smoke_metrics(), [ok_sample()], 190.0)
        with tempfile.TemporaryDirectory() as d:
            outcome = self._execute(runner, root=d)
        self.assertEqual(outcome.verdict, "passed")
        self.assertTrue(runner.full_ran)

    def test_ac2_abort_and_teardown_on_cap_breach(self):
        samples = [ok_sample(), ok_sample(rps=9999), ok_sample()]  # 2nd breaches maxRps
        runner = FakeRunner(passing_smoke_metrics(), samples, 500.0)
        with tempfile.TemporaryDirectory() as d:
            outcome = self._execute(runner, root=d)
            self.assertEqual(outcome.verdict, "aborted")
            self.assertIn("cap:maxRps", outcome.report["abortReason"])
            # Teardown recorded cleanly in the run dir.
            abort_log = os.path.join(outcome.run_dir, "abort.log")
            self.assertTrue(os.path.exists(abort_log))
            with open(abort_log) as fh:
                self.assertIn("cap:maxRps", fh.read())

    def test_ac2_abort_on_threshold_breach(self):
        samples = [ok_sample(p95_ms=3000)]  # breaches p95MsGt=2500
        runner = FakeRunner(passing_smoke_metrics(), samples, 100.0)
        with tempfile.TemporaryDirectory() as d:
            outcome = self._execute(runner, root=d)
        self.assertEqual(outcome.verdict, "aborted")
        self.assertIn("abort:p95MsGt", outcome.report["abortReason"])

    def test_ac3_no_synthetic_span_blocks_full_run(self):
        # Criterion 5: zero synthetic spans -> smoke fails -> full run refused.
        runner = FakeRunner(passing_smoke_metrics(synthetic=0), [ok_sample()], 190.0)
        with tempfile.TemporaryDirectory() as d:
            outcome = self._execute(runner, root=d)
        self.assertEqual(outcome.verdict, "smoke_failed")
        self.assertFalse(runner.full_ran)
        crit5 = [c for c in outcome.smoke["checks"] if c["id"] == "5-synthetic-visible"][0]
        self.assertFalse(crit5["passed"])

    def test_ac4_run_dir_has_achieved_vs_target(self):
        runner = FakeRunner(passing_smoke_metrics(), [ok_sample()], 190.0)
        with tempfile.TemporaryDirectory() as d:
            outcome = self._execute(runner, root=d)
            report_json = os.path.join(outcome.run_dir, "run-report.json")
            self.assertTrue(os.path.exists(report_json))
            with open(report_json) as fh:
                rpt = json.load(fh)
            self.assertEqual(rpt["arrival"]["targetRps"], 200)
            self.assertEqual(rpt["arrival"]["achievedRps"], 190.0)
            self.assertAlmostEqual(rpt["arrival"]["achievedVsTarget"], 0.95)
            self.assertTrue(os.path.exists(os.path.join(outcome.run_dir, "run-report.md")))

    def test_preflight_failure_blocks_full_run(self):
        # Valid smoke, but model unapproved -> preflight fails -> no full run.
        self.model["status"]["approval"]["decision"] = "adjusted"
        runner = FakeRunner(passing_smoke_metrics(), [ok_sample()], 190.0)
        with tempfile.TemporaryDirectory() as d:
            outcome = self._execute(runner, root=d)
        self.assertEqual(outcome.verdict, "preflight_failed")
        self.assertFalse(runner.full_ran)


def ok_sample(**kw):
    base = dict(elapsed_s=10, rps=100, vus=50, error_rate=0.0, p95_ms=200, p99_ms=400)
    base.update(kw)
    return Sample(**base)


if __name__ == "__main__":
    unittest.main()
