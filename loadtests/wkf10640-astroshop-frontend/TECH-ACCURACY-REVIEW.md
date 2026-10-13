# Technical-accuracy review — PAC talk slides 5–12 (ISI-5723)

Reviewer: Observability Agent. Evidence: on-disk Astroshop model (rev 3), `merge-plan.json`,
`scenario-proposal.md`, ISI-5693 (DQL/RUM), ISI-5691/5719 (RUM state). A's slide copy (ISI-5722)
not yet posted — this pass fact-checks the **claim-set** the plan assigns to slides 5–12 and the
real numbers behind them. Re-run a line-level pass when A posts copy.

Verdict key: ✅ accurate as stated · ⚠️ accurate only if phrased carefully (trap) · ❌ would be wrong.

---

## 1. OTel three pillars (metrics / traces / logs) — ⚠️
- ✅ Pillars framing is fine as general OTel teaching.
- ⚠️ **Do not claim this model fused all three pillars.** On wkf10640 the `istio-proxy` access-log
  probe returned **0 lines** → extraction was **spans-only + RUM sessions**. Logs were absent; metrics
  entered only as the R5 cross-check recommendation (CPU/connections), not as an extraction source.
  Honest line: *"traces (spans) primary, RUM sessions secondary, logs unavailable on this tenant."*

## 2. The sampling trap + rate-parity — ⚠️ (highest-risk slide; the room will probe the math)
- ✅ General rule: with head sampling ratio `r`, `observed_rate = true_rate × r`; to drive real load
  you scale the observed rate by `1/r`. `r = 1.0` (100%) → no correction. Tail/adaptive sampling
  breaks naïve rate inversion — that's the real "trap."
- ❌ **Do NOT present 1.27 as a sampling-inversion / `1/r` factor.** This tenant is **unsampled**:
  `metadata.source.samplingRatio = 1.0`, and the proposal states *"no sampling correction applied."*
- ✅ **1.2735 is a cross-signal coverage ratio, not a sampling inverse:** span-observed browser
  arrival **33.0308/s ÷ RUM-observed 25.9377/s = 1.2735** (`merge-plan.json`). RUM beacons fire only
  on real browsers that load the JS; server spans capture *every* request (browsers + API/mobile + bots).
  Driving load off the RUM rate alone would **under-drive by 1.27×**. That is the rate-parity lesson:
  anchor on the signal that represents true arrival (here: unsampled server spans), and if you must
  start from a partial/sampled signal, correct it up to the true volume.
- Defensible numbers to put on the slide: factor **1.2735**, span-rate **33.03/s**, RUM-rate **25.94/s**,
  model peak **43.4/s**, Little's Law ratio **0.9994**. (Note: model window is −3h; the 1.27 merge-plan
  window is 24h — don't equate the two windows' absolute rates on one slide.)

## 3. State of RUM — ✅ (with one correction vs older decks)
- ✅ RUM on this stack is **Grail/DQL-native**: `fetch user.sessions` / `fetch user.events`, keyed by
  **`dt.rum.session.id`**. No classic `dt0c01`/USQL token. ~35.7k sessions/24h, 5 RUM apps incl. mobile.
- ⚠️ This **overturns the ISI-5691 NO-GO** — if any slide still says "RUM needs a classic token / isn't
  Grail-queryable," that's stale. Correct state is in ISI-5693.
- ⚠️ `user.events` requires scope **`storage:user.events:read`** (403 without it, ISI-5719). So **ordered
  per-action journeys + exact measured think-times are NOT in this model.** We used RUM **rate** (the 1.27)
  only; journey *steps* come from span-order reconstruction. Don't claim full ordered-RUM journeys here.

## 4. spans + user.sessions/user.events via DQL; key dt.rum.session.id — ⚠️ (subtle conflation trap)
- ✅ The DQL objects and the `dt.rum.session.id` key are correct.
- ❌ **Do not conflate the OTel `session.id` span attribute with Dynatrace RUM `dt.rum.session.id`.**
  On this tenant the `session.id` *span attribute* has only 20.12% coverage and sits **only** on the
  homepage ad/recommendation fetch (`/api/data → ad GetAds`) — it is a page-refresh ad marker, **not**
  a per-user-action journey key (0 of 1.41M frontend action spans carry it; it reaches none of
  cart/checkout/payment). RUM journeys come from `user.sessions`/`user.events`, a *different* signal.

## 5. The skill (workload-model + renderers) — ✅
- ✅ Gate chain is real and enforced in code: SCOPE → **V1 human gate** (hash/revision-bound
  `status.approval`) → SYNTHESIZE **V2a** (k6) / **J1–J7** (JMeter) → EXECUTE/G5. The demo model carries
  `status.approval` bound to **rev 3** (`sha256:cdd5294…9639e3`); both renderers refuse an unapproved model.
- ✅ Renderers are drop-ins behind one **Renderer interface** (ISI-5655); matrix = k6 / JMeter / Locust /
  Gatling, all green.

## 6. The 3-layer engine — ✅ (name the real layers)
1. **Extract** — `dtctl` DQL spans + RUM sessions → `workload-model.json` (§4 schema).
2. **Render** — one approved model → N tools via the Renderer interface (shown: k6 + JMeter).
3. **Execute + validate** — `loadtest-run` drives it; `synthetic=true` baggage → span attribute closes
   the loop at G5 (`validate-traces`). Correct as long as the slide names these, not invented layers.

