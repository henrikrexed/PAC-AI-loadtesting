"""Path B session-stitch tests (SCOPE §3.1 step 2c tier ii, R5 closure).

Covers the pure stitching core on synthetic chains and a fixture-backed reproduction of the
synthetic example numbers so the extractor stays deterministic and version-controlled.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import session_stitch as ss  # noqa: E402

FX = json.loads(
    (Path(__file__).resolve().parent.parent / "fixtures" / "example_session_stitch.json").read_text()
)

NS = 1_000_000_000


def _span(sid, start_s, dur_ms, op="op", svc="svc"):
    return ss.SessionSpan(session_id=sid, start_ns=int(start_s * NS),
                          duration_ns=int(dur_ms * 1_000_000), service=svc, operation=op)


# --------------------------------------------------------------------------- iso parser

def test_iso_to_ns_full_nanosecond_precision():
    # no micro-truncation: all 9 fractional digits survive
    assert ss.iso_to_ns("2026-10-12T13:16:12.600411257Z") % NS == 600411257
    # whole-second timestamp
    assert ss.iso_to_ns("1970-01-01T00:00:00Z") == 0
    assert ss.iso_to_ns("1970-01-01T00:00:01Z") == NS


# --------------------------------------------------------------------------- stitching

def test_stitch_orders_by_start_and_groups_by_session():
    spans = [_span("B", 10, 5), _span("A", 2, 5), _span("A", 0, 5), _span("A", 1, 5)]
    chains = {c.session_id: c for c in ss.stitch(spans)}
    assert [s.start_ns for s in chains["A"].actions] == [0, 1 * NS, 2 * NS]  # sorted
    assert chains["A"].length == 3
    assert chains["B"].length == 1


def test_think_time_is_gap_between_prev_end_and_next_start_clipped():
    # action0 [0..1s], action1 starts at 3s -> think = 3 - 1 = 2s = 2000ms
    spans = [_span("S", 0, 1000), _span("S", 3, 1000)]
    (c,) = ss.stitch(spans)
    assert c.think_ms == [2000.0]
    assert round(c.duration_s, 3) == 4.0  # 3s start + 1s dur


def test_overlapping_spans_clip_think_time_to_zero():
    # action1 starts before action0 ends -> negative gap clipped to 0
    spans = [_span("S", 0, 5000), _span("S", 2, 100)]
    (c,) = ss.stitch(spans)
    assert c.think_ms == [0.0]


def test_single_action_session_has_no_think_time_and_spec_is_none():
    (c,) = ss.stitch([_span("solo", 0, 10)])
    assert c.think_ms == []
    assert ss.think_time_spec([c]) is None  # no fabricated think-time


def test_max_gap_splits_one_session_into_subchains():
    # two visits under one reused id, separated by a 100s gap > max_gap_s=30
    spans = [_span("R", 0, 100), _span("R", 5, 100), _span("R", 105, 100)]
    chains = ss.stitch(spans, max_gap_s=30)
    assert len(chains) == 2
    assert sorted(c.length for c in chains) == [1, 2]
    # without the boundary it is one chain
    assert len(ss.stitch(spans)) == 1


# --------------------------------------------------------------------------- think-time spec

def test_empirical_spec_is_schema_shaped_and_bounded():
    spans = []
    for i in range(1000):
        spans.append(_span("x", i * 10, 10))  # 999 ~10s think-times
    (c,) = ss.stitch(spans)
    spec = ss.think_time_spec([c], mode="empirical", max_samples=64)
    assert spec["distribution"] == "empirical"
    assert len(spec["samples"]) <= 64
    assert spec["minMs"] <= spec["meanMs"] <= spec["maxMs"]


def test_exponential_spec_is_mean_only():
    spans = [_span("x", 0, 1000), _span("x", 3, 1000), _span("x", 10, 1000)]
    (c,) = ss.stitch(spans)
    spec = ss.think_time_spec([c], mode="exponential")
    assert spec == {"distribution": "exponential", "meanMs": spec["meanMs"]}
    assert set(spec) == {"distribution", "meanMs"}


# --------------------------------------------------------------------------- coverage report

def test_session_coverage_computes_percentages_and_signal():
    rep = ss.session_coverage([
        {"service": "ad", "totalSpans": 100, "sessionSpans": 20, "sessions": 5, "meanActions": 4.0},
        {"service": "x", "totalSpans": 100, "sessionSpans": 0, "sessions": 0},
    ])
    assert rep["hasSessionSignal"] is True
    assert rep["overallCoveragePct"] == 10.0  # 20 / 200
    ad = next(s for s in rep["services"] if s["service"] == "ad")
    assert ad["coveragePct"] == 20.0
    assert ad["meanActions"] == 4.0


def test_session_coverage_no_signal_flags_fallback():
    rep = ss.session_coverage([{"service": "x", "totalSpans": 100, "sessionSpans": 0}])
    assert rep["hasSessionSignal"] is False
    assert rep["overallCoveragePct"] == 0.0


# --------------------------------------------------------------------------- fixture reproduction

def test_fixture_reproduces_example_ad_numbers():
    """The synthetic example `ads` facts captured in the fixture are internally consistent."""
    tt = FX["ad_think_time_ms"]
    assert tt["n"] == 19000
    assert 7000 < tt["p50"] < 7500      # median think-time ~7.2s
    assert 10000 < tt["mean"] < 12000
    sl = FX["ad_session_length"]
    assert sl["sessions"] == 5000
    assert sl["actionsPerSession"]["mean"] == 5.25
    assert 46 < sl["durationSeconds"]["p50"] < 48
    assert FX["ad_exponential_fit"]["fit"] == "exponential"


def test_fixture_coverage_report_round_trips():
    rep = ss.session_coverage(FX["coverage_rows"])
    assert rep["hasSessionSignal"] is True
    ad = next(s for s in rep["services"] if s["service"] == "ads")
    assert 20.0 < ad["coveragePct"] < 20.5   # 20390 / 100000 = 20.39%
    sf = next(s for s in rep["services"] if s["service"].startswith("chat-agent"))
    assert 5.0 < sf["coveragePct"] < 5.6     # non-browser app also carries session.id
