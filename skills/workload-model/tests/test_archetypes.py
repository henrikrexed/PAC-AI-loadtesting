"""Behavioral-archetype tests (G1 journey model) — Buyer vs Browser by business outcome."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import clustering as cl  # noqa: E402
import archetypes as ar  # noqa: E402

FX = json.loads((Path(__file__).resolve().parent.parent / "fixtures" / "oat05854_extract.json").read_text())


def _journeys():
    return [cl.Journey(op=j["op"], traces=j["traces"], svc_set=j["svc_set"]) for j in FX["journeys"]]


def test_places_order_signal_is_structural():
    assert ar.places_order({"frontend", "cart", "payment", "checkout"})
    assert not ar.places_order({"frontend", "product-catalog", "cart"})  # cart w/o checkout/payment
    # generalizes across naming
    assert ar.places_order({"order-processor"})
    assert ar.places_order({"checkoutservice"})


def test_two_archetypes_buyer_and_browser():
    a = ar.to_archetypes(_journeys())
    ids = {x.id for x in a}
    assert ids == {"buyer", "browser"}


def test_buyer_only_contains_order_placing_ops():
    a = {x.id: x for x in ar.to_archetypes(_journeys())}
    assert set(a["buyer"].members) == {"user_checkout_single", "user_checkout_multi"}
    # add_to_cart reaches cart but NOT payment/checkout -> browser, not buyer
    assert "user_add_to_cart" in a["browser"].members
    assert "user_browse_product" in a["browser"].members


def test_browser_is_majority_weight():
    a = {x.id: x for x in ar.to_archetypes(_journeys())}
    assert a["browser"].weight > a["buyer"].weight
    assert a["browser"].weight > 0.8  # read-only dominates traffic


def test_weights_partition_to_full_coverage():
    a = ar.to_archetypes(_journeys())
    assert abs(ar.coverage(a) - 1.0) < 1e-9


def test_buyer_steps_are_a_multistep_funnel_with_correlates():
    a = {x.id: x for x in ar.to_archetypes(_journeys(),
                                           buyer_steps=FX["buyer_steps"],
                                           browser_steps=FX["browser_steps"])}
    buyer = a["buyer"]
    ops = [s["operation"] for s in buyer.steps]
    # a real sequence: browse -> add to cart -> view cart -> checkout
    assert ops == ["GET /api/products/[productId]/index", "POST /api/cart",
                   "GET /api/cart", "POST /api/checkout"]
    # checkout step chains the cart session (G2) and depends on add-to-cart
    checkout = buyer.steps[-1]
    assert checkout["dependsOn"] == ["s2"]
    assert any(c["sourceStepId"] == "s2" for c in checkout["correlates"])


def test_browser_steps_are_readonly_no_order():
    a = {x.id: x for x in ar.to_archetypes(_journeys(),
                                           buyer_steps=FX["buyer_steps"],
                                           browser_steps=FX["browser_steps"])}
    browser = a["browser"]
    methods = [s["operation"].split()[0] for s in browser.steps]
    assert methods.count("GET") >= 4  # predominantly reads
    assert not any("checkout" in s["operation"] for s in browser.steps)
