# ISI-5691 — Dynatrace RUM user-session extraction + session↔span link (SCOPE step 2c feasibility)

> **Feasibility spike (read-only).** Parent ISI-5622; folds into methodology §3.1 step 2c.
> Tenant: **wkf10640** via the readonly `tenant-b` dtctl context (Grail-read platform token
> `dt0s…RAXB`). Window: 24h ending 2026-10-12T13:00Z. No production code; extraction/investigation only.
>
> **Verdict: NO-GO on a DQL/Grail RUM extractor for step 2c on this tenant version.** RUM is live and
> rich, but the raw user-session / user-action *instances* and the RUM→span join are **not reachable
> through Grail/DQL** — they live in the classic RUM session store (USQL / RUM API), which needs a
> classic `dt0c01` token we do not hold. The span method (2a/2b) remains the method. See
> §Recommendation for two integration paths and the hand-back to BigBoss.

---

## TL;DR answers to the 5 questions

| # | Question | Answer (live evidence) |
|---|----------|------------------------|
| 1 | Does RUM data exist on wkf10640? | **YES, heavily** — 3 RUM apps, ~31.8k sessions/day, ~296k actions/day, ~1.47M beacons/day. But only **aggregate** entities + **self-monitoring counters** are DQL-reachable; there is **no `dt.rum.*` Grail data object** and **no `dt.rum.*` attribute on any span**. |
| 2 | Can we reconstruct a browser journey from RUM (via DQL)? | **NO (not via DQL/this token).** Per-session ordered action *instances* — the thing needed for session grouping, order, and think-times — are not in Grail. Grail gives only the 10 action-type entities + per-action volume ⇒ weights, **not** session boundaries/order/think-times. |
| 3 | The RUM ⟕ span join | **Not DQL-joinable on this tenant version.** No span carries `dt.rum.application.id` / `dt.rum.session.id`, and RUM actions aren't in Grail, so there is no join field to resolve. The link exists conceptually (RUM agent propagates `traceparent`; DT maps user-action → server PurePath) and shows in the UI waterfall, but it is not exposed to DQL here. The only cross-tier session key actually present in Grail is the **OTel demo's own `session.id` baggage** — sparse (`ad` service only) and not RUM. |
| 4 | Does it improve fidelity, and where? | **Yes in principle — it closes the exact gap the astroshop model flags** (session stitching + real think-times; see model R5 below). **But unrealizable today** because the data isn't reachable with current access. |
| 5 | Boundary: do non-browser apps have no RUM? | **Confirmed, with one correction.** Only 3 RUM apps exist — all browser frontends (Astroshop, Astroshop Pure OpenTelemetry, **EasyTrade**). unguard, image-provider, the A2A agents (smartfreight/tms), and cron pollers have **no** RUM app → span fallback holds. **Correction:** EasyTrade *does* have a RUM app (its web frontend), so the methodology's blanket "easytrade → no RUM" is imprecise — the browser tier is RUM-covered; its reverse-proxy/backend services are not. |

---

## Q1 — RUM availability on wkf10640

**RUM applications (entities) — 3, all browser frontends:**

```
fetch dt.entity.application | fields entity.name, entity.type, id
```
| entity.name | id |
|---|---|
| Astroshop | APPLICATION-F9D25E95F25AFE0A |
| Astroshop Pure OpenTelemetry | APPLICATION-FDB6411FA4CF4B61 |
| EasyTrade | APPLICATION-55CF6DE67B41A20C |

**User-action *types* (aggregated entities) — 10:**
```
fetch dt.entity.application_method | summarize count()        -- → 10
fetch dt.entity.application_method | fields entity.name | limit 5
```
Sample action names: `/api/checkout?currencycode=eur`, `/loginservice/api/login`,
`/api/images/banner.png`, `loading of page /login`, `/api/cart?currencycode=usd`.
These are **action definitions** (apdex-level aggregates), not per-session instances.

**RUM volume (self-monitoring metrics, 24h) — proves beacons/sessions are actively captured:**
```
timeseries sessions=sum(dt.sfm.server.rum.user_sessions.total_sessions), from:now()-24h
timeseries actions=sum(dt.sfm.server.rum.action_count), beacons=sum(dt.sfm.server.rum.beacon_count), from:now()-24h
```
| metric | 24h total |
|---|---|
| RUM user sessions | **31,843** |
| RUM user actions | **296,086** |
| RUM beacons | **1,468,781** |

