"""V2b-smoke (§3.4.1 six criteria) and V2b pre-flight (§3.4.2) gate tests."""

import copy
import json
import os
import sys
import unittest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
FIX = os.path.join(HERE, "..", "fixtures")

import gates  # noqa: E402


def load(name):
    with open(os.path.join(FIX, name)) as fh:
        return json.load(fh)


def passing_smoke_metrics():
    # Mix matches weights exactly: browse 0.8 / checkout 0.2.
    return {
        "http_5xx_count": 0,
        "http_404_count": 0,
        "steps_missing_downstream_span": 0,
        "null_extract_failures": 0,
        "dropped_iterations": 0,
        "synthetic_span_count": 42,
        "journey_counts": {"browse": 160, "checkout": 40},
        "error_counts_per_journey": {
            "browse": {"errors": 0, "total": 160},
            "checkout": {"errors": 0, "total": 40},
        },
    }


class SmokeGateTest(unittest.TestCase):
    def setUp(self):
        self.model = load("workload-model.sample.json")

    def test_all_six_pass(self):
        g = gates.evaluate_smoke(passing_smoke_metrics(), self.model)
        self.assertTrue(g.passed, g.to_dict())
        self.assertEqual(len(g.checks), 6)

    def test_crit1_5xx_fails(self):
        m = passing_smoke_metrics()
        m["http_5xx_count"] = 3
        m["error_counts_per_journey"]["checkout"] = {"errors": 3, "total": 40}
        g = gates.evaluate_smoke(m, self.model)
        self.assertFalse(g.passed)
        self.assertIn("1-no-5xx", [c.id for c in g.failures])

    def test_crit1_5xx_within_baseline_passes(self):
        # 5xx present but each journey stays within its baseline.errorRate.
        m = passing_smoke_metrics()
        m["http_5xx_count"] = 1
        # checkout baseline errorRate 0.005; 0 errors here keeps it under.
        g = gates.evaluate_smoke(m, self.model)
        self.assertTrue([c for c in g.checks if c.id == "1-no-5xx"][0].passed)

    def test_crit2_404_fails(self):
        m = passing_smoke_metrics()
        m["http_404_count"] = 2
        g = gates.evaluate_smoke(m, self.model)
        self.assertFalse(g.passed)
        self.assertIn("2-routes-reachable", [c.id for c in g.failures])

    def test_crit2_missing_downstream_span_fails(self):
        m = passing_smoke_metrics()
        m["steps_missing_downstream_span"] = 1
        g = gates.evaluate_smoke(m, self.model)
        self.assertIn("2-routes-reachable", [c.id for c in g.failures])

    def test_crit3_null_extract_fails(self):
        m = passing_smoke_metrics()
        m["null_extract_failures"] = 5
        g = gates.evaluate_smoke(m, self.model)
        self.assertIn("3-correlation", [c.id for c in g.failures])

    def test_crit4_mix_within_tolerance(self):
        # browse 0.7 / checkout 0.3 vs weights 0.8/0.2 => TVD = 0.1 <= 0.30.
        m = passing_smoke_metrics()
        m["journey_counts"] = {"browse": 140, "checkout": 60}
        g = gates.evaluate_smoke(m, self.model)
        self.assertTrue([c for c in g.checks if c.id == "4-journey-mix"][0].passed)

    def test_crit4_mix_out_of_tolerance_fails(self):
        # all checkout => TVD = 0.8 > 0.30.
        m = passing_smoke_metrics()
        m["journey_counts"] = {"browse": 0, "checkout": 200}
        g = gates.evaluate_smoke(m, self.model)
        self.assertIn("4-journey-mix", [c.id for c in g.failures])

    def test_crit5_no_synthetic_span_fails(self):
        m = passing_smoke_metrics()
        m["synthetic_span_count"] = 0
        g = gates.evaluate_smoke(m, self.model)
        self.assertFalse(g.passed)
        self.assertIn("5-synthetic-visible", [c.id for c in g.failures])

    def test_crit6_dropped_iterations_fails(self):
        m = passing_smoke_metrics()
        m["dropped_iterations"] = 7
        g = gates.evaluate_smoke(m, self.model)
        self.assertIn("6-no-dropped", [c.id for c in g.failures])


class TVDTest(unittest.TestCase):
    def test_identical(self):
        self.assertAlmostEqual(
            gates.total_variation_distance({"a": 8, "b": 2}, {"a": 0.8, "b": 0.2}), 0.0
        )

    def test_disjoint(self):
        self.assertAlmostEqual(
            gates.total_variation_distance({"a": 1}, {"b": 1}), 1.0
        )


class PreflightTest(unittest.TestCase):
    def setUp(self):
        self.model = load("workload-model.sample.json")
        self.rc = load("run-config.sample.json")
        self.commit = "abc123"
        self.v2a = {"passed": True, "commit": "abc123"}
        self.smoke = gates.evaluate_smoke(passing_smoke_metrics(), self.model)

    def _pre(self, rc=None, model=None, smoke=None, v2a=None, commit=None, run_dir=True):
        return gates.preflight_v2b(
            rc or self.rc,
            model or self.model,
            smoke or self.smoke,
            v2a or self.v2a,
            commit or self.commit,
            run_dir,
        )

    def test_all_pass(self):
        self.assertTrue(self._pre().passed, self._pre().to_dict())

    def test_production_env_refused(self):
        rc = copy.deepcopy(self.rc)
        rc["target"]["environment"] = "production"
        self.assertIn("allowlist-nonprod", [c.id for c in self._pre(rc=rc).failures])

    def test_not_on_allowlist_refused(self):
        rc = copy.deepcopy(self.rc)
        rc["target"]["allowlist"] = False
        self.assertIn("allowlist-nonprod", [c.id for c in self._pre(rc=rc).failures])

    def test_v2a_commit_mismatch_refused(self):
        self.assertIn(
            "v2a-passed-on-commit",
            [c.id for c in self._pre(v2a={"passed": True, "commit": "stale"}).failures],
        )

    def test_hash_mismatch_refused(self):
        rc = copy.deepcopy(self.rc)
        rc["modelRef"]["hash"] = "sha256:wrong"
        self.assertIn("approval-valid", [c.id for c in self._pre(rc=rc).failures])

    def test_unapproved_model_refused(self):
        model = copy.deepcopy(self.model)
        model["status"]["approval"]["decision"] = "adjusted"
        self.assertIn("approval-valid", [c.id for c in self._pre(model=model).failures])

    def test_approval_revision_stale_refused(self):
        model = copy.deepcopy(self.model)
        model["status"]["approval"]["revision"] = 2  # model is rev 3
        self.assertIn("approval-valid", [c.id for c in self._pre(model=model).failures])

    def test_p99_abort_below_baseline_refused(self):
        rc = copy.deepcopy(self.rc)
        rc["abort"]["p99MsGt"] = 100  # checkout baseline p99 = 1500 => threshold too low
        self.assertIn("caps-abort-armed", [c.id for c in self._pre(rc=rc).failures])

    def test_failed_smoke_blocks_preflight(self):
        m = passing_smoke_metrics()
        m["synthetic_span_count"] = 0
        bad = gates.evaluate_smoke(m, self.model)
        self.assertIn("smoke-passed", [c.id for c in self._pre(smoke=bad).failures])

    def test_missing_run_dir_refused(self):
        self.assertIn("run-dir", [c.id for c in self._pre(run_dir=False).failures])


if __name__ == "__main__":
    unittest.main()
