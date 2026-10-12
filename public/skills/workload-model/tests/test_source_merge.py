"""Dual-source RUM⟗span merge reconciler tests (SCOPE §3.1 step 2c)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import source_merge as sm  # noqa: E402


def test_common_key_is_rum_primary_with_span_extrapolation():
    # RUM saw 2/s, spans (unsampled truth) saw 8/s → RUM is sampled; extrapolate ×4.
    entries = {e.key: e for e in sm.reconcile({"GET /api/cart": 2.0}, {"GET /api/cart": 8.0})}
    e = entries["GET /api/cart"]
    assert e.source == "rum"
    assert e.extrapolationFactor == 4.0
    assert e.rumRate == 2.0 and e.spanRate == 8.0


def test_span_only_key_is_http_scenario():
    (e,) = sm.reconcile({}, {"grpc cart.Reserve": 5.0})
    assert e.source == "span"
    assert e.extrapolationFactor is None
    assert "span-order HTTP scenario" in e.rationale


def test_rum_only_key_is_dropped():
    # design decision: a RUM key with no server span is NOT modelled
    entries = sm.reconcile({"client route-change": 3.0}, {})
    assert entries == []


def test_entries_sorted_by_effective_driven_rate_desc():
    entries = sm.reconcile(
        {"a": 1.0, "b": 1.0},
        {"a": 100.0, "b": 2.0, "c": 50.0},
    )
    # effective rate = span truth where present: a=100, c=50, b=2
    assert [e.key for e in entries] == ["a", "c", "b"]


def test_merge_plan_summary_math_and_dropped_rum_only():
    plan = sm.merge_plan(
        {"a": 2.0, "b": 4.0, "clientX": 1.0},  # clientX is rum-only -> dropped
        {"a": 8.0, "b": 8.0, "back": 10.0},    # spans add a backend-only key
    )
    s = plan["summary"]
    assert s["keys"] == 3            # a, b, back (clientX dropped, not emitted)
    assert s["rumPrimaryKeys"] == 2
    assert s["spanFallbackKeys"] == 1
    assert s["droppedRumOnlyKeys"] == 1
    assert all(e["key"] != "clientX" for e in plan["entries"])
    # extrapolation factors: a=4.0, b=2.0 → mean 3.0, range [2,4]
    assert s["meanExtrapolationFactor"] == 3.0
    assert s["extrapolationFactorRange"] == [2.0, 4.0]
    # rum-driven share = (8+8)/(8+8+10) = 16/26
    assert s["rumDrivenShare"] == round(16 / 26, 4)


def test_empty_inputs():
    plan = sm.merge_plan({}, {})
    assert plan["entries"] == []
    assert plan["summary"]["keys"] == 0
