"""Clustering (G1) tests — exercised on the synthetic example journey set."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import clustering as cl  # noqa: E402

FX = json.loads((Path(__file__).resolve().parent.parent / "fixtures" / "example_extract.json").read_text())


def _journeys():
    return [cl.Journey(op=j["op"], traces=j["traces"], svc_set=j["svc_set"]) for j in FX["journeys"]]


def test_five_named_scenarios():
    scenarios = cl.cluster(_journeys())
    names = {s.name for s in scenarios}
    assert names == {"Browse product page", "Cart", "Recommendations", "Checkout", "Home"}
    assert len(scenarios) == 5  # within the 1-6 cap


def test_browse_cluster_absorbs_ads_reviews_ai():
    scenarios = {s.name: s for s in cl.cluster(_journeys())}
    browse = scenarios["Browse product page"]
    assert set(browse.members) == {
        "user_browse_product", "user_get_ads", "user_get_product_reviews",
        "user_ask_product_ai_assistant",
    }


def test_cart_cluster_absorbs_view_cart():
    scenarios = {s.name: s for s in cl.cluster(_journeys())}
    assert set(scenarios["Cart"].members) == {"user_add_to_cart", "user_view_cart"}


def test_checkout_never_merges_despite_low_weight():
    scenarios = {s.name: s for s in cl.cluster(_journeys())}
    co = scenarios["Checkout"]
    assert set(co.members) == {"user_checkout_single", "user_checkout_multi"}
    assert co.reach >= cl.UNIQUE_REACH  # high-reach -> structurally unique, protected


def test_recommendations_stays_separate_on_stem_despite_high_jaccard():
    # recommendations svcSet is Jaccard>=0.6 with browse, but the op stem differs -> no merge
    scenarios = {s.name: s for s in cl.cluster(_journeys())}
    assert scenarios["Recommendations"].members == ["user_get_recommendations"]


def test_weights_sum_to_coverage():
    scenarios, coverage = cl.weight_scenarios(cl.cluster(_journeys()))
    assert abs(coverage - 1.0) < 1e-9
    assert abs(sum(s.weight for s in scenarios) - 1.0) < 1e-9


def test_jaccard_browse_vs_ads_is_exactly_point_six():
    browse = frozenset({"frontend", "load-generator", "frontend-proxy", "product-catalog"})
    ads = frozenset({"frontend", "load-generator", "frontend-proxy", "ad"})
    assert abs(cl.jaccard(browse, ads) - 0.6) < 1e-9


def test_cap_drops_tail_only_while_coverage_holds():
    # 8 synthetic singleton scenarios, top-heavy -> cap to 6 keeping >=0.80
    scen = [cl.Scenario(name=f"s{i}", traces=t, weight=0) for i, t in
            enumerate([50, 20, 10, 8, 6, 3, 2, 1])]
    scen, _ = cl.weight_scenarios(scen)
    kept, dropped, cov = cl.enforce_cap(scen)
    assert len(kept) == 6
    assert len(dropped) == 2
    assert cov >= cl.COVERAGE_MIN


def test_cap_raises_when_coverage_cannot_be_met():
    # flat long tail: top 6 of 20 equal scenarios cover only 0.30 -> must raise, not ship thin
    scen = [cl.Scenario(name=f"s{i}", traces=1, weight=0) for i in range(20)]
    scen, _ = cl.weight_scenarios(scen)
    try:
        cl.enforce_cap(scen)
    except ValueError:
        return
    raise AssertionError("expected enforce_cap to raise on sub-0.80 coverage")
