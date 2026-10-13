"""SCOPE §3.1 step 2c tier (ii) — Path B: stitch sessions from OTel `session.id` on spans.

Grail-native session reconstruction. Closes the §11 **R5** "no notion of a session" gap
*without* any RUM / classic-token dependency. Path A (classic USQL/RUM-API adapter) is
not needed for this Grail-native path.

Where spans carry an OTel `session.id` (the OTel *session* semantic convention, propagated
as baggage), this layer:
  * groups spans by `session.id`,
  * orders them by start time → the **real per-session action sequence**,
  * diffs consecutive actions → **genuine inter-action think-times**, and
  * derives **session boundaries / length**,
feeding the §8.4 SequenceReconstructor with measured session chains instead of the
span-order *inference* of tiers 2a/2b. Where `session.id` is ABSENT nothing changes: the
span-order method is the fallback and the model records **0% session.id coverage** alongside
the span sampling ratio (§11 R1) so fidelity stays auditable.

Design mirrors `archetypes.py` / `shaping.py`: **no telemetry I/O here.** The caller runs the
DQL (`fetch spans | filter isNotNull(session.id) | fields session.id, start_time, duration,
service.name, span.name`) and injects the rows; everything here is pure and deterministic.

**App-agnostic by construction.** The mechanism keys only on `session.id` — it works for any
service that propagates it, browser front-ends *and* non-browser apps (e.g. an ad service's
browse sessions and a chat agent's conversation turns).
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field


def iso_to_ns(ts: str) -> int:
    """Parse an RFC3339 timestamp (`...Z`, up to ns precision) to integer epoch nanoseconds.

    Avoids `datetime` micro-truncation loss by splitting the fractional seconds manually so
    the full nanosecond resolution of Dynatrace span `start_time` survives.
    """
    ts = ts.strip().rstrip("Z")
    if "." in ts:
        head, frac = ts.split(".", 1)
    else:
        head, frac = ts, ""
    frac_ns = int((frac + "000000000")[:9]) if frac else 0
    # head = YYYY-MM-DDТHH:MM:SS
    date, _, clock = head.partition("T")
    y, mo, d = (int(x) for x in date.split("-"))
    hh, mm, ss = (int(x) for x in clock.split(":"))
    # days since epoch via a pure proleptic-Gregorian day count (no tz, UTC assumed)
    days = _days_from_civil(y, mo, d)
    secs = days * 86400 + hh * 3600 + mm * 60 + ss
    return secs * 1_000_000_000 + frac_ns


def _days_from_civil(y: int, m: int, d: int) -> int:
    """Howard Hinnant's days_from_civil — UTC days since 1970-01-01, pure integer math."""
    y -= m <= 2
    era = (y if y >= 0 else y - 399) // 400
    yoe = y - era * 400
    doy = (153 * (m + (-3 if m > 2 else 9)) + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


@dataclass(frozen=True)
class SessionSpan:
    """One span observed to carry a `session.id`."""
    session_id: str
    start_ns: int
    duration_ns: int
    service: str = ""
    operation: str = ""


@dataclass
class SessionChain:
    """One stitched session: its ordered actions + derived think-times + boundary facts."""
    session_id: str
    actions: list[SessionSpan] = field(default_factory=list)
    think_ms: list[float] = field(default_factory=list)  # clipped >= 0, len == len(actions)-1
    duration_s: float = 0.0                               # first.start -> last.end

    @property
    def length(self) -> int:
        return len(self.actions)


def parse_rows(rows: list[dict]) -> list[SessionSpan]:
    """DQL record dicts -> SessionSpan list. `start_time` ISO string, `duration` ns int/str.

    Tolerant of the two field namings DQL emits (`service.name`/`span.name` vs aliased).
    Rows with no `session.id` are dropped (Path B only stitches where the signal exists).
    """
    out: list[SessionSpan] = []
    for r in rows:
        sid = r.get("session.id") or r.get("sessionId")
        if not sid:
            continue
        out.append(SessionSpan(
            session_id=str(sid),
            start_ns=iso_to_ns(r["start_time"]) if isinstance(r["start_time"], str) else int(r["start_time"]),
            duration_ns=int(r.get("duration") or 0),
            service=str(r.get("service.name") or r.get("service") or ""),
            operation=str(r.get("span.name") or r.get("operation") or ""),
        ))
    return out


def stitch(spans: list[SessionSpan], *, max_gap_s: float | None = None) -> list[SessionChain]:
    """Group spans by `session.id`, order by start, derive think-times + session duration.

    think-time(i) = start(i+1) - end(i), clipped at 0 (concurrent/overlapping spans within a
    session — ~1% of ad chains — would otherwise go negative; a replayed think-time is never
    negative). Chains are returned sorted by session_id for determinism.

    `max_gap_s`: optional inactivity-timeout boundary. When set, a gap larger than it SPLITS
    one session.id into sub-chains (a reused/long-lived id spanning distinct visits). Default
    None → the `session.id` itself is the boundary (correct for the OTel session semconv).
    """
    by_sid: dict[str, list[SessionSpan]] = {}
    for s in spans:
        by_sid.setdefault(s.session_id, []).append(s)

    chains: list[SessionChain] = []
    for sid in sorted(by_sid):
        items = sorted(by_sid[sid], key=lambda s: s.start_ns)
        segments: list[list[SessionSpan]] = [[]]
        for i, sp in enumerate(items):
            if i and max_gap_s is not None:
                gap_s = (sp.start_ns - items[i - 1].start_ns) / 1e9
                if gap_s > max_gap_s:
                    segments.append([])
            segments[-1].append(sp)
        for seg in segments:
            chains.append(_chain(sid, seg))
    return chains


def _chain(sid: str, items: list[SessionSpan]) -> SessionChain:
    think: list[float] = []
    for i in range(1, len(items)):
        prev, cur = items[i - 1], items[i]
        end_prev_ns = prev.start_ns + prev.duration_ns
        think.append(max(0.0, (cur.start_ns - end_prev_ns) / 1e6))  # -> ms
    if items:
        last = items[-1]
        duration_s = (last.start_ns + last.duration_ns - items[0].start_ns) / 1e9
    else:
        duration_s = 0.0
    return SessionChain(session_id=sid, actions=items, think_ms=think, duration_s=duration_s)


# --------------------------------------------------------------------------- profiles

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
        "min": round(s[0], 3),
        "p50": round(_pctl(s, 50), 3),
        "p90": round(_pctl(s, 90), 3),
        "p99": round(_pctl(s, 99), 3),
        "max": round(s[-1], 3),
        "mean": round(statistics.mean(s), 3),
    }


