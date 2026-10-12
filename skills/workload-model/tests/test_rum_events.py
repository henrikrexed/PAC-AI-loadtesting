"""Ordered RUM-journey tests (SCOPE §3.1 step 2c, `user.events`) — ISI-5719.

Covers the pure `rum_events` stitcher on synthetic `user.events`-shaped rows so the extractor is
deterministic and version-controlled *before* the `storage:user.events:read` scope lands. On
grant, the only new step is confirming live field names at the explore-data gate and feeding real
rows — the logic under test here does not change.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import rum_events as re  # noqa: E402

NS = 1_000_000_000


def _ev(sid, ts_s, etype, name="", dur_ms=0.0, endpoint="", app="astroshop"):
    return re.RumEvent(session_id=sid, ts_ns=int(ts_s * NS), etype=re.norm_type(etype),
                       name=name, duration_ms=dur_ms, endpoint=endpoint, app=app)


# --------------------------------------------------------------------------- time parse

def test_iso_to_ns_full_nanosecond_precision():
    assert re.iso_to_ns("2026-10-12T13:16:12.600411257Z") % NS == 600411257
    assert re.iso_to_ns("1970-01-01T00:00:00Z") == 0
    assert re.iso_to_ns("1970-01-01T00:00:01Z") == NS


def test_iso_to_ns_accepts_numeric_epoch():
    assert re.iso_to_ns(1_500_000_000) == 1_500_000_000


# --------------------------------------------------------------------------- type norm

def test_norm_type_maps_common_spellings():
    assert re.norm_type("PAGE_VIEW") == "view"
    assert re.norm_type("User Action") == "action"
    assert re.norm_type("XHR") == "request"
    assert re.norm_type("JS_ERROR") == "error"
    # unknown passes through lower-cased
    assert re.norm_type("WeirdType") == "weirdtype"


# --------------------------------------------------------------------------- parse

def test_parse_rows_tolerant_field_namings_and_drops_sessionless():
    rows = [
        {"dt.rum.session.id": "s1", "timestamp": "2026-10-12T00:00:00Z",
         "event.type": "VIEW", "event.name": "home"},
        {"sessionId": "s2", "time": 10 * NS, "type": "xhr",
         "url": "/api/cart", "duration": 5 * 1_000_000},   # 5ms as ns
        {"timestamp": "2026-10-12T00:00:00Z", "event.type": "VIEW"},  # no session -> dropped
    ]
    evs = re.parse_rows(rows)
    assert [e.session_id for e in evs] == ["s1", "s2"]
    assert evs[0].etype == "view" and evs[0].name == "home"
    assert evs[1].etype == "request" and evs[1].endpoint == "/api/cart"
    assert abs(evs[1].duration_ms - 5.0) < 1e-6   # ns heuristic -> ms


def test_parse_rows_duration_already_ms_passthrough():
    (e,) = re.parse_rows([{"session.id": "s", "timestamp": 0, "duration": 250}])
    assert abs(e.duration_ms - 250.0) < 1e-6      # <= 1e6 treated as ms


# --------------------------------------------------------------------------- stitch

def test_stitch_orders_by_timestamp_and_groups_by_session():
    evs = [_ev("B", 10, "view"), _ev("A", 2, "action"), _ev("A", 0, "view"), _ev("A", 1, "action")]
    js = {j.session_id: j for j in re.stitch_journeys(evs)}
    assert [e.ts_ns for e in js["A"].events] == [0, 1 * NS, 2 * NS]
    assert js["A"].length == 3 and js["B"].length == 1


def test_think_time_is_gap_between_prev_end_and_next_start_clipped():
    # ev0 [0..1s], ev1 starts at 3s -> think = 3 - 1 = 2s = 2000ms
    (j,) = re.stitch_journeys([_ev("s", 0, "view", dur_ms=1000), _ev("s", 3, "action", dur_ms=500)])
    assert j.think_ms == [2000.0]
    assert round(j.duration_s, 3) == 3.5     # ev1 start 3s + 0.5s dur


def test_overlapping_events_clip_think_to_zero():
    (j,) = re.stitch_journeys([_ev("s", 0, "view", dur_ms=5000), _ev("s", 2, "action", dur_ms=100)])
    assert j.think_ms == [0.0]


def test_sequence_excludes_requests_by_default():
    evs = [_ev("s", 0, "view", "home"), _ev("s", 1, "request", endpoint="/api/x"),
           _ev("s", 2, "action", "add_to_cart")]
    (j,) = re.stitch_journeys(evs)
    assert j.sequence() == ["home", "add_to_cart"]
    assert j.sequence(kinds=("view", "action", "request")) == ["home", "/api/x", "add_to_cart"]


# --------------------------------------------------------------------------- think-time spec

def test_think_time_spec_empirical_and_none():
    evs = [_ev("s", 0, "view", dur_ms=0), _ev("s", 2, "action", dur_ms=0),
           _ev("s", 5, "action", dur_ms=0)]
    (j,) = re.stitch_journeys(evs)
    spec = re.think_time_spec([j])
    assert spec["distribution"] == "empirical"
    assert spec["minMs"] == 2000.0 and spec["maxMs"] == 3000.0
    # single-action session -> no think-time signal -> None
    (single,) = re.stitch_journeys([_ev("x", 0, "view")])
    assert re.think_time_spec([single]) is None


# --------------------------------------------------------------------------- journey templates

def test_journey_templates_count_and_weight_exact_sequences():
    # two sessions walk home->cart, one walks home->checkout
    j1 = re.stitch_journeys([_ev("a", 0, "view", "home"), _ev("a", 1, "action", "cart")])
    j2 = re.stitch_journeys([_ev("b", 0, "view", "home"), _ev("b", 1, "action", "cart")])
    j3 = re.stitch_journeys([_ev("c", 0, "view", "home"), _ev("c", 1, "action", "checkout")])
    tmpls = re.journey_templates(j1 + j2 + j3)
    assert tmpls[0].sequence == ("home", "cart") and tmpls[0].sessions == 2
    assert round(tmpls[0].weight, 4) == 0.6667
    assert tmpls[1].sequence == ("home", "checkout") and tmpls[1].sessions == 1


def test_journey_templates_min_sessions_drops_singletons_but_keeps_denominator():
    js = []
    for sid in ("a", "b", "c"):
        js += re.stitch_journeys([_ev(sid, 0, "view", "home"), _ev(sid, 1, "action", "cart")])
    js += re.stitch_journeys([_ev("z", 0, "view", "oddpage")])
    tmpls = re.journey_templates(js, min_sessions=2)
    assert len(tmpls) == 1
    # weight still computed over all 4 sequences (denominator includes the dropped singleton)
    assert round(tmpls[0].weight, 4) == 0.75


# --------------------------------------------------------------------------- endpoint rates + overlap

def test_endpoint_rates_from_request_events_only():
    evs = [_ev("s", 0, "request", endpoint="/api/cart"),
           _ev("s", 1, "request", endpoint="/api/cart"),
           _ev("s", 2, "view", "home"),                       # non-request ignored
           _ev("s", 3, "request", endpoint="/api/checkout")]
    rates = re.endpoint_rates(evs, window_s=2.0)
    assert rates["/api/cart"] == 1.0           # 2 / 2s
    assert rates["/api/checkout"] == 0.5
    assert re.endpoint_rates(evs, window_s=0) == {}


def test_per_endpoint_overlap_delegates_to_source_merge():
    evs = [_ev("s", 0, "request", endpoint="/api/cart"),
           _ev("s", 1, "request", endpoint="/api/cart")]   # RUM sees /api/cart at 1/s
    span_rates = {"/api/cart": 4.0, "/api/backend": 2.0}    # spans: cart 4/s (sampled 4x), backend-only
    plan = re.per_endpoint_overlap(evs, span_rates, window_s=2.0)
    by_key = {e["key"]: e for e in plan["entries"]}
    assert by_key["/api/cart"]["source"] == "rum"
    assert by_key["/api/cart"]["extrapolationFactor"] == 4.0   # span 4 / rum 1
    assert by_key["/api/backend"]["source"] == "span"
    assert plan["summary"]["rumPrimaryKeys"] == 1
    assert plan["summary"]["spanFallbackKeys"] == 1


if __name__ == "__main__":
    import subprocess
    raise SystemExit(subprocess.call([sys.executable, "-m", "pytest", "-q", __file__]))
