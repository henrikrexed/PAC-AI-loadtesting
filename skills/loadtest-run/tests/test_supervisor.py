"""Caps / abort supervisor tests (§7 safety, §3.4.2 rule 2)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from supervisor import Sample, Supervisor, _dur_to_seconds  # noqa: E402


CAPS = {"maxRps": 400, "maxVus": 200, "maxDuration": "30m"}
ABORT = {"errorRateGt": 0.05, "p95MsGt": 2500, "p99MsGt": 4000}


def ok_sample(**kw):
    base = dict(elapsed_s=10, rps=100, vus=50, error_rate=0.0, p95_ms=200, p99_ms=400)
    base.update(kw)
    return Sample(**base)


class DurationTest(unittest.TestCase):
    def test_minutes(self):
        self.assertEqual(_dur_to_seconds("30m"), 1800)

    def test_compound(self):
        self.assertEqual(_dur_to_seconds("1h30m"), 5400)

    def test_bare_number(self):
        self.assertEqual(_dur_to_seconds("90"), 90)

    def test_numeric(self):
        self.assertEqual(_dur_to_seconds(45), 45)

    def test_bad(self):
        with self.assertRaises(ValueError):
            _dur_to_seconds("30x")


class SupervisorTest(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.sup = Supervisor(CAPS, ABORT, teardown=self.calls.append)

    def test_nominal_continue(self):
        self.assertEqual(self.sup.observe(ok_sample()), "continue")
        self.assertFalse(self.sup.aborted)
        self.assertEqual(self.calls, [])

    def test_cap_rps(self):
        self.assertEqual(self.sup.observe(ok_sample(rps=401)), "abort")
        self.assertTrue(self.sup.aborted)
        self.assertIn("cap:maxRps", self.sup.abort_reason)

    def test_cap_vus(self):
        self.assertEqual(self.sup.observe(ok_sample(vus=201)), "abort")
        self.assertIn("cap:maxVus", self.sup.abort_reason)

    def test_cap_duration(self):
        self.assertEqual(self.sup.observe(ok_sample(elapsed_s=1801)), "abort")
        self.assertIn("cap:maxDuration", self.sup.abort_reason)

    def test_abort_error_rate(self):
        self.assertEqual(self.sup.observe(ok_sample(error_rate=0.06)), "abort")
        self.assertIn("abort:errorRateGt", self.sup.abort_reason)

    def test_abort_p95(self):
        self.assertEqual(self.sup.observe(ok_sample(p95_ms=2501)), "abort")
        self.assertIn("abort:p95MsGt", self.sup.abort_reason)

    def test_abort_p99(self):
        self.assertEqual(self.sup.observe(ok_sample(p99_ms=4001)), "abort")
        self.assertIn("abort:p99MsGt", self.sup.abort_reason)

    def test_teardown_called_exactly_once(self):
        self.sup.observe(ok_sample(rps=500))
        self.sup.observe(ok_sample(rps=500))  # already latched
        self.assertEqual(len(self.calls), 1)

    def test_latched_after_abort(self):
        self.sup.observe(ok_sample(rps=500))
        self.assertEqual(self.sup.observe(ok_sample()), "abort")  # stays aborted


if __name__ == "__main__":
    unittest.main()
