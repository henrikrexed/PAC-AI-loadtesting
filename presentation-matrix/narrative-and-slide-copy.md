# PAC Talk — *There Is No Spoon: Load-Testing the Real World*
## Narrative + Slide Copy + Research (Matrix theme)

*ISI-5722 (workstream A) · child of [ISI-5720](/ISI/issues/ISI-5720) · theme **The Matrix** 🔴💊 approved by the board (plan rev `d09391e7`)*
*Speaker: Henrik Rexed · IsItObservable · Format: PAC expert session, 30 min (~22 min content + ~8 min room discussion)*
*Draft v1 · 2026-10-12 · Content Writer*

> **How to read this doc.**
> - **Part 1** — theme spine + the film-beat→process map every themed line must sit on.
> - **Part 2** — the §4 research pack, with sources and accuracy flags. Read this before you trust a number on a slide.
> - **Part 3** — the speaking narrative, timed, first person, ready to rehearse.
> - **Part 4** — per-slide copy (title, bullets, speaker-note pointer, visual cue for UXDesigner/B).
> - **Part 5** — claims flagged for Observability Agent (workstream C) to fact-check, and open questions.
>
> **Voice:** informed peer talking to peers. No hype. The recurring honesty move is *"trust the trace, not the demo."* We are provoking a room of experts into a fight about sampling and fidelity — not lecturing them.

---

# Part 1 — Theme spine & the beat→process map

**One-line spine:** *"Take the red pill: stop guessing, load the real world."*

**The deeper spine (say it once, slide 2):** our process is literally the plot of *The Matrix* — *see reality as it truly is → build a faithful projection of it → load that projection on demand → and never bend the test to make it pass.*

Every themed line on every slide maps to a **real technical claim**. If a Matrix reference doesn't carry a technical point, it gets cut. The map:

| Film beat (verified quote — see Part 2 §3) | Our process | Lands on slide |
|---|---|---|
| **Blue pill** — "you wake up in your bed and believe whatever you want to believe" | The load test built on folklore: RPS, mix, pacing you guessed | 2, 3 |
| **Red pill** — "you stay in Wonderland, and I show you how deep the rabbit hole goes" | Observability: production telemetry is the ground truth | 2, 5 |
| **"Residual self image… the mental projection of your digital self"** | The workload **model** — a projection of reality, only as complete as what you sampled | 8, 11, 12 |
| **"Déjà vu… a glitch in the Matrix. It happens when they change something"** (Trinity) | **Sampling artifacts** — the gaps a sampled trace stream leaves when you extrapolate | 6 |
| **"This is the Construct. It's our loading program. We can load anything…"** | The **engine** — loads a runnable world (the test config) from the model | 12 |
| **"Guns. Lots of guns."** (materialize an arsenal on demand) | Renderers materialize **k6 / JMeter / Locust / Gatling** from one model | 13, 14–17 |
| **The Oracle** / **"Temet Nosce" — Know thyself** | The human **VALIDATE** gate — judgment stays human | 18 |
| **"There is no spoon… it is not the spoon that bends, it is only yourself"** | Don't bend the test to pass; bend the test to match reality | 1, 19, 20 |

**Theme discipline (for a sharp audience):** the theme is a thin framing layer. Use it in titles, section turns, and the three discussion beats. In the technical core (slides 5–13) let the numbers carry the weight and let the Matrix line be the *punctuation*, not the argument.

---

# Part 2 — Research pack (§4)

*Full sourcing so C can verify and so Henrik can answer hard questions from the floor. Tier flags included. Anything marked ⚠ needs confirmation before it goes verbatim on a slide.*

## 2.1 Sampling & extrapolation for performance engineers

**The claim we make:** a sampling *rate* corrupts naive **count-based** extrapolation, and the fix is **rate parity** — re-weight each dataset by its own sampling ratio and compare *rates*, never raw counts.

