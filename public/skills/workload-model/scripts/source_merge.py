"""SCOPE §3.1 step 2c — dual-source merge: RUM user sessions ⟗ spans.

Board directive (2026-10-12): *"do both-sides analysis — RUM data and span data — then merge.
If the requests are common with RUM, use mainly the user session (but beware of the sampling
applied, so extrapolate). For the spans having no match with RUM, generate an HTTP-based
scenario."*

This module is the deterministic reconciler that encodes exactly that. It is **pure** — the
caller runs the two DQL passes and injects per-key rates:
  * `rum_rates`  — key → observed rate from `user.sessions`/`user.events` (RUM; may be sampled).
  * `span_rates` — key → observed rate from `spans` (server-side; unsampled on this tenant,
    `dt.system.sampling_ratio == 1.0`).
A *key* is a request/endpoint identity common to both sides (e.g. `GET /api/cart`), or a
journey id. Matching/canonicalisation of keys is the caller's job (so this stays pure and
tenant-agnostic).

Merge rules (one per key):
  * **common (in both)** → `source="rum"`: the RUM user session is primary (real ordered journey
    + think-times). **Extrapolate** its volume by `factor = span_rate / rum_rate` so the sampled
    RUM rate is scaled up to the unsampled span-observed truth. This simultaneously *measures* the
    RUM effective sampling (no separate sampling-rate config needed) and corrects for it.
  * **span-only (no RUM match)** → `source="span"`: generate an HTTP span-order scenario
    (tiers 2a/2b) — backend/internal calls and non-browser apps the RUM agent never sees.
  * **rum-only (in RUM, not spans)** → **DROPPED** (deliberate decision): a key
    with no server span has nothing to drive server-side, so it is not modelled. The count of
    dropped keys is reported in the summary for auditability, but no entry is emitted.

Open dependency: the authoritative per-endpoint RUM rates come from `user.events`, which is
gated on OAuth scope `storage:user.events:read` (403 today). Until then the reconciler runs on
whatever RUM keys are available (app/journey granularity from `user.sessions`); the algorithm
and the extrapolation math are unchanged when the finer keys arrive.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, asdict


@dataclass
class MergeEntry:
    key: str
    source: str                      # "rum" | "span"
    rumRate: float | None
    spanRate: float | None
    extrapolationFactor: float | None  # span/rum for common keys; applied to RUM-primary volume
    rationale: str

    def to_dict(self) -> dict:
        return asdict(self)


def reconcile(rum_rates: dict[str, float], span_rates: dict[str, float]) -> list[MergeEntry]:
    """Merge RUM and span per-key rates into a routing plan (one MergeEntry per key).

    Returns entries sorted by effective rate (the volume that will actually be driven) desc, so
    the dominant workload is first. Pure and deterministic.
    """
    entries: list[MergeEntry] = []
    for key in sorted(set(rum_rates) | set(span_rates)):
        r = rum_rates.get(key)
        s = span_rates.get(key)
        if r and s:
            factor = round(s / r, 4) if r else None
            entries.append(MergeEntry(
                key, "rum", round(r, 6), round(s, 6), factor,
                f"common: RUM user-session primary; scale RUM rate ×{factor} to the unsampled "
                f"span-observed volume ({s:g}/s).",
            ))
        elif s:
            entries.append(MergeEntry(
                key, "span", None, round(s, 6), None,
                "no RUM match → span-order HTTP scenario (tiers 2a/2b).",
            ))
        # else: rum-only (no server span) → DROPPED by design; not modelled.
    entries.sort(key=lambda e: _effective_rate(e), reverse=True)
    return entries


def _effective_rate(e: MergeEntry) -> float:
    """The rate that will actually be driven: span truth for rum/span common & span-only,
    RUM rate for rum-only."""
    if e.spanRate is not None:
        return e.spanRate
    return e.rumRate or 0.0


def merge_plan(rum_rates: dict[str, float], span_rates: dict[str, float]) -> dict:
    """Full merge plan + summary for the model/proposal and auditability."""
    entries = reconcile(rum_rates, span_rates)
    rum_primary = [e for e in entries if e.source == "rum"]
    span_fallback = [e for e in entries if e.source == "span"]
    factors = [e.extrapolationFactor for e in rum_primary if e.extrapolationFactor]
    dropped_rum_only = sorted(set(rum_rates) - set(span_rates))
    total_rate = sum(_effective_rate(e) for e in entries) or 1.0
    rum_rate = sum(_effective_rate(e) for e in rum_primary)
    return {
        "entries": [e.to_dict() for e in entries],
        "summary": {
            "keys": len(entries),
            "rumPrimaryKeys": len(rum_primary),
            "spanFallbackKeys": len(span_fallback),
            "droppedRumOnlyKeys": len(dropped_rum_only),  # rum-only is dropped, not modelled
            "rumDrivenShare": round(rum_rate / total_rate, 4),
            "meanExtrapolationFactor": round(statistics.mean(factors), 4) if factors else None,
            "extrapolationFactorRange": [round(min(factors), 4), round(max(factors), 4)] if factors else None,
        },
    }
