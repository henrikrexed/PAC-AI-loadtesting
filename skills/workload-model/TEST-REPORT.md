# workload-model skill — test evidence (ISI-5630)

*Rev 2, 2026-10-09. Revised after board feedback: journeys are now **behavioral archetypes**
(Buyer vs Browser), reconstructed from the trace span-tree, not endpoint clusters. Every
result is reproducible: `cd skills/workload-model && python3 -m pytest tests/ -v`; live runs use
`dtctl` against tenant **oat05854** (`dynatrace-dev` context).*

## 0. What changed (board feedback)

> "the 5 scenarios are wrong: technically it should be a buyer buying a product or products and
> placing an order, and a user purely searching and browsing. it sounds like we extracted
> individual spans."

Correct. The previous output clustered **individual entry operations** (one locust task = one
HTTP action) into endpoint buckets. A user *journey* is a multi-step business flow. The skill now
groups by **business outcome** (`archetypes.py`): does the flow place an order (reach an
order-terminal service)? → **Buyer** (browse → add-to-cart → checkout → pay → ship) vs
**Browser** (search/browse, no order). Each journey's `steps[]` is the ordered sequence
reconstructed from the trace span-tree (`collectArray` over `sort start_time asc`).

## 1. Unit + gate + archetype suite — 34 passed

```
python3 -m pytest tests/ -v   →   34 passed
```
clustering (9) · shaping (9) · G0 gate (9) · **archetypes (7)**: order-placing signal is
structural, exactly two archetypes, Buyer contains only order-placing ops, add-to-cart lands in
Browser (cart without order), weights partition to full coverage, Buyer steps are a multi-step
funnel with G2 correlates, Browser steps are read-only.

## 2. The two journeys emitted (live oat05854, -3h)

**Buyer — browse, add to cart, place order** (weight 0.067, reconstructed 4-step HTTP flow):
```
s1 GET  /api/products/[productId]/index
s2 POST /api/cart          [dependsOn s1; correlates productId <- s1.body $.id]
s3 GET  /api/cart          [correlates session cookie <- s2]
s4 POST /api/checkout      [dependsOn s2; correlates session cookie <- s2]
```
Backend funnel behind s4 (reconstructed, reach 12): `PlaceOrder → GetCart → GetProduct×N →
Convert×N → shipping /get-quote → payment Charge → ship-order → EmptyCart → email`.

**Browser — search & browse, no order** (weight 0.933, 6-step read-only flow):
```
GET / → GET /api/products/[productId] → GET /api/data (ads) →
GET /api/recommendations → GET /api/product-reviews/[productId] →
POST /api/product-ask-ai-assistant/[productId]
```
Weights sum 1.0, coverage 100%. **G0: 12/12 PASS.**

## 3. Fresh live run — proves it's live, not canned

Re-pulled a **new -6h window** and ran the archetype reconstruction on it:

| archetype | places order | -3h weight | -6h fresh-live weight | ops folded |
|---|---|---|---|---|
| Browser | no | 0.933 | 0.936 | 8 |
| Buyer | yes | 0.067 | 0.064 | 2 |

Stable two-archetype split, window-appropriate weights, coverage 1.000.

## 4. G0 gate — passes on good, blocks on bad

```
PASS   real committed artifact
BLOCK  ACCEPTANCE #4: accesslog unknown + no caveat   -> accesslog-availability
BLOCK  too many journeys (8 > 6)                       -> journey-count
BLOCK  Little's Law from driver wrapper (ratio 7.4)    -> littles-law
BLOCK  dependsOn without correlates (G2)               -> correlates
BLOCK  cacheProfile missing keyCardinality (G4)        -> cache-profile
BLOCK  coverage below 0.80                             -> coverage
BLOCK  DQL not attested run-live                        -> dql-live
```

## 5. Honest limit (R5)

The locust driver carries no persistent session id on browse spans (`app.user.id` appears only
on `cart`/`checkout`), so browse→buy cannot be chained across independent tasks. The Buyer
archetype is reconstructed from the self-contained `checkout_*` traces (which internally
browse→cart→checkout). A production front-end with a `session.id` cookie would let SCOPE chain
full end-user sessions directly — recorded as a caveat in the proposal.
