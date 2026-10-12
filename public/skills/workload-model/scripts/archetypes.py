"""Behavioral-journey archetypes for the SCOPE stage (methodology §3.1 step 3, gate G1).

**Why this layer exists.** Clustering entry
operations by endpoint similarity (`clustering.py`) answers "which endpoints look alike",
but a *user journey* is a multi-step business flow, not a single span. The practical
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

# Services/operations whose presence in a trace means the flow reached a *terminal action
# class*. Matched as substrings (case-insensitive) so they generalize across tenants/naming.
# Commerce: an order was placed. The classifier below is domain-agnostic — swap the pattern
# set to model any binary behavioral split (see AGENTIC_TOOL_PATTERNS for the agent-app case
# validated on an agent-gateway generalization test).
ORDER_TERMINAL_PATTERNS = ("payment", "checkout", "charge", "placeorder", "order")
# Agentic apps: did the agent turn invoke a tool (ReAct loop) vs stay pure-LLM (conversational)?
AGENTIC_TOOL_PATTERNS = ("execute_tool", "tool.", "/tool", "function_call")


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


def reaches_terminal(svc_set, patterns: tuple[str, ...]) -> bool:
    """True if any element of the flow's downstream set matches a terminal-action pattern."""
    rx = re.compile("|".join(re.escape(p) for p in patterns), re.IGNORECASE)
    return any(rx.search(s) for s in svc_set)


def places_order(svc_set, *, patterns: tuple[str, ...] = ORDER_TERMINAL_PATTERNS) -> bool:
    """Commerce specialization: does the flow reach an order-terminal service?"""
    return reaches_terminal(svc_set, patterns)


def classify_by_terminal(
    journeys: list[Journey],
    *,
    patterns: tuple[str, ...],
    present: tuple[str, str],   # (id, name) for flows that reach the terminal action
    absent: tuple[str, str],    # (id, name) for flows that do not
    present_steps: list[dict] | None = None,
    absent_steps: list[dict] | None = None,
) -> list[Archetype]:
    """Domain-agnostic behavioral split by a terminal-action signal.

    Commerce (`to_archetypes`) and agentic apps (tool-using vs pure-LLM turns) are both just
    configurations of this one function — the §2.1 agnostic-engine thesis in code. Pure:
    step sequences are injected by the caller (reconstructed from the trace span-tree).
    """
    hit = Archetype(id=present[0], name=present[1], places_order=True, steps=present_steps or [])
    miss = Archetype(id=absent[0], name=absent[1], places_order=False, steps=absent_steps or [])
    for j in journeys:
        target = hit if reaches_terminal(j.svc_set, patterns) else miss
        target.members.append(j.op)
        target.traces += j.traces
        target.reach = max(target.reach, j.reach)
        target.svc_set = target.svc_set | frozenset(j.svc_set)
    result = [a for a in (hit, miss) if a.members]
    total = sum(a.traces for a in result) or 1
    for a in result:
        a.weight = a.traces / total
    result.sort(key=lambda a: a.weight, reverse=True)
    return result


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
    return classify_by_terminal(
        journeys,
        patterns=patterns,
        present=("buyer", "Buyer — browse, add to cart, place order"),
        absent=("browser", "Browser — search & browse (no order)"),
        present_steps=buyer_steps,
        absent_steps=browser_steps,
    )


def coverage(archetypes: list[Archetype]) -> float:
    """Cumulative weight retained (archetypes partition all journeys -> 1.0)."""
    return sum(a.weight for a in archetypes)
