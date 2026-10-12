# DEMO-DIFF — one model, two tools (Astroshop frontend, wkf10640)

Source: `workload-model.json` rev 3 (`sha256:cdd5294…9639e3`), V1-approved.
Both renderers consume the **same** model and reproduce the **same** load contract.

## Shared contract (comes from the model, identical for both)
| Property | Value | From |
|---|---|---|
| Arrival model | open | `spec.arrivalProfile.model` |
| Envelope | ramp 162m → **peak 43.4/s** → 1m plateau → 17m ramp-down → 0 | `arrivalProfile.stages` |
| Journey mix | `browser` 0.9908 / `buyer` 0.0092 | `journeys[].weight` (real root-trace outcomes) |
| Concurrency anchor | Little's Law expected **3.6755** ≈ observed 3.6776 (ratio 0.9994) | `littlesLawCheck` |
| RUM→span extrapolation | **1.2735** (span 33.03/s ÷ RUM 25.94/s) | `merge-plan.json` |
| Payload (product) | Zipf, cardinality **10**, target hit-ratio 0.99, seed 42, synthetic keys (PII-free) | `payloads.product.cacheProfile` |
| Payload (checkout) | faker email/cc + weighted currency, seed 42 | `payloads.checkout` |
| Caps | maxRps 60 / maxVus 50 / maxDuration 45m | `spec.caps` |

## Same concern, two renderings
| Concern | k6 (`k6-synthesis`) | JMeter (`jmeter-synthesis`) |
|---|---|---|
| Open arrival | `executor: "ramping-arrival-rate"` | **Concurrency Thread Group** + **Throughput Shaping Timer** (jp@gc) |
| Per-journey rate | `stages` scaled ×weight — browser `29.24 → 43 → 38.93 → 0` | `load_profile` rows ×weight — browser `29.24 → 43 → 38.93 → 0` |
| Buyer rate | `0.27 → 0.4 → 0.36 → 0` | matching shaping rows (w=0.0092) |
| VU ceiling | `preAllocatedVUs 5 / maxVUs 8` (Little's Law, clamped to caps) | `TargetLevel` 5 (browser) / 1 (buyer) |
| Correlation (G2) | `chain.js` extract→inject, `fail()` + `chain_broken` counter on null | `JSONPostProcessor` + `RegexExtractor`, default `__CHAIN_BROKEN__` |
| Cache-avoidance payload | `payloads/product.json` (Zipf K=10) | `CSV Data Set` `data/product.csv` (Zipf K=10) |
| Synthetic identity (P4) | `syntheticParams()` → `baggage: synthetic=true` | Header Manager `baggage: synthetic=true` |
| Static gate | **V2a PASS** (7 checks) | **J1–J7 PASS** |

## The one-liner
> The workload model is the **program**. k6 and JMeter are two **compiler back-ends**.
> Same arrival envelope, same journey mix, same correlation, same synthetic baggage —
> emitted into two tools with **zero hand-authoring**. *Guns. Lots of guns.*

> Note: Zipf key pools use synthetic `productId-NNNNNN` keys (cardinality 10, PII-free) rather than
> the raw catalog IDs — identical scheme in both tools, so the production cache hit-ratio is reproduced,
> not the real identifiers. Deliberate, consistent, and part of the "same model" guarantee.
