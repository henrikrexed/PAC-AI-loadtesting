# ISI-5787 — Grail-native RUM journeys (overturn ISI-5691 NO-GO) · consolidation

**Parent:** [ISI-5622](/ISI/issues/ISI-5622). **Board correction** (comment `65c6ace4`, 2026-10-13, Henrik):
*"why no go on grail rum data — `user.events` has lots of relevant information."*

This document consolidates the Grail-native RUM result and marks SCOPE methodology **step 2c (iii)**
DELIVERED. It does **not** redo extraction — the ordered-RUM-journey work already shipped under
[ISI-5693](/ISI/issues/ISI-5693) (session stitch + dual-source merge) and
[ISI-5719](/ISI/issues/ISI-5719) (live `user.events` ordered journeys, app-agnostic on two apps).
Per the "consolidate, don't duplicate" instruction, this is the single place that states the four
done-when criteria as met and links the proof.

---

## TL;DR — the NO-GO was a false negative

[ISI-5691](/ISI/issues/ISI-5691) reported **NO-GO on a Grail/DQL RUM extractor**. It probed the
**wrong objects**: `dt.rum.*` attributes *on spans* (there are ~none) and the classic USQL/RUM store
(which needs a `dt0c01` token). It missed Grail's **first-class RUM record types** — `user.sessions`
and `user.events`. Those are plain DQL (`fetch user.sessions` / `fetch user.events`), keyed by
`dt.rum.session.id`, on the ordinary `dtctl`/Grail read plane — **no `dt0c01`/USQL token**. The only
gate is the read-token scope `storage:user.events:read` (+ `storage:user.sessions:read`). The NO-GO is
**overturned**; RUM fusion is viable and now shipped.

---

## Done-when criteria — all met

### 1. Grail RUM path confirmed live (wkf10640, `tenant-b` readonly)

| object | access | live volume (24 h, wkf10640) | key |
|---|---|---|---|
| `user.sessions` | readonly token, **accessible** | ~37 k sessions tenant-wide; 5 RUM apps incl. mobile | `dt.rum.session.id` |
| `user.events` | needs scope `storage:user.events:read` | **448 k events**; Astroshop 18,773 sessions | `dt.rum.session.id` |

- `user.sessions` was accessible on the base readonly token (ISI-5693 §7.1).
- `user.events` initially **403'd** on that token (missing scope) — this was flagged as the **one board
  action**. The board granted a wkf10640 token **with** `storage:user.events:read`; it is bound locally
  as `dtctl` context **`tenant-b-events`** (token local-only, rotate). With the scope present, live
  `user.events` returned 448 k rows and all downstream journeys below are from real data.
- **Both record types are plain DQL** — confirming the overturn. No `dt0c01`, no USQL.

### 2. Ordered browser journeys from `user.events` — Astroshop, with measured think-times

Built by grouping `user.events` by `dt.rum.session.id`, ordering by event time, and reducing each
session to its ordered view sequence. Live `user.events`, 24 h, **18,773 sessions → 16 distinct
ordered templates**. Top paths (full table in `loadtests/wkf10640-astroshop-frontend/rum-journey-sidebyside.md`,
model in `rum-journey-model-astroshop.json`):

| sessions | weight | steps | sequence |
|---:|---:|---:|---|
| 15,588 | 83.1% | 7 | `/ > /product/:id: > /cart > / > /product/:id: > /cart > /cart/checkout/:uuid:` |
| 2,482 | 13.2% | 6 | `/ > /product/:id: > /cart > / > /product/:id: > /cart` (**abandon** — no checkout) |
| 408 | 2.2% | 5 | `/ > /product/:id: > /cart > / > /product/:id:` |

**Measured per-page think-time** (view-dwell from inter-event gaps, not an assumption):

| page | n | p50 ms | p90 ms | mean ms |
|---|---:|---:|---:|---:|
| `/` | 37,502 | 1773 | 3869 | 2369 |
| `/product/:id:` | 37,484 | 988 | 2351 | 3589 |
| `/cart` | 37,044 | 1431 | 2829 | 1304 |
| `/cart/checkout/:uuid:` | 15,763 | 831 | 988 | 3045 |

**vs the span-derived Browser/Buyer journeys ([ISI-5684](/ISI/issues/ISI-5684)):** RUM gives the **real
ordered end-to-end** (the browse→cart→checkout order, the 13.2 % abandon branch, and real dwell times)
that span-tree extraction under-samples. Span extraction saw an overwhelmingly "Browser" mix and a
rare "Buyer" tail; RUM shows the dominant path **is** a buyer journey that completes checkout 83 % of
the time, with a measured abandon rate — the Buyer path spans under-counted.