## 7. Cross-cutting caveats A's copy should respect
- ⚠️ **Error rates read 0.0 because no error spans fell in the window — not a guarantee of error-free
  paths** (R1). Don't imply "prod has zero errors."
- ⚠️ **Weights are per-outcome, mean-of-window:** browser 99.08% / buyer 0.92%; model captures *mean*
  arrival (low CoV 0.29 here is tenant luck, not a peak-envelope guarantee, R2).
- ✅ wkf10640 is a shared, continuously-deployed playground (3 redeploys / 31 Davis problems in-window);
  baselines computed over 810,116 server spans so transients don't dominate — fine to state as a caveat.

---

**Bottom line:** the demo and its numbers are defensible. The two slides most likely to draw a
challenge are **§2 (sampling vs the 1.27 factor)** and **§4 (`session.id` span attr vs `dt.rum.session.id`)** —
both are easy to state wrong and are corrected above. Everything else is accurate if phrased per the ⚠️ notes.

---

## 8. Architecture recap — slide #13 "the stack in our cluster" (rev2 add) — ✅ with pipeline annotations
The plan's arch flow is **Astroshop/otel-demo → OTel Collector → Dynatrace Grail (spans + RUM) →
agent + skill + engine → renderers**. Fact-check against what is actually wired:
- ✅ **Astroshop = the OpenTelemetry Demo** (`frontend` + ~15 microservices), auto/SDK-instrumented,
  OTLP → **OTel Collector** → Dynatrace. Correct and standard.
- ✅ **Grail stores two surfaces we read:** the **`spans`** table (traces) and **RUM** (`user.sessions`,
  `user.events`), queried with **DQL via `dtctl`** (readonly context `tenant-b` = wkf10640).
- ⚠️ **Annotate the logs leg honestly.** On wkf10640 the `istio-proxy` access-log probe returns **0 lines**
  — logs are *not* a populated extraction source here. If the diagram draws a logs arrow into the model,
  label it "unavailable on this tenant (spans-only)."
- ⚠️ **Annotate `user.events` as scope-gated.** The RUM→model arrow for `user.events` is **403
  (`storage:user.events:read`, [ISI-5719](/ISI/issues/ISI-5719))**; live extraction **degrades to spans +
  `user.sessions`**. Draw it as a dashed/"glitch" edge, not a solid feed.
- ✅ **Engine = 3 layers** (matches §6): **Extract** (`dtctl` DQL → `workload-model.json`) → **Render**
  (one approved model → N tools via the Renderer interface) → **Execute+validate** (`loadtest-run`,
  `synthetic=true` baggage → G5 `validate-traces`). The **V1 human gate** sits between Extract and Render
  and is enforced in code (renderers refuse an unapproved model) — worth drawing as an explicit gate.
- ⚠️ **Keep "readonly / extraction-only / non-production / tenant isolated"** on the diagram: the token is
  readonly and the methodology (§7.1) forbids production targets without board approval.
- **Repo/asset links on #13 and the close slide:** point to `skills/workload-model` (extract+schema+gates),
  `skills/{k6,jmeter,locust,gatling}-synthesis` + `skills/renderer-kit` (render), `skills/loadtest-run`
  (execute), and `loadtests/wkf10640-astroshop-frontend/` (this demo's artifacts). Verify each path resolves
  in the public mirror before the QR/links go on the slide.

## 9. rev2 demo change — FULL LIVE end-to-end (verified this run) — ✅
The demo is now **live on stage**, not a pre-baked model (plan rev2). Verified end-to-end against
live wkf10640 on 2026-10-13 (`run-demo-live.sh`):
- **live DQL** `fetch spans` + `fetch user.sessions` → `live_extract.py` → fresh `wkf10640_extract.live.json`
  → `build_wkf10640.py` (**G0 12/12**) → **live V1 human gate** (`approve_model.py`) → **k6 V2a 7/7** +
  **JMeter J1–J7**. No committed `workload-model.json` as the source.
- **Live numbers captured this run (3h window):** 321,495 frontend root traces; order split **buyer 0.9% /
  browser 99.1%** (independently re-confirmed live, matches the methodology); server rate **77.9 tps**;
  product-key cardinality **10**; `samplingRatio` **1.0**; `user.sessions` reachable.
- **The "glitch in the Matrix" is real and reproducible on cue:** `fetch user.events` → **403
  NOT_AUTHORIZED_FOR_TABLE** (missing `storage:user.events:read`). The extractor catches it and degrades to
  spans + `user.sessions`; nothing in the model depends on `user.events`, so the degrade is **lossless** for
  this demo. ⚠️ Live volumetrics vary by window (e.g. latency/concurrency were higher in this run than the
  captured 3h fixture) — narrate numbers as "what the system is doing right now," not fixed constants.
- **Fallback:** the committed rev1 artifacts + `run-demo.sh` + `demo-transcript.txt` are a rehearsed
  recorded run of the identical flow, played only if stage network/tenant is down (`run-demo-live.sh`
  Step 0 auto-detects reachability and tells you to fall back).