Davis also raises RUM application events (`APPLICATION_SLOWDOWN`, `APPLICATION_ERROR_RATE_INCREASED`)
in the `events` stream, confirming the RUM apps are live-monitored.

**What is NOT present in Grail (the blocker):**
- No `dt.rum.*` data object. Every candidate returns `UNKNOWN_DATA_OBJECT`:
  `dt.rum.user_actions`, `dt.rum.user_sessions`, `dt.rum.user_action`, `dt.rum.user_session`,
  `dt.rum.session`, `dt.rum.action`, `dt.rum.events`, `dt.rum.visit`, `dt.rum.web`, `useraction`,
  `usersession`, … all invalid.
- No `dt.rum.*` attribute on any span: `fetch spans | filter isNotNull(dt.rum.application.id)` → **0 rows** over 48.6M spans.
- Only `dt.sfm.*` RUM metrics exist (self-monitoring counters) — volume, not content.

**Conclusion:** RUM is on and busy, but on this tenant version its session/action record store is the
**classic RUM store**, queryable via **USQL / the RUM API** (classic `dt0c01` token with
`DTAQLAccess`/`DataExport`), **not** via Grail/DQL. Our `tenant-b` token is a Grail-read platform
token (`dt0s…`) → the raw RUM data is out of reach for this spike.

---

## Q2 — Reconstructing a browser journey from RUM

Not achievable via DQL/this token. To group actions by session, order them, and derive inter-action
think-times you need the per-session **action instances** (`usersession`/`useraction` rows). Those are
in the classic store (USQL), not Grail. Via Grail we can only recover:
- the **10 action types** (`dt.entity.application_method`), and
- per-action **volume** (RUM metrics) ⇒ action weights.

That yields a weighted *bag of actions*, **not** ordered sessions, session boundaries, or think-times
— i.e. it does **not** deliver the headline RUM value. The USQL query that *would* do it (not runnable
here, documented for the integration path) is of the shape:

```usql
SELECT userSessionId, startTime, name, apdexCategory, targetUrl
FROM useraction
ORDER BY userSessionId, startTime     -- group by session, order within session → per-user sequence
```
then aggregate identical ordered sequences → dominant journeys + weights, and diff consecutive
`startTime` within a session → think-time distribution.

---

## Q3 — The RUM ⟕ span join (the key question)

**Finding: not a DQL-joinable relationship on wkf10640.**
- `fetch spans | filter isNotNull(dt.rum.application.id) OR isNotNull(dt.rum.session.id)` → **0 rows**.
  Server spans do not carry RUM identifiers, and RUM actions are not in Grail, so there is **no field to
  join on** in DQL.