def think_ms_samples(chains: list[SessionChain]) -> list[float]:
    """All clipped inter-action think-times (ms) across every stitched session."""
    out: list[float] = []
    for c in chains:
        out.extend(c.think_ms)
    return out


def think_time_stats(chains: list[SessionChain]) -> dict:
    """Think-time distribution (ms) — the measured pacing span-order inference cannot see."""
    return _dist(think_ms_samples(chains))


def session_length_stats(chains: list[SessionChain]) -> dict:
    """Actions-per-session and session-duration (s) distributions over stitched chains."""
    return {
        "sessions": len(chains),
        "actionsPerSession": _dist([float(c.length) for c in chains]),
        "durationSeconds": _dist([c.duration_s for c in chains]),
    }


def _exponential_fit(samples: list[float]) -> dict:
    """Mean-of-samples exponential fit + a crude fit indicator (median/mean ≈ ln2 ⇒ ~exp)."""
    if not samples:
        return {"meanMs": 0.0, "fit": "none"}
    mean = statistics.mean(samples)
    med = _pctl(sorted(samples), 50)
    ratio = (med / mean) if mean else 0.0
    # exponential has median = mean * ln2 ≈ 0.693 * mean
    fit = "exponential" if 0.55 <= ratio <= 0.85 else "skewed"
    return {"meanMs": round(mean, 3), "medianMeanRatio": round(ratio, 3), "fit": fit}


