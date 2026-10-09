"""Behavioral-journey archetypes for the SCOPE stage (methodology §3.1 step 3, gate G1).

**Why this layer exists (board feedback on ISI-5630, 2026-10-09).** Clustering entry
operations by endpoint similarity (`clustering.py`) answers "which endpoints look alike",
but a *user journey* is a multi-step business flow, not a single span. The board's reality
test for the astronomy shop: there are two behavioral archetypes —

  * **Buyer** — searches/browses products, adds to a cart, and *places an order* (a
    transactional funnel: browse -> add-to-cart -> checkout -> pay -> ship).
  * **Browser** — searches and browses only; never places an order (read-only exploration,
    incl. cart-building that is abandoned).

The distinguishing signal is **business outcome**: does the flow reach an order-terminal
service (payment / checkout / order / charge)? That is detected structurally from the
trace's downstream service set — not hard-coded per tenant. Each archetype carries the
ordered, telemetry-reconstructed step sequence (the real HTTP calls a driver must replay),
so `steps[]` is a genuine journey, not a bag of spans.

This layer runs BEFORE / ABOVE the Jaccard sub-clustering: first split by outcome into
behavioral journeys; if one archetype still fans into too many structurally distinct flows,
`clustering.cluster()` can sub-split it while staying within the <=6 cap.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from clustering import Journey

# Services whose presence in a trace's downstream set means an order was placed.
# Matched as substrings (case-insensitive) so it generalizes across tenants /
# naming schemes (payment-svc, checkoutservice, order-processor, ...).
ORDER_TERMINAL_PATTERNS = ("payment", "checkout", "charge", "placeorder", "order")


@dataclass
class Archetype:
    id: str                         # "buyer" | "browser" | ...
    name: str                       # human-legible
    places_order: bool
    members: list[str] = field(default_factory=list)   # entry ops folded in
    traces: int = 0
    reach: float = 0.0
    svc_set: frozenset[str] = frozenset()
    steps: list[dict] = field(default_factory=list)    # ordered, reconstructed flow
    weight: float = 0.0


def places_order(svc_set, *, patterns: tuple[str, ...] = ORDER_TERMINAL_PATTERNS) -> bool:
    """True if the downstream service set reaches an order-terminal service."""
    rx = re.compile("|".join(patterns), re.IGNORECASE)
    return any(rx.search(s) for s in svc_set)


def to_archetypes(
    journeys: list[Journey],
    *,
    patterns: tuple[str, ...] = ORDER_TERMINAL_PATTERNS,
    buyer_steps: list[dict] | None = None,
    browser_steps: list[dict] | None = None,
) -> list[Archetype]:
    """Fold entry journeys into behavioral archetypes keyed on business outcome.

    `buyer_steps` / `browser_steps` are the ordered step sequences reconstructed from the
    trace span-tree (the `collectArray(... sort start_time asc)` DQL). They are injected so
    this stays a pure function — the caller runs the reconstruction query and passes results.
    Returns archetypes sorted by weight desc, each with its summed traces and merged svc_set.
    """
    buyer = Archetype(id="buyer", name="Buyer — browse, add to cart, place order",
                      places_order=True, steps=buyer_steps or [])
    browser = Archetype(id="browser", name="Browser — search & browse (no order)",
                        places_order=False, steps=browser_steps or [])

    for j in journeys:
        target = buyer if places_order(j.svc_set, patterns=patterns) else browser
        target.members.append(j.op)
        target.traces += j.traces
        target.reach = max(target.reach, j.reach)
        target.svc_set = target.svc_set | frozenset(j.svc_set)

    result = [a for a in (buyer, browser) if a.members]
    total = sum(a.traces for a in result) or 1
    for a in result:
        a.weight = a.traces / total
    result.sort(key=lambda a: a.weight, reverse=True)
    return result


def coverage(archetypes: list[Archetype]) -> float:
    """Cumulative weight retained (archetypes partition all journeys -> 1.0)."""
    return sum(a.weight for a in archetypes)
