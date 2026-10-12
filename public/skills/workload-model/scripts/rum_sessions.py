"""SCOPE §3.1 step 2c — RUM user-session signal via Grail-native `user.sessions` / `user.events`.

Note: RUM is reachable in Grail — the key is probing the right objects (`dt.rum.*` and RUM attrs
on `spans` are the wrong ones). The real Dynatrace Grail RUM objects are **`user.sessions`**
(one row per real-user session, with action / navigation counts, duration, bounce, errors,
app/frontend, geo/device) and **`user.events`** (the per-session ordered navigation — views,
user actions, requests, errors). Both are DQL-native; no classic / USQL token is required.
The pointer: `fetch user.events | filter dt.rum.session.id == "…"`.

Token scopes needed:
  * `user.sessions` — typically accessible with a plain read token (this module consumes it):
    one row per real-user session across your RUM apps (web and mobile). This is the real
    user-session population a span/`session.id` marker may not see.
  * `user.events` — **scope-gated**: needs `storage:user.events:read` on the token (403 otherwise).
    Required for the *ordered* action sequence, exact per-action think-times, and the actual pages
    / use-cases. Until the scope is granted, `user.sessions` gives session **shape** (how many
    actions, how long, bounce) but not the ordered journey.

Design mirrors `session_stitch.py` / `shaping.py`: **no telemetry I/O here.** The caller runs the
DQL and injects rows; these functions are pure and deterministic. App-agnostic — works for every
RUM app (web and mobile).
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass


def _pctl(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    n = len(sorted_vals)
    return sorted_vals[min(n - 1, int(p / 100 * n))]


def _dist(vals: list[float]) -> dict:
    if not vals:
        return {"n": 0}
    s = sorted(vals)
    return {
        "n": len(s),
        "p50": round(_pctl(s, 50), 3),
        "p90": round(_pctl(s, 90), 3),
        "p99": round(_pctl(s, 99), 3),
        "max": round(s[-1], 3),
        "mean": round(statistics.mean(s), 3),
    }


@dataclass
class RumSession:
    """One `user.sessions` row (the fields we model a workload from)."""
    app: str
    user_action_count: int
    navigation_count: int
    duration_s: float
    is_bounce: bool = False
    error_count: int = 0


def parse_rows(rows: list[dict]) -> list[RumSession]:
    """`user.sessions` DQL records -> RumSession list. `duration` is nanoseconds."""
    out: list[RumSession] = []
    for r in rows:
        app = r.get("frontend.name") or r.get("fe") or r.get("app") \
            or (r.get("dt.rum.application.entities") or [None])[0] or "unknown"
        if isinstance(app, list):
            app = app[0] if app else "unknown"
        dur = r.get("duration")
        out.append(RumSession(
            app=str(app),
            user_action_count=int(r.get("user_action_count") or 0),
            navigation_count=int(r.get("navigation_count") or 0),
            duration_s=(float(dur) / 1e9) if dur is not None else 0.0,
            is_bounce=bool(r.get("characteristics.is_bounce") or r.get("is_bounce") or False),
            error_count=int(r.get("error.count") or r.get("error_count") or 0),
        ))
    return out


def mean_interaction_gap_s(duration_s: float, action_count: int) -> float:
    """APPROXIMATE inter-action gap = session duration / (actions-1).

    This is a session-aggregate *estimate* of pacing, NOT a measured think-time: `user.sessions`
    carries no per-action timings. It is strictly better than a blind constant (it is anchored to
    the real session duration and real action count), but the exact per-action think-time
    distribution requires `user.events` (scope-gated). Labelled as such wherever emitted.
    """
    return round(duration_s / (action_count - 1), 3) if action_count > 1 else 0.0


def session_shape(sessions: list[RumSession]) -> dict:
    """Per-RUM-session-population shape: action/navigation/duration distributions + bounce.

    This is the real session-boundary + session-length signal (R5) across the whole RUM
    population — the thing the span/`session.id` ad marker could not provide.
    """
    if not sessions:
        return {"sessions": 0}
    actions = [float(s.user_action_count) for s in sessions]
    gaps = [mean_interaction_gap_s(s.duration_s, s.user_action_count)
            for s in sessions if s.user_action_count > 1]
    return {
        "sessions": len(sessions),
        "actionsPerSession": _dist(actions),
        "navigationsPerSession": _dist([float(s.navigation_count) for s in sessions]),
        "durationSeconds": _dist([s.duration_s for s in sessions]),
        "meanInteractionGapSeconds": _dist(gaps),  # APPROX (see mean_interaction_gap_s)
        "bounceRate": round(sum(1 for s in sessions if s.is_bounce) / len(sessions), 4),
        "errorSessionRate": round(sum(1 for s in sessions if s.error_count > 0) / len(sessions), 4),
    }


def rum_coverage(per_app: list[dict]) -> dict:
    """Coverage report over the RUM apps (consumes DQL `summarize ... by:{app}` rows).

    Input per app: {"app": str, "type": "web"|"mobile", "sessions": int,
                    "actionsP50": number, "durationP50Seconds": number} (extra keys passed through).
    Output attaches to metadata.source.rumSessionCoverage:
      {"hasRumSignal": bool, "totalSessions": int, "apps": [... sorted by sessions]}.
    """
    apps = []
    total = 0
    for r in per_app:
        n = int(r.get("sessions") or 0)
        total += n
        apps.append({
            "app": str(r["app"]),
            "type": str(r.get("type") or "unknown"),
            "sessions": n,
            **{k: r[k] for k in ("actionsP50", "durationP50Seconds", "bounceRate") if k in r},
        })
    apps.sort(key=lambda x: x["sessions"], reverse=True)
    return {"hasRumSignal": total > 0, "totalSessions": total, "apps": apps}
