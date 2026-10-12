"""run-report emission tests (§3.4.2, §5.1 — achieved-vs-target arrival, AC4)."""

import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
FIX = os.path.join(HERE, "..", "fixtures")

import report  # noqa: E402


def load(name):
    with open(os.path.join(FIX, name)) as fh:
        return json.load(fh)


class ReportTest(unittest.TestCase):
    def setUp(self):
        self.model = load("workload-model.sample.json")
        self.rc = load("run-config.sample.json")

    def test_target_rps_is_peak_stage(self):
        self.assertEqual(report.model_target_rps(self.model), 200)

    def test_achieved_vs_target(self):
        rpt = report.build_report(
            "20261009T120000Z", self.rc, self.model, "passed", None, None, 190.0, None
        )
        self.assertEqual(rpt["arrival"]["targetRps"], 200)
        self.assertEqual(rpt["arrival"]["achievedRps"], 190.0)
        self.assertAlmostEqual(rpt["arrival"]["achievedVsTarget"], 0.95)

    def test_write_run_dir_emits_artifacts(self):
        rpt = report.build_report(
            "20261009T120000Z", self.rc, self.model, "passed", {"gate": "V2b-smoke", "passed": True, "checks": []}, None, 190.0, None
        )
        with tempfile.TemporaryDirectory() as d:
            run_dir = os.path.join(d, "20261009T120000Z")
            paths = report.write_run_dir(run_dir, self.rc, rpt, smoke=rpt["gates"]["smoke"])
            for key in ("run-config.json", "run-report.json", "run-report.md", "smoke-result.json"):
                self.assertTrue(os.path.exists(paths[key]), key)
            with open(paths["run-report.md"]) as fh:
                md = fh.read()
            self.assertIn("Achieved vs target arrival", md)
            self.assertIn("95.00%", md)

    def test_aborted_report_records_cause(self):
        rpt = report.build_report(
            "ts", self.rc, self.model, "aborted", None, None, 50.0, "abort:p95MsGt p95=3000ms>2500ms"
        )
        self.assertEqual(rpt["verdict"], "aborted")
        self.assertIn("p95MsGt", rpt["abortReason"])


if __name__ == "__main__":
    unittest.main()
