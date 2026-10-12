"""Scenario clustering for the SCOPE stage (methodology §3.1 step 3, gate G1).

Reduce a ranked list of entry journeys to 1-6 named scenarios by merging journeys
that share BOTH a structural fan-out signature (Jaccard over the downstream service
set) AND a semantic op-name stem. Pure functions — the caller feeds the journey list
extracted from telemetry (G1-E query); no I/O here so the logic is unit-testable.

Normative merge rule (methodology §3.1 step 3, findings note §G1.2):
  two journeys merge iff
    (a) Jaccard(svcSet_a, svcSet_b) >= JACCARD_THRESHOLD  (default 0.6), AND
    (b) they share an op-name stem (or the operator confirms the grouping).
Structurally unique high-reach journeys (reach >= UNIQUE_REACH, e.g. checkout) are
NEVER merged even when low-weight — they are the highest-risk code paths.
Coverage (cumulative weight) must stay >= COVERAGE_MIN after merging; a tail is only
dropped while cumulative weight stays >= COVERAGE_MIN.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

JACCARD_THRESHOLD = 0.6
UNIQUE_REACH = 10
COVERAGE_MIN = 0.80
MAX_SCENARIOS = 6


@dataclass
class Journey:
    op: str                       # entry op name, e.g. "user_browse_product"
    traces: int                   # volume in the window
    svc_set: frozenset[str]       # downstream service set (G1-E)
    reach: float = 0.0            # avg downstream reach (|svc_set| proxy)

    def __post_init__(self) -> None:
        self.svc_set = frozenset(self.svc_set)
        if not self.reach:
            self.reach = float(len(self.svc_set))


@dataclass
class Scenario:
    name: str
    members: list[str] = field(default_factory=list)
    member_sets: list[frozenset[str]] = field(default_factory=list)
    traces: int = 0
    reach: float = 0.0
    svc_set: frozenset[str] = frozenset()
    weight: float = 0.0           # share of covered traffic, filled by weight_scenarios


def jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    """Jaccard similarity of two downstream service sets (full sets, as returned by G1-E).

    Computed on the full svcSet — the common entry-path hops (frontend/driver/proxy) are
    *kept* — e.g. a live-validated clustering where browse+ads merged at
    exactly J=0.6 (3 shared of 5 union). Excluding them would zero out legitimate merges.
    """
    sa, sb = frozenset(a), frozenset(b)
    if not sa and not sb:
        return 1.0
    union = sa | sb
    return len(sa & sb) / len(union) if union else 1.0


def op_stem(op: str) -> str:
    """Semantic stem of an op name used for the (b) half of the merge rule.

    `user_browse_product` -> `browse`; `user_add_to_cart` / `user_view_cart` -> `cart`;
    `user_checkout_single` -> `checkout`. Deliberately coarse: it groups page-render and
    cart ops while keeping checkout / recommendations / home distinct. Operators may
    override by passing an explicit stem map to :func:`cluster`.
    """
    s = op
    for prefix in ("user_", "get_", "post_"):
        if s.startswith(prefix):
            s = s[len(prefix):]
    # cart family
    if "cart" in s:
        return "cart"
    if s.startswith("checkout"):
        return "checkout"
    if s.startswith("browse") or s.startswith("ads") or s.startswith("get_ads") \
            or "product_reviews" in s or "reviews" in s or "ask_product" in s or "ads" in s:
        return "browse"
    if "recommend" in s:
        return "recommendations"
    if s in ("index", "home"):
        return "home"
    # fall back to the first token
    return s.split("_")[0]


SCENARIO_NAMES = {
    "browse": "Browse product page",
    "cart": "Cart",
    "recommendations": "Recommendations",
    "checkout": "Checkout",
    "home": "Home",
}


def cluster(
    journeys: list[Journey],
    *,
    threshold: float = JACCARD_THRESHOLD,
    unique_reach: int = UNIQUE_REACH,
    stem_fn=op_stem,
    confirmed_groups: dict[str, str] | None = None,
) -> list[Scenario]:
    """Merge journeys into named scenarios per the §3.1 step-3 rule.

    `confirmed_groups` maps an op name to an operator-confirmed stem, satisfying the
    "or the operator confirms the semantic grouping" clause without loosening Jaccard.
    Returns scenarios sorted by traces desc.
    """
    confirmed_groups = confirmed_groups or {}
    buckets: dict[str, Scenario] = {}
    singletons: list[Scenario] = []

    for j in sorted(journeys, key=lambda x: x.traces, reverse=True):
        stem = confirmed_groups.get(j.op, stem_fn(j.op))
        # structurally unique high-reach journeys never merge
        if j.reach >= unique_reach:
            # group checkout_single + checkout_multi (same stem, both high reach) together,
            # but keep the whole stem isolated from everything else.
            key = f"__unique__{stem}"
        else:
            key = stem

        if key in buckets:
            sc = buckets[key]
            # (a) Jaccard gate against the MOST-similar existing member (not the growing
            # union, which would drift as the cluster absorbs members), (b) stem already equal
            best = max((jaccard(ms, j.svc_set) for ms in sc.member_sets), default=0.0)
            if best >= threshold or key.startswith("__unique__"):
                _absorb(sc, j)
                continue
            # same stem but fan-out diverged -> new singleton cluster
            singletons.append(_new_scenario(j, stem))
        else:
            sc = _new_scenario(j, stem)
            buckets[key] = sc

    scenarios = list(buckets.values()) + singletons
    scenarios.sort(key=lambda s: s.traces, reverse=True)
    return scenarios


def _new_scenario(j: Journey, stem: str) -> Scenario:
    return Scenario(
        name=SCENARIO_NAMES.get(stem, stem.replace("_", " ").title()),
        members=[j.op],
        member_sets=[j.svc_set],
        traces=j.traces,
        reach=j.reach,
        svc_set=j.svc_set,
    )


def _absorb(sc: Scenario, j: Journey) -> None:
    sc.members.append(j.op)
    sc.member_sets.append(j.svc_set)
    sc.traces += j.traces
    sc.reach = max(sc.reach, j.reach)
    sc.svc_set = sc.svc_set | j.svc_set


def weight_scenarios(scenarios: list[Scenario]) -> tuple[list[Scenario], float]:
    """Assign each scenario its share of total journey traffic; return (scenarios, coverage).

    Coverage = cumulative weight retained. All scenarios are kept here (caller applies the
    >6 / <0.80 tail-drop via :func:`enforce_cap`).
    """
    total = sum(s.traces for s in scenarios) or 1
    for s in scenarios:
        s.weight = s.traces / total
    return scenarios, sum(s.weight for s in scenarios)


def enforce_cap(
    scenarios: list[Scenario],
    *,
    max_scenarios: int = MAX_SCENARIOS,
    coverage_min: float = COVERAGE_MIN,
) -> tuple[list[Scenario], list[Scenario], float]:
    """Keep <= max_scenarios while cumulative weight stays >= coverage_min.

    Drops the lowest-weight tail. Returns (kept, dropped, coverage_of_kept).
    Raises ValueError if the top `max_scenarios` cannot reach `coverage_min` (caller must
    surface this as a G0 failure rather than silently shipping thin coverage).
    """
    ordered = sorted(scenarios, key=lambda s: s.weight, reverse=True)
    if len(ordered) <= max_scenarios:
        return ordered, [], sum(s.weight for s in ordered)

    kept = ordered[:max_scenarios]
    dropped = ordered[max_scenarios:]
    coverage = sum(s.weight for s in kept)
    if coverage < coverage_min:
        raise ValueError(
            f"top {max_scenarios} scenarios cover only {coverage:.3f} < {coverage_min} "
            "— cannot cap to <=6 without losing required coverage"
        )
    return kept, dropped, coverage