**App-agnostic proof:** the same pipeline was run unchanged on **EasyTrade** (a wholly different trading
app) → 15,351 sessions, 18 templates, 47.3 % login-bounce, `/deposit` think-time ~14.8 s
(`rum-journey-model-easytrade.json`). Two unrelated apps, one code path ⇒ not app-specific.

### 3. The RUM ↔ span join — demonstrated

Two complementary joins, both keyed on the session id and shipped:

- **OTel `session.id` on spans** → `skills/workload-model/scripts/session_stitch.py` (ISI-5693,
  default-on, 56/56 tests). Grail-native, no token, works beyond browser apps. Practical limit: on
  wkf10640 `session.id` is sparse (~0.056 % of spans), so this is the broad-but-shallow join.
- **`user.events` ⟗ server spans** → `source_merge` in
  `skills/workload-model/scripts/rum_events.py` + `build_wkf10640_rum_journeys.py`. RUM browser paths
  and server-span paths are canonicalised deterministically (template numeric/uuid/hex id segments,
  drop static assets) and joined where they match; the rest fall to span-only. Live Astroshop merge:

  > 14 endpoint keys · **7 RUM-primary · 7 span-only** · 3 rum-only dropped ·
  > **rumDrivenShare 0.579** · mean extrapolation factor **×1.248** (range 1.05–1.88).

  This is the link Henrik flagged: a RUM journey now carries **browser steps + backend fan-out** —
  RUM supplies the user-visible ordered path and think-times, spans supply the internal/proxy-rewritten
  endpoints RUM can't see, joined on `dt.rum.session.id` / propagated `trace.id`.

### 4. Fold into SCOPE — step 2c tier (iii)

Folded as an **additive, browser-apps-only, PII-scrubbed** RUM input to the `workload-model` engine.
Methodology §3.1 step 2c (iii) is updated from "tracked/pending" to **DELIVERED** (this commit).
Tier structure unchanged:

- **(i)** span method — default, every app.
- **(ii)** OTel `session.id` on spans — preferred Grail-native session signal (ISI-5693), default-on.
- **(iii)** **Grail-native RUM fusion via `user.sessions` + `user.events`** — richest signal, browser
  apps only, additive on `metadata.source.*`, gated only by `storage:user.events:read`.

**Boundary (unchanged):** RUM covers browser/mobile front-ends only; API/service/agent/batch/cron
workloads have no RUM → span method holds. **Correction retained:** EasyTrade *does* have a browser
RUM app.

---

## PII & read-only posture

- Tenant kept **read-only** (§7.1); all extraction via `dtctl` readonly contexts (`tenant-b`,
  `tenant-b-events`). No writes.
- RUM user fields (user ids, geo, IPs) are **scrubbed** before the G4 dataset; journeys key on
  `dt.rum.session.id` and reduce to anonymous ordered **view/endpoint** sequences + aggregate
  think-times — no per-user attributes survive into the model.

## Deliverables (shipped, consolidated here)

| artifact | ticket | what |
|---|---|---|
| `skills/workload-model/scripts/rum_events.py` | ISI-5719 | pure `user.events` → ordered-journey stitcher (+ measured think-times, per-endpoint overlap, `source_merge`) |
| `skills/workload-model/scripts/session_stitch.py` | ISI-5693 | OTel `session.id`-on-spans stitcher (tier ii) |
| `skills/workload-model/scripts/rum_sessions.py` | ISI-5693 | `user.sessions` envelope parser |
| `skills/workload-model/scripts/build_wkf10640_rum_journeys.py` | ISI-5719 | app-agnostic live builder (Astroshop + EasyTrade) |
| `loadtests/wkf10640-astroshop-frontend/rum-journey-model-astroshop.json` | ISI-5719 | live Astroshop model |
| `loadtests/wkf10640-astroshop-frontend/rum-journey-model-easytrade.json` | ISI-5719 | live EasyTrade model (app-agnostic proof) |
| `loadtests/wkf10640-astroshop-frontend/rum-journey-sidebyside.md` | ISI-5719 | both apps, human-readable |
| `docs/evidence/isi5693-session-stitch.md` | ISI-5693 | session-stitch + `user.sessions`/`user.events` evidence |
| tests | — | `test_rum_events.py` + `test_rum_sessions.py` + `test_session_stitch.py` = **32/32 green** |

## DQL gotchas (for whoever re-runs)

No single-quotes / no `arrayConcatString`; nested if-else is flaky; `--context` returns `{records}`;
Paperclip `POST /comments` field is `body` (not `comment`); attachments need an explicit MIME type.
`user_action` in Astroshop `user.events` is labelled by page, so the derived sequence is views-only
(not sub-page actions) — a known, documented limit, not a bug.

---

**Report to BigBoss:** methodology step 2c (iii) is now DELIVERED (Grail-native RUM fusion), the
ISI-5691 NO-GO is formally overturned, and the only board action that was ever needed — the
`storage:user.events:read` scope — is granted. No further board decision required.