- **OpenTelemetry's own spec backs the fix (Tier 1).** The OTel *TraceState: Probability Sampling* spec defines **adjusted count** as *"the mathematical inverse (reciprocal) of the sampling probability — the expected number of times an item should be counted for it to be representative of the population."* i.e. `adjusted_count = 1 / probability`. That is exactly "normalize by the sampling ratio before you count." Source: <https://opentelemetry.io/docs/specs/otel/trace/tracestate-probability-sampling/> (status: Development). Design rationale: OTEP 0170 *Sampling probability* <https://github.com/open-telemetry/opentelemetry-specification/blob/main/oteps/trace/0170-sampling-probability.md>.
- **Head vs tail sampling — the distinction that decides whether extrapolation is even possible:**
  - **Head sampling** — keep/drop decided at trace *start*, probabilistically. You *can* recover population counts **if** the probability is propagated (OTel carries it in `tracestate` as the `th` threshold). Reweighting is valid.
  - **Tail sampling** — keep/drop decided *after* the trace completes (keep errors, slow traces, etc.). Outcome-biased, and it **does not propagate a reweighting factor**, so you **cannot** recover true counts/rates from tail-sampled data. Authority (Tier 2/3, a well-known OTel engineer): Goutham Veeramachaneni — *"There is no way to generate accurate metrics based on sampled data with tail-sampling … metrics need to be generated before the sampling happens."* <https://www.gouthamve.dev/sampling-at-scale-with-opentelemetry/>. Supporting: OTel blog *Tail Sampling* <https://opentelemetry.io/blog/2022/tail-sampling/>; Uptrace *Head-Based and Tail-Based Sampling* <https://uptrace.dev/opentelemetry/sampling>; Elastic *How we fixed head-based sampling in OpenTelemetry* <https://www.elastic.co/observability-labs/blog/how-we-fixed-head-based-sampling-in-opentelemetry>.
- **Our own live proof — the 1.27 factor (internal, Tier 1 for us).** On the Astroshop frontend (tenant wkf10640, 24 h window, [ISI-5693](/ISI/issues/ISI-5693)): RUM `user.sessions` captured **25.94 req/s**; the **unsampled** span-observed volume was **33.03 req/s**. Ratio = **1.2735** (= 2,853,862 / 2,241,018 requests). So RUM sees ~**79 %** of the frontend requests, and the RUM-primary journey is driven **×1.27** to reproduce the unsampled truth. This is the methodology's "beware the sampling → extrapolate" rule made concrete, with a *measured* factor, not a toy number. Source: `docs/evidence/isi5693-session-stitch.md` §8.1; `loadtests/wkf10640-astroshop-frontend/merge-plan.json` (`extrapolationFactor: 1.2735`).
- **Our methodology position (internal).** ANALYZE §3.5 *sampling parity*: "Compare *rates*, not raw counts, and normalize for the sampling ratio of each dataset… Mismatched, unrecorded sampling is the most common false 'out of tolerance'." The applied factor is recorded in `shape-diff.json` (`samplingFactor: {prod, test}`). And §11 residual **R1** is the honest caveat: extraction-side sampling blindness — rare/error journeys (tail-sampled-away checkouts, retry storms) are under-represented at *extraction*, and SCOPE must flag low-confidence journeys. Source: `docs/methodology.md` §3.5, §11.

**Stage one-liner (expert-safe):** *"OpenTelemetry's own spec says a sampled span's adjusted count is the reciprocal of its sampling probability. So before you size a test from sampled traces, re-weight each dataset by its own ratio and compare rates — never raw counts. And that only works for head sampling; tail sampling throws the weighting away, so you literally cannot extrapolate counts from it."*

## 2.2 State of RUM 2025–2026