- The link *exists* in Dynatrace: the RUM agent propagates W3C `traceparent` from the browser and DT
  stitches **user action → server-side PurePath/trace** (visible in the UI action waterfall; exposed via
  the classic RUM API as the action's linked PurePath / `webRequestId`). It is simply **not surfaced to
  DQL** on this tenant version.

**The only session key actually present in Grail is NOT RUM — it's the OTel demo's own `session.id`:**
```
fetch spans | filter isNotNull(session.id) | summarize c=count(), sessions=countDistinct(session.id), by:{service.name}
```
| service.name | spans | distinct session.id |
|---|---|---|
| ad | 27,996 | 5,274 |
| smartfreight-agent-service | 132 | 132 |

This is the astronomy-shop demo propagating an OTel `session.id` baggage attribute — but only on the
`ad` path (and smartfreight), **not end-to-end**, and it is independent of Dynatrace RUM. It is *not* a
RUM↔span join; it's a hint (see Path B).

---

## Q4 — Does RUM improve fidelity, and where?

**Where it would help is precisely documented in the existing astroshop span model**
(`loadtests/wkf10640-astroshop-frontend/scenario-proposal.md`, risk R5):

> *"R5 session-chaining limit. No persistent session id on browse spans; the Buyer archetype is
> reconstructed from self-contained checkout traces (browse→cart→checkout)."*

RUM's **true session boundaries** and **real inter-action think-times** are strictly higher fidelity
than span-order inference, and would let the Buyer journey be stitched from real browse→cart→checkout
sessions instead of inferred from self-contained traces. It would also cleanly separate real
user-initiated actions from background polling/XHR noise.

**But:** with the current access the gain is **unrealizable** — the session/action data cannot be
extracted. So the fidelity improvement is real in theory, zero in practice on this tenant/token today.
Quantification (RUM vs span journeys) was not possible because no RUM session data could be fetched.

---

## Q5 — Boundary confirmation (non-browser apps have no RUM)

`fetch dt.entity.application` returns **exactly 3** applications, all browser frontends. Therefore:
- **No RUM** for: unguard, image-provider, the A2A agents (smartfreight / tms), cron pollers
  (cloudsreagents). → span method (2a/2b) **unchanged** there. ✓ boundary holds.
- **Correction to the methodology:** **EasyTrade has a RUM app.** The blanket "easytrade → no RUM" is
  imprecise — EasyTrade's *web frontend* is browser-based and RUM-covered; only its reverse-proxy /
  backend services (the part ISI-5690 modeled from spans) are not browser surfaces. RUM covers the
  browser tier, not the backend.

---

## Recommendation (go / no-go) → hand back to BigBoss

**NO-GO on implementing SCOPE step 2c as a Grail/DQL RUM extractor on this tenant version.** The RUM
session/action instances and the user-action→`trace.id` join are not exposed to DQL; the join
described in methodology §3.1 step 2c ("user action → `trace.id` → spans") is **not implementable in
DQL on wkf10640**. The span method (2a/2b) stays the default.

Two integration paths if the board wants RUM fusion:

- **Path A — classic USQL / RUM API adapter (heavy, needs board action).**
  Mint a classic `dt0c01` token scoped `DTAQLAccess` (USQL) + `DataExport`. Build a *separate* input
  adapter (not DQL/Grail) that reads `usersession`/`useraction`, groups by session, derives order +
  think-times, and joins to spans via the action's linked PurePath / `webRequestId`. Must **strip PII**
  (user ids, geo, IP) before anything reaches the G4 dataset (methodology §3.1 2c caveats). This is a
  different data path from the rest of SCOPE (all Grail/DQL) and carries the most integration + security
  weight. **Blocked on:** board minting the classic token + a PII-scrubbing sign-off.

- **Path B — OTel `session.id` in spans (lightweight, Grail-native, recommended first step).**
  The demo already proves the plumbing: the `ad` service propagates an OTel `session.id` baggage
  attribute visible in `spans`. If apps propagate `session.id` (OTel session semconv) as **baggage
  across all services**, session stitching + think-times come straight from the existing `spans`
  pipeline — **no RUM dependency, no classic token, no PII** (synthetic/opaque id), and it generalizes
  **beyond browser apps** (works for easytrade backends, A2A agents too). This directly closes the model
  R5 gap without the Path-A cost. Recommend SCOPE detect `session.id` presence on spans and use it for
  session reconstruction when available.

**Proposed methodology edit (for BigBoss):** reframe §3.1 step 2c from "RUM via DQL join" to:
(i) default = span method; (ii) *preferred* session signal = **OTel `session.id` on spans where present**
(Path B); (iii) RUM fusion = **optional, gated** on a classic USQL/RUM-API adapter + board token + PII
scrubbing (Path A), marked *not available on Grail-only access*. Also fix the easytrade RUM note (Q5).

---

## Appendix — query ledger (all read-only, `--context tenant-b`)

| purpose | query (abbrev.) |
|---|---|
| event kinds/types | `fetch events, from:now()-24h \| summarize count(), by:{event.kind,event.type} \| sort count() desc` |
| RUM apps | `fetch dt.entity.application \| fields entity.name, id` |
| RUM action types | `fetch dt.entity.application_method \| summarize count()` |
| RUM sessions vol | `timeseries sessions=sum(dt.sfm.server.rum.user_sessions.total_sessions), from:now()-24h` |
| RUM actions/beacons vol | `timeseries sum(dt.sfm.server.rum.action_count), sum(dt.sfm.server.rum.beacon_count), from:now()-24h` |
| RUM metric catalog | `fetch metric.series \| filter matchesPhrase(metric.key,"rum") \| summarize count(), by:{metric.key}` |
| no RUM attrs on spans | `fetch spans, from:now()-24h \| filter isNotNull(dt.rum.application.id) \| summarize count()` → 0 |
| OTel session.id coverage | `fetch spans, from:now()-24h \| filter isNotNull(session.id) \| summarize count(), countDistinct(session.id), by:{service.name}` |
| `dt.rum.*` object probes | `fetch dt.rum.* \| limit 1` → all `UNKNOWN_DATA_OBJECT` |

Tenant kept read-only/isolated (§7.1). Token `tenant-b-read` still un-rotated (flagged to board) — valid for this round.
