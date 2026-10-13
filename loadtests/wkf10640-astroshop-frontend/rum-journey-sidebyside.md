# wkf10640 / Astroshop — RUM-primary ordered journeys (ISI-5719)

_otel-demo e-commerce._ Live `user.events`, 24h, **18,773 sessions**.

## Ordered journey templates (16 distinct, top 8)

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

## Measured per-page think-time (view dwell, ms)

| page | n | p50 | p90 | mean |
|---|---:|---:|---:|---:|
| `/` | 37,502 | 1773 | 3869 | 2369 |
| `/product/:id:` | 37,484 | 988 | 2351 | 3589 |
| `/cart` | 37,044 | 1431 | 2829 | 1304 |
| `/cart/checkout/:uuid:` | 15,763 | 831 | 988 | 3045 |

## Per-endpoint overlap & extrapolation (RUM ⟗ spans)

| endpoint | source | RUM req/s | span req/s | factor |
|---|---|---:|---:|---:|
| `/oteldemo.CartService/GetCart` | span | — | 2.295 | — |
| `/api/cart` | rum | 1.617 | 2.075 | 1.28 |
| `/api/recommendations` | rum | 1.883 | 2.046 | 1.09 |
| `/api/data` | rum | 1.322 | 1.453 | 1.10 |
| `/get-quote` | span | — | 1.036 | — |
| `/getquote` | span | — | 1.036 | — |
| `/api/shipping` | rum | 0.744 | 0.785 | 1.05 |
| `/api/products` | rum | 0.654 | 0.746 | 1.14 |
| `/oteldemo.CartService/AddItem` | span | — | 0.476 | — |
| `/api/currency` | rum | 0.218 | 0.410 | 1.88 |
| `/api/products/:id:` | span | — | 0.281 | — |
| `/oteldemo.CartService/EmptyCart` | span | — | 0.276 | — |

**Summary:** 14 endpoints · 7 RUM-primary · 7 span-only · rumDrivenShare 0.579 · mean extrapolation ×1.248.

---

# wkf10640 / EasyTrade — RUM-primary ordered journeys (ISI-5719)

_trading app — a wholly different app from Astroshop._ Live `user.events`, 24h, **15,351 sessions**.

## Ordered journey templates (18 distinct, top 8)

| sessions | weight | steps | sequence |
|---:|---:|---:|---|
| 7,265 | 47.3% | 1 | `/login` |
| 3,622 | 23.6% | 8 | `/ > /login > /home > /deposit > /instruments > /instruments/:id: > /credit-card > /credit-card/active` |
| 2,979 | 19.4% | 7 | `/ > /login > /home > /instruments > /instruments/:id: > /credit-card > /credit-card/active` |
| 521 | 3.4% | 8 | `/ > /login > /home > /instruments > /instruments/:id: > /withdraw > /credit-card > /credit-card/active` |
| 470 | 3.1% | 5 | `/ > /login > /home > /instruments > /instruments/:id:` |
| 345 | 2.2% | 6 | `/ > /login > /home > /deposit > /instruments > /instruments/:id:` |
| 58 | 0.4% | 8 | `/ > /login > /home > /deposit > /instruments > /instruments/:id: > /credit-card > /credit-card/status` |
| 41 | 0.3% | 7 | `/ > /login > /home > /instruments > /instruments/:id: > /credit-card > /credit-card/status` |

## Measured per-page think-time (view dwell, ms)

| page | n | p50 | p90 | mean |
|---|---:|---:|---:|---:|
| `/login` | 15,346 | 1546 | 1686 | 1566 |
| `/` | 8,083 | 783 | 996 | 786 |
| `/home` | 8,082 | 1635 | 1867 | 1629 |
| `/instruments` | 8,058 | 1773 | 2062 | 1828 |
| `/instruments/:id:` | 8,053 | 5591 | 37610 | 11038 |
| `/credit-card` | 7,264 | 1402 | 1981 | 1434 |
| `/credit-card/active` | 7,155 | 1009 | 1402 | 1109 |
| `/deposit` | 4,028 | 13297 | 13297 | 14787 |
| `/withdraw` | 538 | 11182 | 13297 | 14046 |
| `/credit-card/status` | 132 | 875 | 1209 | 948 |
| `/credit-card/order` | 25 | 9222 | 9703 | 8790 |

## Per-endpoint overlap & extrapolation (RUM ⟗ spans)

| endpoint | source | RUM req/s | span req/s | factor |
|---|---|---:|---:|---:|
| `/v1/flags/ergo_aggregator_slowdown` | span | — | 1.666 | — |
| `/api/Packages/GetPackages` | span | — | 1.664 | — |
| `/api/Products/GetProducts` | span | — | 1.664 | — |
| `/api/offers/CryptoTrading.com` | span | — | 0.333 | — |
| `/api/offers/tradeCom.co.uk` | span | — | 0.333 | — |
| `/api/offers/Stratton-oakmount.com` | span | — | 0.333 | — |
| `/api/offers/CheapTrading.mi` | span | — | 0.333 | — |
| `/api/offers/dynatestsieger.at` | span | — | 0.333 | — |
| `/v1/flags/high_cpu_usage` | span | — | 0.185 | — |
| `/v1/prices/latest` | span | — | 0.140 | — |
| `/broker-service/v1/instrument` | rum | 0.117 | 0.123 | 1.05 |
| `/v1/instrument` | span | — | 0.123 | — |

**Summary:** 39 endpoints · 11 RUM-primary · 28 span-only · rumDrivenShare 0.0741 · mean extrapolation ×0.9153.

---