def think_time_spec(chains: list[SessionChain], *, mode: str = "empirical",
                    max_samples: int = 256) -> dict | None:
    """Build a schema-valid `thinkTime` object (schema.json#/definitions/thinkTime) from the
    stitched chains, to attach to a journey step. Returns None when there is no think-time
    signal (single-action sessions, e.g. a single-turn chat workflow) so the step simply
    carries no think-time rather than a fabricated one.

    mode="empirical": distribution:"empirical" + an evenly-strided sample of real think-times
                      (ms) plus mean/min/max — highest fidelity, replay draws from the real set.
    mode="exponential": distribution:"exponential" + meanMs — compact closed-form when the
                      sample is a clean exponential (see _exponential_fit).
    """
    samples = think_ms_samples(chains)
    if not samples:
        return None
    s = sorted(samples)
    mean, mn, mx = round(statistics.mean(s), 3), round(s[0], 3), round(s[-1], 3)
    if mode == "exponential":
        return {"distribution": "exponential", "meanMs": mean}
    # empirical: evenly stride down to <= max_samples to keep the model file bounded
    if len(s) > max_samples:
        step = len(s) / max_samples
        s = [s[int(i * step)] for i in range(max_samples)]
    return {"distribution": "empirical", "meanMs": mean, "minMs": mn, "maxMs": mx,
            "samples": [round(v, 1) for v in s]}


# --------------------------------------------------------------------------- coverage report

def session_coverage(per_service: list[dict]) -> dict:
    """Build the auditable §11-R1-adjacent coverage report recorded on the model `source`.

    Input: one dict per service from the coverage DQL —
      {"service": str, "totalSpans": int, "sessionSpans": int, "sessions": int,
       "meanActions": float (optional)}.
    Services with sessionSpans == 0 may be omitted or included (coveragePct 0).

    Output (attaches to metadata.source.sessionIdCoverage):
      {"hasSessionSignal": bool, "overallCoveragePct": float,
       "services": [{service, totalSpans, sessionSpans, sessions, coveragePct, meanActions}]}
    overallCoveragePct = Σ sessionSpans / Σ totalSpans over the reported services.
    """
    services = []
    tot = sess_spans = 0
    for r in per_service:
        total = int(r.get("totalSpans") or 0)
        ss = int(r.get("sessionSpans") or 0)
        tot += total
        sess_spans += ss
        services.append({
            "service": str(r["service"]),
            "totalSpans": total,
            "sessionSpans": ss,
            "sessions": int(r.get("sessions") or 0),
            "coveragePct": round(100.0 * ss / total, 2) if total else 0.0,
            **({"meanActions": round(float(r["meanActions"]), 3)} if r.get("meanActions") is not None else {}),
        })
    services.sort(key=lambda x: x["sessionSpans"], reverse=True)
    return {
        "hasSessionSignal": sess_spans > 0,
        "overallCoveragePct": round(100.0 * sess_spans / tot, 2) if tot else 0.0,
        "services": services,
    }


# --------------------------------------------------------------------------- CLI

def _cli_main(argv: list[str] | None = None) -> int:  # pragma: no cover - thin CLI
    """Standalone CLI.

    Rows come from this DQL (run it yourself; this tool never talks to your tenant):

        fetch spans, from: -24h
        | filter isNotNull(session.id)
        | fields session.id, start_time, duration, service.name, span.name

    Usage:
        python3 session_stitch.py stitch < rows.json [--max-gap-s 1800]
        python3 session_stitch.py cover  < coverage_rows.json
    """
    import argparse
    import json
    import sys

    ap = argparse.ArgumentParser(prog="session_stitch",
                                 description="Stitch OTel session.id spans into session chains + think-times")
    ap.add_argument("mode", choices=["stitch", "cover"],
                    help="stitch: chains + think-time/session-length stats from span rows; "
                         "cover: coverage report from per-service rows")
    ap.add_argument("input", nargs="?", default="-",
                    help="input JSON file (array of DQL record dicts); '-' = stdin")
    ap.add_argument("--max-gap-s", type=float, default=None,
                    help="optional inactivity timeout (s): larger gaps split a session.id into sub-chains")
    a = ap.parse_args(argv)
    rows = json.load(sys.stdin if a.input == "-" else open(a.input))
    if a.mode == "stitch":
        chains = stitch(parse_rows(rows), max_gap_s=a.max_gap_s)
        spec = think_time_spec(chains) or {}
        print(json.dumps({
            "sessionLength": session_length_stats(chains),
            "thinkTime": think_time_stats(chains),
            "thinkTimeSpec": spec,
        }, indent=2))
    else:
        print(json.dumps(session_coverage(rows), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli_main())