- **What RUM captures that synthetic and APM/tracing do not (Tier 3, uncontroversial):** RUM is passive collection from *real* sessions (JS/mobile SDK) — real user journeys, the real arrival curve / traffic shape over time, real concurrency, and the real device/geo/browser/network distribution. Synthetic is scripted and uniform (fixed location, fixed schedule); server-side APM/tracing is sampled and server-centric. Source: ClickHouse, *RUM vs synthetic monitoring* <https://clickhouse.com/resources/engineering/rum-vs-synthetic-monitoring>.
- **Strongest expert-proof point (Tier 1 — use this, not the market-size figure):** Google ranks on **field** Core Web Vitals from the **Chrome User Experience Report (CrUX)** at the **75th percentile** — *not* lab/synthetic data. A page can score well in Lighthouse (lab) and still fail Core Web Vitals in the field. Trace on stage to Google's own web.dev / CrUX docs. Vendor summary: Middleware <https://middleware.io/blog/core-web-vitals-with-rum-synthetic-monitoring/>.
- **OTel browser / client-side RUM story — be precise, this room will know (Tier 1 for status):**
  - OTel browser instrumentation is **experimental / in flux, NOT stable.** Instrumentations were refactored into a new repo; `@opentelemetry/instrumentation-document-load` is being replaced by `@opentelemetry/browser-instrumentation/*` (navigation-timing, resource-timing), and page loads are now emitted as **log records rather than spans.** Source: Honeycomb, *Understanding OpenTelemetry's Browser Instrumentation* <https://www.honeycomb.io/blog/opentelemetry-browser-instrumentation>.
  - The **session semantic convention is status = Development** (OTel's word for not-stable — names can change with no deprecation path). `session.id` and `session.previous_id` are both **Development** and **Opt-In**. Source (Tier 1): <https://opentelemetry.io/docs/specs/semconv/general/session/> and registry <https://opentelemetry.io/docs/specs/semconv/registry/attributes/session/>.
  - Vendor OTel-RUM offerings ship as **technical preview** (e.g. Elastic OTel RUM <https://www.elastic.co/docs/solutions/observability/applications/otel-rum>).
  - ⚠ The OTel **Client-Side Telemetry SIG** drives this work — real, but **verify the exact SIG name/charter URL before naming it on a slide.**
- ⚠ **Market-size figures are analyst estimates (low tier) — present as "analyst estimate" or omit.** RUM market ≈ USD 1.2 B (2024) → USD 3.5 B by 2033 at ~13.5 % CAGR (Verified Market Reports). I recommend we **lead with the CrUX/75th-percentile field-data point instead** — far stronger for this audience than a paid market forecast.

**Stage one-liner (expert-safe):** *"OpenTelemetry can do RUM today — but the browser SDK and the session semantic conventions are still marked Development, not stable. So client-side OTel RUM is early; the production-grade RUM truth today still lives in your vendor's `user.sessions`."*

## 2.3 DQL for RUM — confirmed field names & queries

Confirmed against our tenant evidence ([ISI-5693](/ISI/issues/ISI-5693), `docs/evidence/isi5693-session-stitch.md` §7). **RUM in Grail is DQL-native** — no classic `dt0c01`/USQL token. The correct objects are **`user.sessions`** and **`user.events`**, keyed by **`dt.rum.session.id`**. (ISI-5691's earlier NO-GO probed the wrong objects — `dt.rum.*` and RUM attributes on `spans` — and was overturned.)

- **Spans (server-side traces):**
  ```
  fetch spans
  | filter isNotNull(session.id)
  | summarize spans=count(), sessions=countDistinctExact(session.id), by:{service.name}
  ```
- **`user.sessions`** — one row per real-user session; **accessible today** on the read token. Live: **35,679 sessions / 24 h** across 5 RUM apps incl. mobile (Astroshop 17.1k web · EasyTrade 7.9k web · Astroshop-PureOTel 5.2k · Astroshop_Android 2.9k mobile · others). 54 fields incl. `dt.rum.session.id`, `duration`, `user_action_count`, `navigation_count`, `request_count`, `characteristics.is_bounce`, `end_reason`, geo/device/browser.
  ```
  fetch user.sessions
  | summarize sessions=count(), p50_actions=percentile(user_action_count,50), by:{frontend.name}
  ```
- **`user.events`** — the **ordered** per-session navigation (views / user actions / requests + exact inter-action think-times). This is what turns volume into a *journey*.
  ```
  fetch user.events
  | filter dt.rum.session.id == "<id>"
  | sort timestamp asc
  ```
  ⚠ **Caveat to state honestly on stage:** `user.events` is **scope-gated** on our read token — it returns `403 NOT_AUTHORIZED_FOR_TABLE` (missing `storage:user.events:read`). So the *ordered journey + exact per-action think-times* piece is proven in design and awaits the scope grant ([ISI-5719](/ISI/issues/ISI-5719)); the **request-volume merge and the 1.27 factor need only `user.sessions` + spans** and are live today. Don't demo `user.events` live.

## 2.4 Matrix — verbatim-verified quotes (Part 1 map uses these)

Verified from *The Matrix* (1999) transcript (Scraps from the Loft) + The Ringer monologue fact-check.

- **Red/blue pill — Morpheus:** *"You take the blue pill, the story ends; you wake up in your bed and believe whatever you want to believe. You take the red pill, you stay in Wonderland, and I show you how deep the rabbit hole goes."* Lead-in: *"I imagine that right now you're feeling a bit like Alice. Tumbling down the rabbit hole?"*
  - **Misquote guard:** it's *"show you how deep the rabbit hole goes"* (not "see"), and *"you stay in Wonderland"* (not "go to"). Don't over-claim which hand holds which pill.
- **"There is no spoon" — the Spoon Boy** (Oracle's waiting room, NOT the Oracle, NOT Morpheus): *"Do not try and bend the spoon. That's impossible. Instead, only try to realize the truth… There is no spoon… Then you'll see that it is not the spoon that bends, it is only yourself."* Neo echoes *"There is no spoon?"*
- **"Residual self image" — Morpheus** (the Construct, white void): *"Your appearance now is what we call residual self image. It is the mental projection of your digital self."*
- **Déjà vu / glitch — Trinity** (black-cat scene): Neo: *"A black cat went past us, and then another that looked just like it."* **Trinity:** *"Déjà vu is usually a glitch in the Matrix. It happens when they change something."* (The glitch line is **Trinity's**.)
- **"Guns. Lots of guns." — Neo** (the Construct, weapon racks slide in).
- **"The Construct" — Morpheus:** *"This is the Construct. It's our loading program. We can load anything, from clothing, to equipment, weapons, training simulations, anything we need."*
- **The Oracle:** sign over her door **"Temet Nosce" = "Know thyself."** ⚠ Her spoken lines are the most-paraphrased in the film — treat Oracle dialogue as **paraphrase**, not verbatim, unless re-verified. The "Free your mind" / jump-program wording also ⚠ re-verify before putting verbatim on a slide.

---

# Part 3 — Speaking narrative (timed, first person)

*Target ≈ 22 min spoken + ~8 min distributed across 3 discussion beats = 30 min. Beats marked 💬 are where I shut up and the room talks. [FLEX] marks cuttable material if I'm running long.*

### Slide 1 — Title (0:00–0:30)
Hi — I'm Henrik Rexed, from IsItObservable. The title of this talk is *There is no spoon*, and by the end I want you to agree with it. Because almost every load test I've ever seen tries to bend the spoon — tries to make the system pass the test — when the real job is the opposite: bend the test until it matches reality. Thirty minutes, three places where I'm going to stop and make *you* argue with me, one live demo, and one number — one-point-two-seven — that I'll earn before I use it.

### Slide 2 — The blue pill load test (0:30–2:00)
Here's the choice every performance engineer makes, usually without noticing. *(Morpheus line on screen.)* The blue pill: you run the test you've always run, the dashboard goes green, you wake up and believe whatever you want to believe. The red pill: you look at what production is *actually* doing, and you follow that rabbit hole all the way down — even when it tells you your test has been fiction for three years. This whole talk is the red pill. We're going to see the real world as it is, build a faithful projection of it, load that projection on demand — and never, ever cheat it to pass.

### Slide 3 — The basics: a load test must reflect real life (2:00–4:00)
Let's start where we agree. A load test is only worth running if it reproduces production *shape* — not just an average number. Open a typical k6 or JMeter script and ask four questions. Volume: where did the RPS come from? Usually "ten times peak" — peak of what, measured when? Mix: three endpoints in the script, forty in production. Pacing: whatever the thread-group default happened to be. Payloads: three hardcoded JSON blobs. Each one is a guess, and they multiply. And here's the failure mode that costs money: the run passes, production still burns, because a flat synthetic ramp against a jagged, bursty, seasonal real curve — same average, completely different reality — exercises your system in a state it never actually occupies. A test that doesn't match shape doesn't test your system. It tests your imagination. Which brings me to my first question for you.

### 💬 Slide 4 — Discussion #1 (4:00–5:30)
So — honestly — where do *your* numbers come from? Show of hands, or shout it out: who chose the RPS in your main load test, and what was it based on? *(Collect 3–4 answers. Expect: "last year's number," "double the record," "the SLO," "marketing's traffic forecast.")* I'm collecting folklore here, and I'm going to come back to every one of these. Hold that thought — because the rest of this talk is about replacing every one of those answers with a trace.

### Slide 5 — The evolution with OTel (5:30–7:30)
What changed is that the red pill actually exists now. Ten years ago, "production reality" was a guess dressed up as a metric. Today, with OpenTelemetry, we have three correlated signals — metrics for the *what*, traces for the *why and the path*, logs for the *detail* — and for a load test, traces are the gift: they give you the actual journeys, the fan-out across the service graph, the real per-operation latency, and the arrival curve at one-minute resolution. This is the red pill. The catch — and it's the whole middle of this talk — is that the red pill shows you reality *through a sample*. And a sample lies to you in a very specific, very dangerous way.

### Slide 6 — The sampling trap (7:30–10:00)
This is the glitch in the Matrix. *(Trinity quote on screen.)* Déjà vu — you see the same cat twice — means they changed something. In telemetry, the thing that "changed" is that you're not seeing every request; you're seeing a sample. And here's the trap that bites every performance engineer: you take your sampled trace count and multiply by one-over-the-rate to "extrapolate" back to production volume. That works for exactly one kind of sampling. **Head sampling** — the decision is made up front, probabilistically — you can recover the real count, *if* the probability is propagated. OpenTelemetry's own spec gives you the math: the *adjusted count* of a sampled span is the reciprocal of its sampling probability. One over the rate. That's sanctioned. But **tail sampling** — keep the errors, keep the slow ones, decide *after* the trace finishes — is biased by construction and throws the reweighting factor away. You cannot extrapolate counts from tail-sampled data. Full stop. A respected OTel engineer, Goutham, put it bluntly: there is no way to generate accurate metrics from tail-sampled data — the metrics have to be generated *before* the sampling happens. So the fix, the rule we bake into the methodology: compare *rates*, not raw counts, and normalize every dataset by its own sampling ratio before you compare. Mismatched, unrecorded sampling is the number-one cause of a false "out of tolerance" verdict. Remember the number one-point-two-seven — I'm about to earn it.

### Slide 7 — State of RUM (10:00–12:00)
There's a second source of truth the trace stream doesn't have, and it's the one closest to your user: RUM. Real User Monitoring sits in the browser and the mobile app and records what *actually* happened to real people — the real journeys, the real arrival curve, the real device, geography, and network mix. Here's the proof point I like for this room: Google doesn't rank your site on Lighthouse — a lab test, synthetic. It ranks on *field* Core Web Vitals, from the Chrome User Experience Report, at the seventy-fifth percentile of real sessions. A page can ace the lab and fail the field. That gap — lab versus field — is exactly the gap between a synthetic load test and production. Now, the honest part, because you'll ask: OpenTelemetry *can* do RUM in the browser today, but the browser SDK and the session semantic conventions are still marked "Development" — not stable — and the vendor implementations ship as technical preview. So the production-grade RUM truth today still lives in your observability backend. In our case, that's two specific objects. Which is my second question.

### 💬 Slide 10 note — [Discussion #2 is slide 10; see below] — continue to slide 8 first.

### Slide 8 — Where the truth is stored: spans + RUM (12:00–14:00)
*(This is the "residual self image" slide.)* Here's the key mental model. Everything we build is a *projection* of reality — and like Neo's residual self image in the Construct, it's only as complete as the data behind it. Two stores feed the projection. Server-side traces live in **spans** — the service graph, fan-out, backend latency. The real user truth lives in **RUM** — and in our backend that's two DQL objects: `user.sessions`, one row per real session, and `user.events`, the ordered actions *inside* a session. Both keyed by `dt.rum.session.id`. Spans tell you what the services did; RUM tells you what the humans did. You need both, because each is blind where the other sees.

### Slide 9 — DQL: querying both worlds (14:00–16:00)
And you query both with one language — DQL. *(Show the three snippets.)* `fetch spans` for the service-side shape. `fetch user.sessions` for the real session population — live, that's thirty-five thousand sessions a day across five apps, web and mobile, and it's accessible right now. And `fetch user.events`, filtered by the session id, for the ordered journey and the exact think-times between actions. One honest caveat, on the slide: on our read token `user.events` is scope-gated — it needs a storage scope we've requested and haven't been granted yet. So the *ordered-journey* piece is proven in design and waiting on an admin. But — and this matters — the request-volume merge and that one-point-two-seven factor need only `user.sessions` plus spans, and those are live today. Which is where I earn the number.

### 💬 Slide 10 — Discussion #2 (16:00–17:30)
Second question, and this is the one I actually want to fight about. Do you trust sampled traces to size a load test? *(Let the room go. Expect a split. Push both sides.)* Here's my position, and you just saw the receipts: I trust them *only* after I've reconciled them against a less-sampled source and recorded the factor. On Astroshop, RUM saw twenty-six requests a second; the unsampled spans saw thirty-three. That's a one-point-two-seven multiplier — RUM captured seventy-nine percent of the real traffic. If I'd sized the test off RUM counts alone, I'd have under-loaded the system by twenty-one percent and called it a pass. *That's* the glitch in the Matrix, and that's why we extrapolate with a measured factor instead of a guess.

### Slide 11 — Let's use a skill (17:30–19:00)
So how do we make this repeatable instead of a one-off heroics project? We give an agent a *skill* — a versioned, deterministic capability — and a scope contract. The skill reads the telemetry and proposes a workload model: the journeys, their weights, the arrival shape, the think-times, the dataset sizing. The agent does the boring, mechanical extraction. But — and this is the spine of the whole method — the agent proposes; it does not decide. It operates inside a written contract: what it may read, hard caps, and a human gate before anything runs. Telemetry proposes. You dispose.

### Slide 12 — The engine: telemetry in, model out (19:00–21:00)
*(The Construct slide.)* "This is the Construct. It's our loading program. We can load anything." That's the engine. It's three layers, and the split is deliberate. A backend-specific **input adapter** pulls the raw telemetry — DQL for us, but it could be Tempo, Jaeger, Envoy logs — and normalizes it into one neutral schema. Then the **engine** — completely backend-agnostic, deterministic, offline-testable — turns that neutral telemetry into a workload model: front-end discovery, scenario clustering to about eighty percent coverage, per-scenario load via Little's Law, ramp shaping, dataset sizing. Telemetry in, model out, nothing about Dynatrace or k6 inside it. That determinism is the point — same telemetry, same model, every time.

### Slide 13 — One model, many worlds (21:00–22:30)
And once you have the model, here's the "guns, lots of guns" moment. *(Neo quote.)* One `workload-model.json`, and a registry of **renderers** materializes it into whatever tool you run: k6, JMeter, Locust, Gatling — all four exist today and all four pass their acceptance tests. Same model, same shape, four weapons. The tool stops being the thing you argue about. The *model* is the asset; the tool is a render target. Let me show you.

### Slides 14–17 — DEMO: load the program (22:30–27:30) — *narration; artifacts owned by C*
Watch the loading program run. *(Step 1)* Here's the Astroshop workload model — it came out of DQL: spans for the service shape, `user.sessions` for the real journeys, reconciled with that one-point-two-seven factor so the volume matches the unsampled truth. G0 checks are green. *(Step 2)* I hand that one model to the k6 renderer — out comes a k6 project: arrival-rate executor, think-times from the model, and every single request carries `synthetic=true` in baggage so I can find it later. *(Step 3)* Same model, JMeter renderer — out comes a `.jmx`: Concurrency thread group, Throughput Shaping Timer, CSV data sets for cache-busting. *(Step 4)* Put them side by side: same journeys, same weights, same arrival shape — two completely different tools. Guns, lots of guns. I'm running this from committed artifacts, not a live cluster, on purpose — trust the trace, not the demo. *(Fallback if time: narrate steps 1, 2, 4 only; drop JMeter detail.)*

### Slide 18 — The loop + the Oracle (27:30–29:00)
Zoom out: the whole thing is a five-stage loop. SCOPE — telemetry to model. VALIDATE — the human gate. SYNTHESIZE — model to test code. EXECUTE — the scoped run, tagged synthetic. ANALYZE — shape-diff against production, and iterate at most three times before it escalates to a human. And VALIDATE is the Oracle. *(Temet Nosce — "know thyself" — on screen.)* The agent can model, generate, run, and diff all day long. But whether *this* scenario is the right thing to test is a human judgment, bound by a hash to the exact model revision — change one field and the approval is void and the gate re-opens. No auto-approval, ever. Not on confidence, not on a similarity score, not on a deadline. That's what "delegate execution, not judgment" means in practice.

### Slide 19 — Honest limits: glitches in the Matrix (29:00–30:00) [FLEX]
Before I open it up — the glitches I haven't fixed, because an expert room deserves the caveats. One: we extract *and* validate from the same telemetry, so a shared blind spot — async fan-out, websockets, fire-and-forget — is invisible on both sides. We cross-check at least one run against infra metrics, not telemetry alone. Two: mean is not peak; we model mean arrival today and a peak-envelope profile is still on the backlog. Three: the ordered-journey RUM piece is waiting on a storage scope. And the deepest one — there is no spoon. The temptation, always, is to tune the test until the diff turns green. We cap iterations at three and escalate with evidence precisely so we bend the test toward reality, not toward passing.

### 💬 Slide 20 — Discussion #3 + close (30:00 → into Q&A)
So here's my last question, and then the floor is yours. If you walked out of here and took the red pill on exactly one service — one service you already observe well — which one would you red-pill first, and what's the one number in your current test for it that you've never been able to justify? *(Collect answers; tie back to the folklore from Discussion #1.)* That's the ask. Not "rebuild all your load testing." Pick one service, let the telemetry propose the model, you validate it, render it, run it scoped, diff the shape. One service. Stop guessing. Load the real world. Thank you.

---

# Part 4 — Per-slide copy (for UXDesigner / B)

*Format per slide: Title · Bullets (verbatim, ≤6 words each where possible) · Speaker-note pointer · Visual cue. Discussion slides are deliberately sparse.*

### Slide 1 — Title
- **There is no spoon**
- *Load-testing the real world*
- Henrik Rexed · IsItObservable · PAC 2026
- **Visual:** full-bleed near-black; digital code-rain (green) as a slow backdrop; title in white, "spoon" subtly glitched. Pills not needed yet.

### Slide 2 — The blue pill load test
- Blue pill: run the test you always run. Dashboard green. Believe what you want.
- Red pill: look at what production actually does.
- *"…how deep the rabbit hole goes."*
- This talk is the red pill.
- **Visual:** red-pill / blue-pill split, hand motif. Morpheus quote as a caption (verbatim, Part 2 §2.4). Blue side = a green-check dashboard; red side = a messy real traffic curve.

### Slide 3 — The basics: a load test must reflect real life
- Volume — "10× peak"? peak of *what*?
- Mix — 3 endpoints vs 40 in prod
- Pacing — thread-group defaults
- Payloads — 3 hardcoded blobs
- Shape mismatch = the test tests your imagination
- **Visual:** reuse v1 slide 4 — two overlaid arrival curves, flat synthetic ramp vs jagged production ("same average, different reality"). Four folklore boxes (Volume/Mix/Pacing/Payloads) each stamped "source: ???".

### Slide 4 — 💬 Discussion #1
- **Where do *your* numbers come from?**
- (who chose your RPS — and why?)
- **Visual:** near-empty slide, big question, a blinking terminal cursor `> _`. No bullets to read; this is a prompt for the room.

### Slide 5 — The evolution with OTel
- Metrics — the *what*
- Traces — the *why* + the path
- Logs — the detail
- For load tests, traces = journeys + fan-out + arrival curve
- But the red pill shows reality *through a sample*
- **Visual:** three correlated-signal panel; red-pill accent on "traces." Foreshadow the sample with a faint glitch at the edge.

### Slide 6 — The sampling trap *(glitch slide)*
- Déjà vu = a glitch in the Matrix
- Naive: count × 1/rate — **only valid for head sampling**
- Head: adjusted count = 1 / probability *(OTel spec)*
- Tail: reweighting thrown away — **you cannot extrapolate counts**
- Fix: compare **rates**, normalize each dataset's ratio
- **Visual:** THE glitch-treatment slide (reserve the effect for here). Trinity quote caption. A head-vs-tail split: head = clean reweight, tail = a "✗ cannot recover" stamp. Footer: `samplingFactor recorded in shape-diff.json`.

### Slide 7 — State of RUM
- RUM = the edge truth: real journeys, real arrival curve, real device/geo/network
- Google ranks on **field** CrUX @ 75th pct — not Lighthouse (lab)
- OTel browser SDK + session semconv = **Development**, not stable
- Vendor OTel-RUM = technical preview
- Production RUM truth today = your backend's `user.sessions`
- **Visual:** lab-vs-field split (Lighthouse gauge vs CrUX field histogram). Status pill badge "Development" on the OTel line (honesty). *Do not* use the market-size figure.

### Slide 8 — Where the truth is stored: spans + RUM
- *"Residual self image — the mental projection of your digital self"*
- The model is a **projection** — only as complete as your data
- Spans → service graph, fan-out, backend latency
- RUM → `user.sessions` + `user.events`, key `dt.rum.session.id`
- Spans = what services did · RUM = what humans did
- **Visual:** "residual self image" motif (a wireframe human projection). Two data stores feeding one model card. Key callout: `dt.rum.session.id`.

### Slide 9 — DQL: querying both worlds
- `fetch spans` — service-side shape
- `fetch user.sessions` — 35,679 sessions/24h, 5 apps (web+mobile), **live**
- `fetch user.events | filter dt.rum.session.id == …` — ordered journey + think-times
- ⚠ `user.events` scope-gated today (403) — volume merge needs only sessions + spans
- **Visual:** terminal/`>` styling for the three DQL snippets (green on black). A small "403 — pending scope" tag on the `user.events` line (honest, not hidden).

### Slide 10 — 💬 Discussion #2
- **Do you trust sampled traces to size a test?**
- Astroshop: RUM 25.94/s vs spans 33.03/s → **×1.27** (RUM saw 79%)
- Size off RUM alone → under-load by 21%, call it a pass
- **Visual:** the 1.27 reveal — two bars (RUM vs unsampled spans) with the ×1.27 bridge. This is the money slide; let it breathe.

### Slide 11 — Let's use a skill
- A skill = versioned, deterministic capability
- Reads telemetry → proposes a workload model (journeys, weights, arrival, think-times, data)
- Inside a scope contract: read-only inputs, hard caps, human gate
- The agent proposes; it does not decide
- **Visual:** scope-contract card (inputs / boundaries / human gate) + agent glyph on "execute", person glyph on "decide".

### Slide 12 — The engine: telemetry in, model out *(the Construct)*
- *"This is the Construct. It's our loading program."*
- Adapter (backend-specific) → **Engine** (agnostic, deterministic) → Renderers
- Engine: front-end discovery, ~80% scenario clustering, Little's Law load, ramp + dataset sizing
- Same telemetry → same model, every time
- **Visual:** the 3-layer engine diagram (primary diagram to draw). Construct white-void motif optional behind it. Label determinism.

### Slide 13 — One model, many worlds
- *"Guns. Lots of guns."*
- One `workload-model.json`
- Renderers: **k6 · JMeter · Locust · Gatling** (all pass acceptance tests)
- The model is the asset; the tool is a render target
- **Visual:** renderer fan-out diagram — one model → four tool logos. Weapon-rack motif (tasteful). This sets up the demo.

### Slides 14–17 — DEMO: load the program *(artifacts owned by C)*
- 14 — The model (from DQL: spans + `user.sessions`, ×1.27, G0 green)
- 15 — Model → **k6** (arrival-rate executor, `synthetic=true` baggage)
- 16 — Model → **JMeter** (Concurrency TG, Throughput Shaping Timer, CSV data sets)
- 17 — Side by side: same journeys/weights/shape, two tools
- **Visual:** screen-capture frames from C; keep chrome minimal; a persistent "running from committed artifacts" footer (trust-the-trace honesty). Coordinate exact framing with Observability Agent.

### Slide 18 — The loop + the Oracle
- SCOPE → VALIDATE → SYNTHESIZE → EXECUTE → ANALYZE (≤3 iterations, then escalate)
- VALIDATE = the Oracle. **Temet Nosce — know thyself**
- Approval is hash-bound to the model revision — change a field, gate re-opens
- No auto-approval: not confidence, not similarity, not a deadline
- **Visual:** the 5-stage loop diagram (primary diagram), human gate highlighted as the Oracle. "Temet Nosce" over the gate.

### Slide 19 — Honest limits: glitches in the Matrix
- Circular ground truth — extract + validate from same telemetry (cross-check infra metrics) [R5]
- Mean ≠ peak — peak-envelope profile on backlog [R2]
- Ordered-journey RUM waiting on `storage:user.events:read`
- There is no spoon: don't tune the test green — bend it to reality
- **Visual:** three "⚠ field notes" cards + a closing "there is no spoon" line. Honest, credible — this slide buys trust with experts.

### Slide 20 — 💬 Discussion #3 + close
- **What would you red-pill first?**
- One service you already observe — and the one number you can't justify
- The ask: telemetry proposes → you validate → render → run scoped → diff
- **Stop guessing. Load the real world.**
- **Visual:** red pill, single CTA bar. Code-rain returns (bookend with slide 1). QR to repo.

---

# Part 5 — Flags for C (technical fact-check) & open questions

**Please verify (workstream C — Observability Agent):**
1. **1.27 factor** (slides 10, 14) — confirm `25.94` RUM req/s, `33.03` span req/s, ratio `1.2735`, "~79% captured," and that it needs only `user.sessions` + spans (not `user.events`). Source: `isi5693-session-stitch.md` §8.1 + `merge-plan.json`.
2. **Head vs tail sampling claim** (slide 6) — confirm my framing of "adjusted count = 1/probability (OTel spec)" and "tail sampling cannot be extrapolated" is accurate and not overstated. Part 2 §2.1 sources.
3. **`user.events` 403 / scope-gated** (slide 9, 19) — confirm current state is still `missing storage:user.events:read` (per [ISI-5719](/ISI/issues/ISI-5719), re-confirmed 2026-10-12) so we don't claim it live on stage.
4. **35,679 sessions / 5 apps** (slide 9) — confirm still representative of the tenant; it's a 24h snapshot.
5. **Renderer matrix** (slide 13) — confirm k6 / JMeter / Locust / Gatling all currently pass acceptance tests (memory says yes: ISI-5656/57/58 + k6 done).
6. **OTel browser/session semconv = "Development"** (slide 7) — confirm wording; and ⚠ confirm the exact **Client-Side Telemetry SIG** name before we name it anywhere.
7. **G0 12/12 on the Astroshop model** (slide 14) — confirm `loadtests/wkf10640-astroshop-frontend/workload-model.json` is the demo source and still G0-green.

**Open questions for Henrik / board:**
- OK to **omit the RUM market-size figure** entirely and lead with the Google CrUX field-data point? (Recommended — stronger for this audience.)
- The **1.27 under-load framing** on slide 10 ("you'd under-load by 21% and call it a pass") — punchy and true; confirm you're comfortable saying it that bluntly to the council.
- Demo (slides 14–17) is **5 min** of a 30-min slot with 3 discussion beats — if the room runs hot on Discussion #2, I've written a fallback to compress the demo to ~3 min (drop JMeter detail). Acceptable?

**Handoff status:**
- Outline already posted to ISI-5722 for **B (UXDesigner)** — visual system + diagram list.
- This document = the full narrative + per-slide copy + research for **B to lay out** and **C to fact-check**.
- Theme locked; every themed line maps to a technical claim (Part 1 table).
