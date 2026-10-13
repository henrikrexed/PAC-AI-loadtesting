# wkf10640 / Astroshop — RUM-primary ordered journeys (ISI-5719)

Live `user.events` extraction, 24h, **18,773 sessions**. Scope `storage:user.events:read` granted 2026-10-13 (board token).

## Ordered journey templates (16 distinct, top 10)

| sessions | weight | steps | sequence |
|---:|---:|---:|---|
| 15,588 | 83.1% | 7 | `/ > /product/:id: > /cart > / > /product/:id: > /cart > /cart/checkout/:uuid:` |
| 2,482 | 13.2% | 6 | `/ > /product/:id: > /cart > / > /product/:id: > /cart` |
| 408 | 2.2% | 5 | `/ > /product/:id: > /cart > / > /product/:id:` |
| 171 | 0.9% | 7 | `/ > /product/:id: > / > /cart > /product/:id: > /cart > /cart/checkout/:uuid:` |
| 56 | 0.3% | 6 | `/ > /product/:id: > / > /cart > /product/:id: > /cart` |
| 22 | 0.1% | 2 | `/ > /product/:id:` |
| 13 | 0.1% | 4 | `/ > /product/:id: > /cart > /` |
| 10 | 0.1% | 1 | `/` |
| 9 | 0.1% | 5 | `/ > /product/:id: > / > /cart > /product/:id:` |
| 2 | 0.0% | 2 | `/ > /` |

## Measured per-page think-time (view dwell, ms)

| page | n | p50 | p90 | p99 | mean |
|---|---:|---:|---:|---:|---:|
| `/` | 37,502 | 1773 | 3869 | 12255 | 2369 |
| `/product/:id:` | 37,484 | 988 | 2351 | 5591 | 3589 |
| `/cart` | 37,044 | 1431 | 2829 | 6682 | 1304 |
| `/cart/checkout/:uuid:` | 15,763 | 831 | 988 | 1398 | 3045 |

## Per-endpoint overlap & extrapolation (RUM ⟗ spans, `/api/*`)

| endpoint | source | RUM req/s | span req/s | factor |
|---|---|---:|---:|---:|
| `/api/images/:file:` | rum | 11.090 | 11.737 | 1.06 |
| `/api/cart` | rum | 1.608 | 2.066 | 1.28 |
| `/api/recommendations` | rum | 1.873 | 2.035 | 1.09 |
| `/api/data` | rum | 1.315 | 1.446 | 1.10 |
| `/api/shipping` | rum | 0.741 | 0.781 | 1.05 |
| `/api/products` | rum | 0.651 | 0.743 | 1.14 |
| `/api/products/:id:` | rum | 2.521 | 0.511 | 0.20 |
| `/api/currency` | rum | 0.217 | 0.409 | 1.88 |
| `/api/checkout` | span | — | 0.250 | — |
| `/api/cart/invalid-chaos-endpoint` | span | — | 0.007 | — |

**Summary:** 10 endpoints · 8 RUM-primary · 2 span-only · rumDrivenShare 0.9871 · mean extrapolation ×1.1016 (range [0.2025, 1.8845]).
