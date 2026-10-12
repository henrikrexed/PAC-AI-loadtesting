"""SCOPE §3.1 step 2c — **ordered** RUM journeys from Grail-native `user.events` (ISI-5719).

The finer half of the step-2c RUM signal. `rum_sessions.py` consumes `user.sessions` and gives
session *shape* (how many actions, how long, bounce) but no ordering and no per-action timing.
`user.events` is the per-session **ordered navigation** — views, user actions, requests, errors
with their real order and exact inter-action timings — i.e. the actual pages / use-cases, the
exact action sequence, and the measured think-times. This module stitches those rows into
RUM-primary journey templates and the per-endpoint RUM rates the dual-source merge
(`source_merge.py`) consumes as its *authoritative* RUM side.

Blocker (ISI-5719): `fetch user.events` on the `tenant-b`/wkf10640 read token returns
**`403 NOT_AUTHORIZED_FOR_TABLE` — missing `storage:user.events:read`** (re-confirmed live
2026-10-12). `user.sessions` is already accessible; this is the one additional OAuth scope.
Unblock owner: the board / tenant admin who minted the `tenant-b` dt0s16 token. Action: add
scope `storage:user.events:read`. This module is **pure and testable without the data** (same
contract as `session_stitch.py` / `rum_sessions.py`: the caller runs the DQL and injects rows),
so it is drop-in ready — on grant, the only remaining step is to confirm the live field names at
the explore-data gate and feed the rows in.

Design mirrors `session_stitch.py`: **no telemetry I/O here.** Everything is pure and
deterministic. App-agnostic — works for every RUM app (web and mobile).

DQL the caller runs on scope grant (field names TO BE CONFIRMED at the explore-data gate against
live sample output — never embed unverified field names in a tile/extractor; the parse layer
below is tolerant of the common namings so confirmation is a projection tweak, not a rewrite):

    fetch user.events, from:now()-24h
    | fields dt.rum.session.id, timestamp, event.type, event.name, duration,
             application, endpoint          // endpoint = request target/url for REQUEST events
    | sort timestamp asc

PII note (§7.1 scrub still applies): session ids are opaque; drop/neverproject geo/user/IP fields.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field


# --------------------------------------------------------------------------- time parse

def iso_to_ns(ts) -> int:
    """RFC3339 (`...Z`, up to ns) OR an already-numeric epoch value -> integer epoch ns.

    `user.events` `timestamp` arrives either as an ISO string or (via some DQL projections) as a
    numeric epoch. Both are accepted; ISO keeps full ns resolution (no datetime micro-truncation).
    """
    if not isinstance(ts, str):
        return int(ts)
    ts = ts.strip().rstrip("Z")
    head, _, frac = ts.partition(".")
    frac_ns = int((frac + "000000000")[:9]) if frac else 0
    date, _, clock = head.partition("T")
    y, mo, d = (int(x) for x in date.split("-"))
    hh, mm, ss = (int(x) for x in clock.split(":"))
    days = _days_from_civil(y, mo, d)
    return (days * 86400 + hh * 3600 + mm * 60 + ss) * 1_000_000_000 + frac_ns


def _days_from_civil(y: int, m: int, d: int) -> int:
    """Howard Hinnant's days_from_civil — UTC days since 1970-01-01, pure integer math."""
    y -= m <= 2
    era = (y if y >= 0 else y - 399) // 400
    yoe = y - era * 400
    doy = (153 * (m + (-3 if m > 2 else 9)) + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


# --------------------------------------------------------------------------- data model

# Canonical event-type buckets. `user.events` emits DT RUM event types; we normalise the common
# spellings so downstream logic keys on a stable vocabulary. Unknown types pass through lower-cased.
_TYPE_MAP = {
    "view": "view", "page_view": "view", "pageview": "view", "load": "view",
    "user_action": "action", "action": "action", "useraction": "action", "click": "action",
    "request": "request", "xhr": "request", "fetch": "request", "resource": "request",
    "error": "error", "js_error": "error", "crash": "error",
}


def norm_type(raw) -> str:
    return _TYPE_MAP.get(str(raw or "").strip().lower().replace(" ", "_"), str(raw or "").strip().lower())


@dataclass
class RumEvent:
    session_id: str
    ts_ns: int
    etype: str                 # normalised: view | action | request | error | <passthrough>
    name: str                  # action/page name (view/action) — the use-case label
    duration_ms: float = 0.0   # event duration if present (ms)
    endpoint: str = ""         # request target/url (REQUEST events) — the per-endpoint merge key
    app: str = ""


@dataclass
class RumJourney:
    session_id: str
    events: list[RumEvent] = field(default_factory=list)
    think_ms: list[float] = field(default_factory=list)  # len == len(events)-1, clipped >= 0
    duration_s: float = 0.0
    app: str = ""

    @property
    def length(self) -> int:
        return len(self.events)

    def sequence(self, *, kinds: tuple[str, ...] = ("view", "action")) -> list[str]:
        """Ordered use-case labels (default: views + user actions, the human journey).

        Request/error events are excluded by default so the template is the navigation the user
        performed, not every XHR it fired; pass kinds to widen.
        """
        return [e.name or e.endpoint or e.etype
                for e in self.events if e.etype in kinds and (e.name or e.endpoint or e.etype)]


# --------------------------------------------------------------------------- parse + stitch

def parse_rows(rows: list[dict]) -> list[RumEvent]:
    """DQL record dicts -> RumEvent list. Tolerant of the common `user.events` field namings so
    confirming the live projection is a tweak, not a rewrite. Rows without a session id are
    dropped (we only stitch where the RUM session key exists).
    """
    out: list[RumEvent] = []
    for r in rows:
        sid = r.get("dt.rum.session.id") or r.get("session.id") or r.get("sessionId")
        if not sid:
            continue
        ts = r.get("timestamp")
        if ts is None:
            ts = r.get("start_time")
        if ts is None:
            ts = r.get("time")
        if ts is None:
            continue  # ts may legitimately be 0 (epoch) — only a missing key drops the row
        dur = r.get("duration") or r.get("duration_ms") or 0
        # duration may be ns (int from DQL) or already ms — heuristic: > 1e6 treated as ns
        dur_val = float(dur or 0)
        dur_ms = dur_val / 1e6 if dur_val > 1e6 else dur_val
        out.append(RumEvent(
            session_id=str(sid),
            ts_ns=iso_to_ns(ts),
            etype=norm_type(r.get("event.type") or r.get("eventType") or r.get("type")),
            name=str(r.get("event.name") or r.get("eventName") or r.get("name")
                     or r.get("dt.rum.action.name") or ""),
            duration_ms=dur_ms,
            endpoint=str(r.get("endpoint") or r.get("url") or r.get("request.url")
                         or r.get("http.url") or ""),
            app=str(r.get("application") or r.get("app") or r.get("dt.rum.application.name") or ""),
        ))
    return out


def stitch_journeys(events: list[RumEvent]) -> list[RumJourney]:
    """Group `user.events` rows by `dt.rum.session.id`, order by timestamp, derive per-action
    think-times + session duration. Returned sorted by session_id for determinism.

    think-time(i) = ts(i+1) - (ts(i) + duration(i)), clipped at 0 — the *measured* inter-action
    pacing (the exact think-time span-order inference and `user.sessions` mean-estimate cannot
    see). When an event carries no duration the gap is ts(i+1) - ts(i).
    """
    by_sid: dict[str, list[RumEvent]] = {}
    for e in events:
        by_sid.setdefault(e.session_id, []).append(e)

    journeys: list[RumJourney] = []
    for sid in sorted(by_sid):
        items = sorted(by_sid[sid], key=lambda e: e.ts_ns)
        think: list[float] = []
        for i in range(1, len(items)):
            prev, cur = items[i - 1], items[i]
            end_prev_ns = prev.ts_ns + int(prev.duration_ms * 1e6)
            think.append(max(0.0, (cur.ts_ns - end_prev_ns) / 1e6))  # -> ms
        if items:
            last = items[-1]
            duration_s = (last.ts_ns + int(last.duration_ms * 1e6) - items[0].ts_ns) / 1e9
        else:
            duration_s = 0.0
        journeys.append(RumJourney(session_id=sid, events=items, think_ms=think,
                                   duration_s=duration_s,
                                   app=next((e.app for e in items if e.app), "")))
    return journeys


# --------------------------------------------------------------------------- distributions

def _pctl(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return 0.0
    n = len(sorted_vals)
    return sorted_vals[min(n - 1, int(p / 100 * n))]


def think_ms_samples(journeys: list[RumJourney]) -> list[float]:
    out: list[float] = []
    for j in journeys:
        out.extend(j.think_ms)
    return out


def think_time_spec(journeys: list[RumJourney], *, mode: str = "empirical",
                    max_samples: int = 256) -> dict | None:
    """Schema-valid `thinkTime` object (schema.json#/definitions/thinkTime) from measured
    per-action think-times. Returns None when there is no signal (all single-action sessions) so
    the step carries no think-time rather than a fabricated one. Mirrors
    `session_stitch.think_time_spec` so a RUM-primary journey and a span-stitched one are
    interchangeable in the renderer.
    """
    samples = think_ms_samples(journeys)
    if not samples:
        return None
    s = sorted(samples)
    mean, mn, mx = round(statistics.mean(s), 3), round(s[0], 3), round(s[-1], 3)
    if mode == "exponential":
        return {"distribution": "exponential", "meanMs": mean}
    if len(s) > max_samples:
        step = len(s) / max_samples
        s = [s[int(i * step)] for i in range(max_samples)]
    return {"distribution": "empirical", "meanMs": mean, "minMs": mn, "maxMs": mx,
            "samples": [round(v, 1) for v in s]}


# --------------------------------------------------------------------------- journey templates

@dataclass
class JourneyTemplate:
    sequence: tuple[str, ...]   # ordered use-case labels — the exact action sequence
    sessions: int               # how many sessions walked this exact sequence
    weight: float = 0.0         # share of stitched sessions (filled by journey_templates)
    think_ms_mean: float = 0.0  # mean measured think-time across member sessions


def journey_templates(journeys: list[RumJourney], *,
                      kinds: tuple[str, ...] = ("view", "action"),
                      min_sessions: int = 1) -> list[JourneyTemplate]:
    """Collapse stitched journeys into **ordered-sequence** templates: the distinct action
    sequences users actually walked, each weighted by how many sessions walked it. This is the
    RUM-primary journey set the merge treats as authoritative — exact order + real use-cases,
    not the span-side set-similarity clustering (`clustering.py`), which has no ordering.

    `min_sessions` drops long-tail singleton paths from the emitted set (their weight still
    counts in the denominator so the kept weights stay honest).
    """
    buckets: dict[tuple[str, ...], list[RumJourney]] = {}
    for j in journeys:
        seq = tuple(j.sequence(kinds=kinds))
        if not seq:
            continue
        buckets.setdefault(seq, []).append(j)

    total = sum(len(v) for v in buckets.values())
    templates: list[JourneyTemplate] = []
    for seq, members in buckets.items():
        if len(members) < min_sessions:
            continue
        thinks = [t for m in members for t in m.think_ms]
        templates.append(JourneyTemplate(
            sequence=seq,
            sessions=len(members),
            weight=round(len(members) / total, 4) if total else 0.0,
            think_ms_mean=round(statistics.mean(thinks), 3) if thinks else 0.0,
        ))
    templates.sort(key=lambda t: t.sessions, reverse=True)
    return templates


# --------------------------------------------------------------------------- per-endpoint rates

def endpoint_rates(events: list[RumEvent], window_s: float) -> dict[str, float]:
    """Per-endpoint RUM request rate (req/s) over the window, from REQUEST events. This is the
    finer, *authoritative* RUM side `source_merge.reconcile` wants (vs the app/journey-grain
    `user.sessions` estimate). Keyed on `endpoint`; canonicalisation (templating path ids, etc.)
    is the caller's job so this stays pure — pass already-canonical endpoints for a clean join
    against span rates.
    """
    if window_s <= 0:
        return {}
    counts: dict[str, int] = {}
    for e in events:
        if e.etype != "request" or not e.endpoint:
            continue
        counts[e.endpoint] = counts.get(e.endpoint, 0) + 1
    return {k: round(v / window_s, 6) for k, v in counts.items()}


def per_endpoint_overlap(events: list[RumEvent], span_rates: dict[str, float],
                        window_s: float) -> dict:
    """ISI-5719 one-call bridge: stitch per-endpoint RUM rates from `user.events`, then reconcile
    against span rates via the (already-tested) `source_merge` reconciler — yielding the
    per-endpoint overlap + extrapolation factors (common → RUM-primary × factor, span-only → HTTP
    scenario, rum-only → dropped). Import is local so this module stays importable standalone.
    """
    import source_merge  # noqa: E402  (local import keeps rum_events dependency-free to import)
    rum_rates = endpoint_rates(events, window_s)
    return source_merge.merge_plan(rum_rates, span_rates)
