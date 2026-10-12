"""Tests for the baseline-diff skill (methodology §3.5).

Maps directly onto the acceptance criteria:
  AC1 — schema-valid shape-diff.json with synthetic traffic correctly isolated.
  AC2 — correctly flags an over/under-shoot dimension and classifies the action.
  AC3 — includes at least one infra-metric (non-telemetry) cross-check (R5).

Plus the §3.5 mechanics: sampling + scale normalization, the R5-contradiction and
R5-unavailable gates, the R8 tolerance-drift flag, and the iteration cap.

Run: python3 -m unittest discover -s skills/baseline-diff/scripts -p 'test_*.py'
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIX = HERE.parent / "fixtures"
sys.path.insert(0, str(HERE))

import diff  # noqa: E402
import build_shape_diff as bsd  # noqa: E402


def _load(name: str) -> dict:
    return json.loads((FIX / f"diff-input.{name}.json").read_text())


class TestAcceptPath(unittest.TestCase):
    def test_all_within_tolerance_and_r5_corroborates_accepts(self):
        doc = bsd.build(_load("accept"))
        self.assertEqual(doc["decision"], "accept")
        self.assertEqual(doc["failedDimensions"], [])
        for d in doc["dimensions"].values():
            self.assertTrue(d["pass"], d)

    def test_accept_output_is_schema_valid(self):  # AC1
        doc = bsd.build(_load("accept"))
        bsd.validate(doc)  # raises on failure

    def test_synthetic_isolation_probe_zero_is_caveated(self):  # AC1 (isolation)
        inp = _load("accept")
        inp["syntheticProbeCount"] = 0
        doc = bsd.build(inp)
        self.assertEqual(doc["syntheticProbeCount"], 0)
        self.assertTrue(any("baggage" in c for c in doc["caveats"]))


class TestIteratePath(unittest.TestCase):
    def setUp(self):
        self.doc = bsd.build(_load("iterate"))

    def test_overshoot_flagged_and_decision_is_iterate(self):  # AC2
        self.assertEqual(self.doc["decision"], "iterate")
        self.assertIn("latency", self.doc["failedDimensions"])
        self.assertIn("journeyMix", self.doc["failedDimensions"])

    def test_latency_overshoot_detail(self):  # AC2 — correctly flags the dimension
        lat = self.doc["dimensions"]["latency"]
        self.assertFalse(lat["pass"])
        # checkout p99 20->... baseline 480 test 900 => ~0.875 rel > 0.35
        self.assertGreater(lat["p99Rel"], 0.35)

    def test_miss_is_classified(self):  # AC2 — classifies the iteration action
        kinds = {c["dimension"]: c for c in self.doc["classifications"]}
        self.assertEqual(kinds["latency"]["classification"], "latency")
        self.assertFalse(kinds["latency"]["structural"])  # parameter-only
        self.assertEqual(kinds["journeyMix"]["classification"], "mix")

    def test_iterate_output_is_schema_valid(self):
        bsd.validate(self.doc)


class TestR5CrossCheck(unittest.TestCase):
    def test_crosscheck_always_present(self):  # AC3
        doc = bsd.build(_load("accept"))
        self.assertIn("r5CrossCheck", doc)
        self.assertTrue(doc["r5CrossCheck"]["available"])
        self.assertEqual(doc["r5CrossCheck"]["plane"], "infra (non-telemetry)")

    def test_infra_contradiction_forces_escalate(self):  # AC3 — the whole point of R5
        doc = bsd.build(_load("r5-contradiction"))
        # all telemetry dims pass, but CPU stayed flat under a load claim
        self.assertEqual(doc["decision"], "escalate")
        self.assertFalse(doc["r5CrossCheck"]["pass"])
        self.assertIn("contradict", doc["reason"])

    def test_unavailable_r5_blocks_clean_accept(self):  # R5 "not optional"
        inp = _load("accept")
        inp["r5CrossCheck"] = {"available": False}
        doc = bsd.build(inp)
        self.assertEqual(doc["decision"], "escalate")
        self.assertTrue(any("circular" in c.lower() or "unavailable" in c.lower()
                            for c in doc["caveats"]))

    def test_require_r5_false_allows_accept_without_infra(self):
        inp = _load("accept")
        inp["r5CrossCheck"] = {"available": False}
        inp["requireR5"] = False
        doc = bsd.build(inp)
        self.assertEqual(doc["decision"], "accept")


class TestNormalization(unittest.TestCase):
    def test_sampling_correction_applied_to_arrival_shape(self):
        # baseline sampled at 50% => true baseline rate doubles before scaling.
        inp = _load("accept")
        inp["samplingFactor"] = {"prod": 0.5, "test": 1.0}
        # scale so expected == test: expected = (base/0.5)*scaling. base~410,
        # test~104 => scaling 0.125 makes expected ~102.5 ≈ test.
        inp["scalingFactor"] = 0.125
        doc = bsd.build(inp)
        self.assertTrue(doc["dimensions"]["arrivalShape"]["pass"])
        # Without correction (treating prod as unsampled) the expected curve would
        # be ~half and WMAPE would blow past 0.20 — confirm the knob bites:
        inp2 = _load("accept")
        inp2["scalingFactor"] = 0.125  # mismatched for unsampled baseline
        doc2 = bsd.build(inp2)
        self.assertFalse(doc2["dimensions"]["arrivalShape"]["pass"])

    def test_wmape_zero_expected_is_zero(self):
        self.assertEqual(diff.wmape([0, 0], [0, 0]), 0.0)

    def test_tvd_matches_hand_calc(self):
        # observed 80/20, target 50/50 => TVD = 0.30
        tvd = diff.total_variation_distance({"a": 80, "b": 20}, {"a": 50, "b": 50})
        self.assertAlmostEqual(tvd, 0.30, places=6)


class TestGovernanceR8(unittest.TestCase):
    def test_loosened_tolerance_is_flagged(self):  # R8 anti-gaming
        inp = _load("accept")
        inp["tolerances"] = {"journeyTvd": 0.40, "p99Rel": 0.80}  # both looser
        doc = bsd.build(inp)
        drift = {d["dimension"] for d in doc["governance"]["toleranceDrift"]}
        self.assertEqual(drift, {"journeyTvd", "p99Rel"})
        self.assertTrue(any("R8" in c for c in doc["caveats"]))

    def test_tightened_tolerance_not_flagged(self):
        inp = _load("accept")
        inp["tolerances"] = {"journeyTvd": 0.05}  # stricter — fine
        doc = bsd.build(inp)
        self.assertNotIn("governance", doc)


class TestIterationCap(unittest.TestCase):
    def test_fourth_miss_escalates(self):  # §3.5 cap: max 3 iterations
        inp = _load("iterate")
        inp["iterationIndex"] = 4
        doc = bsd.build(inp)
        self.assertEqual(doc["decision"], "escalate")
        self.assertIn("after 3 iterations", doc["reason"])

    def test_third_miss_still_iterates(self):
        inp = _load("iterate")
        inp["iterationIndex"] = 3
        doc = bsd.build(inp)
        self.assertEqual(doc["decision"], "iterate")


class TestCacheDimension(unittest.TestCase):
    def test_cache_dim_only_when_present(self):
        doc = bsd.build(_load("accept"))
        self.assertNotIn("cacheHitRatio", doc["dimensions"])

    def test_cache_overshoot_flagged(self):  # G4
        inp = _load("accept")
        inp["cacheHitRatio"] = {"/products/{id}": {"baseline": 0.80, "test": 0.55}}
        doc = bsd.build(inp)
        self.assertIn("cacheHitRatio", doc["dimensions"])
        self.assertFalse(doc["dimensions"]["cacheHitRatio"]["pass"])
        self.assertEqual(doc["decision"], "iterate")
        kinds = {c["dimension"]: c for c in doc["classifications"]}
        self.assertEqual(kinds["cacheHitRatio"]["classification"], "cache")


if __name__ == "__main__":
    unittest.main(verbosity=2)
