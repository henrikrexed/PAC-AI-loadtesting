"""RUM user-session signal tests (SCOPE §3.1 step 2c, Grail-native user.sessions).

Covers the pure session-shape core on synthetic sessions and a fixture-backed coverage check
against the synthetic example user.sessions facts.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import rum_sessions as rs  # noqa: E402

FX = json.loads(
    (Path(__file__).resolve().parent.parent / "fixtures" / "example_rum_sessions.json").read_text()
)


def _s(app, actions, dur_s, nav=None, bounce=False, err=0):
    return rs.RumSession(app=app, user_action_count=actions,
                         navigation_count=nav if nav is not None else actions,
                         duration_s=dur_s, is_bounce=bounce, error_count=err)


def test_parse_rows_handles_ns_duration_and_app_fallbacks():
    rows = [{"frontend.name": "storefront-web", "user_action_count": 9, "navigation_count": 8,
             "duration": 26_000_000_000, "characteristics.is_bounce": False, "error.count": 0}]
    (p,) = rs.parse_rows(rows)
    assert p.app == "storefront-web"
    assert p.user_action_count == 9
    assert abs(p.duration_s - 26.0) < 1e-6
    # app fallback to dt.rum.application.entities list
    (q,) = rs.parse_rows([{"dt.rum.application.entities": ["APPLICATION-X"],
                           "user_action_count": 1, "duration": 1_000_000_000}])
    assert q.app == "APPLICATION-X"


def test_mean_interaction_gap_is_duration_over_actions_minus_one():
    assert rs.mean_interaction_gap_s(30.0, 7) == 5.0   # 30 / (7-1)
    assert rs.mean_interaction_gap_s(10.0, 1) == 0.0   # single action -> no gap
    assert rs.mean_interaction_gap_s(0.0, 5) == 0.0


def test_session_shape_distributions_and_rates():
    sessions = [
        _s("A", 8, 16.0, bounce=False, err=0),
        _s("A", 9, 27.0, bounce=False, err=1),
        _s("A", 1, 2.0, bounce=True, err=0),
    ]
    shape = rs.session_shape(sessions)
    assert shape["sessions"] == 3
    assert shape["actionsPerSession"]["n"] == 3
    assert shape["bounceRate"] == round(1 / 3, 4)
    assert shape["errorSessionRate"] == round(1 / 3, 4)
    # gap distribution only over multi-action sessions (2 of 3)
    assert shape["meanInteractionGapSeconds"]["n"] == 2


def test_session_shape_empty():
    assert rs.session_shape([]) == {"sessions": 0}


def test_rum_coverage_from_fixture_totals_and_sorting():
    rep = rs.rum_coverage([
        {"app": a["app"], "type": a["type"], "sessions": a["sessions"],
         "actionsP50": a["actionsP50"], "durationP50Seconds": a["durationP50Seconds"],
         "bounceRate": a["bounceRate"]}
        for a in FX["per_app"]
    ])
    assert rep["hasRumSignal"] is True
    # top app is storefront-web by sessions
    assert rep["apps"][0]["app"] == "storefront-web"
    assert rep["apps"][0]["sessions"] == 12000
    # mobile app present -> app-agnostic (web + mobile)
    assert any(a["type"] == "mobile" for a in rep["apps"])
    assert rep["totalSessions"] == sum(a["sessions"] for a in FX["per_app"])


def test_fixture_is_internally_consistent():
    # the synthetic RUM population dwarfs the span/session.id ad marker (5,000 ad sessions)
    assert FX["totalRumSessions24h"] == 24000
    assert sum(a["sessions"] for a in FX["per_app"]) < FX["totalRumSessions24h"]  # top apps subset
    # every modelled web app has multi-action sessions (real journeys, not single hits)
    for a in FX["per_app"]:
        if a["type"] == "web":
            assert a["actionsP50"] >= 5
