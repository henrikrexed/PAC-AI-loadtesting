# PAC Talk — *There Is No Spoon: Load-Testing the Real World*
## Narrative + Slide Copy + Research (Matrix theme)

*ISI-5722 (workstream A) · child of [ISI-5720](/ISI/issues/ISI-5720) · theme **The Matrix** 🔴💊 approved by the board (plan rev `d09391e7`)*
*Speaker: Henrik Rexed · IsItObservable · Format: PAC expert session, 30 min (~22 min content + ~8 min room discussion)*
*Draft v3 · 2026-10-13 · Content Writer*

> **rev3 changelog (accuracy fix, folds C's tech-accuracy review [ISI-5723](/ISI/issues/ISI-5723) §9):** the **1.27 factor is now framed as a RUM→span *coverage* ratio (samplingRatio = 1.0), not a trace-sampling inverse.** Slide 6 stays pure trace-sampling (head/tail, adjusted count); slide 10 owns the 1.27 coverage gap; the narrative explicitly says "same cure, different disease" so the two never conflate. Removes the internal contradiction with the live-demo line "sampling ratio one-point-zero, because this tenant is unsampled." Edits: Part 2.1, slide-6 & slide-10 narrative, slide-10 copy, Part 5 flag #1.

> **rev2 changelog (folded from [ISI-5720](/ISI/issues/ISI-5720) plan rev2):**
> 1. **New slide #13 — "Architecture: the stack in our cluster."** A recap of the real wired stack (Astroshop/otel-demo → OTel Collector → Dynatrace Grail spans+RUM → agent + skill + engine → renderers) with repo + all-asset links. All later slides shift +1 (old 13→14 … old 20→21).
> 2. **Demo (now slides 15–18) is FULL LIVE end-to-end.** No committed `workload-model.json` as the source: live DQL (`fetch spans` + `fetch user.sessions`) → materialize the Astroshop model → live V1 gate → render k6 + JMeter, on stage. The `user.events` 403 is narrated as a real "glitch in the Matrix"; a rehearsed recorded run is the fallback. Narration rewritten accordingly.
> 3. **Repo/asset links** added to the new #13 and the close slide (now #21).

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
| **"This is the Construct. It's our loading program. We can load anything…"** | The **engine** — loads a runnable world (the test config) from the model | 12, 13 |
| **"Guns. Lots of guns."** (materialize an arsenal on demand) | Renderers materialize **k6 / JMeter / Locust / Gatling** from one model | 14, 15–18 |
| **The Oracle** / **"Temet Nosce" — Know thyself** | The human **VALIDATE** gate — judgment stays human | 19 |
| **"There is no spoon… it is not the spoon that bends, it is only yourself"** | Don't bend the test to pass; bend the test to match reality | 1, 20, 21 |

**Theme discipline (for a sharp audience):** the theme is a thin framing layer. Use it in titles, section turns, and the three discussion beats. In the technical core (slides 5–14) let the numbers carry the weight and let the Matrix line be the *punctuation*, not the argument.

---

# Part 2 — Research pack (§4)

*Full sourcing so C can verify and so Henrik can answer hard questions from the floor. Tier flags included. Anything marked ⚠ needs confirmation before it goes verbatim on a slide.*

## 2.1 Sampling & extrapolation for performance engineers

**The claim we make:** a sampling *rate* corrupts naive **count-based** extrapolation, and the fix is **rate parity** — re-weight each dataset by its own sampling ratio and compare *rates*, never raw counts.

- **OpenTelemetry's own spec backs the fix (Tier 1).** The OTel *TraceState: Probability Sampling* spec defines **adjusted count** as *"the mathematical inverse (reciprocal) of the sampling probability — the expected number of times an item should be counted for it to be representative of the population."* i.e. `adjusted_count = 1 / probability`. That is exactly "normalize by the sampling ratio before you count." Source: <https://opentelemetry.io/docs/specs/otel/trace/tracestate-probability-sampling/> (status: Development). Design rationale: OTEP 0170 *Sampling probability* <https://github.com/open-telemetry/opentelemetry-specification/blob/main/oteps/trace/0170-sampling-probability.md>.
- **Head vs tail sampling — the distinction that decides whether extrapolation is even possible:**
  - **Head sampling** — keep/drop decided at trace *start*, probabilistically. You *can* recover population counts **if** the probability is propagated (OTel carries it in `tracestate` as the `th` threshold). Reweighting is valid.
  - **Tail sampling** — keep/drop decided *after* the trace completes (keep errors, slow traces, etc.). Outcome-biased, and it **does not propagate a reweighting factor**, so you **cannot** recover true counts/rates from tail-sampled data. Authority (Tier 2/3, a well-known OTel engineer): Goutham Veeramachaneni — *"There is no way to generate accurate metrics based on sampled data with tail-sampling … metrics need to be generated before the sampling happens."* <https://www.gouthamve.dev/sampling-at-scale-with-opentelemetry/>. Supporting: OTel blog *Tail Sampling* <https://opentelemetry.io/blog/2022/tail-sampling/>; Uptrace *Head-Based and Tail-Based Sampling* <https://uptrace.dev/opentelemetry/sampling>; Elastic *How we fixed head-based sampling in OpenTelemetry* <https://www.elastic.co/observability-labs/blog/how-we-fixed-head-based-sampling-in-opentelemetry>.
- **Our own live proof — the 1.27 *coverage* factor (internal, Tier 1 for us). ⚠ Precise framing, per C's tech-accuracy review ([ISI-5723](/ISI/issues/ISI-5723) §9):** this factor is **not** a trace-sampling inverse — on our Astroshop tenant the spans are **un-sampled** (`samplingRatio = 1.0`). 1.27 is a **source-coverage** factor: the *sibling* of the sampling lesson, not the sampling lesson itself. Over 24 h ([ISI-5693](/ISI/issues/ISI-5693)): RUM `user.sessions` captured **25.94 req/s**; the un-sampled span-observed volume was **33.03 req/s**. Ratio = 33.03 / 25.94 = **1.2735** (= 2,853,862 / 2,241,018 requests) — i.e. **RUM sees ~79 %** of the frontend requests the spans see, so the RUM-primary journey is scaled **×1.27** up to the span truth. Same *discipline* as sampling parity — *two sources at different capture rates → reconcile them and record the factor* — but driven by RUM coverage, not by a sampling ratio. Keep the two ideas distinct on stage (sampling = slide 6; the 1.27 coverage gap = slide 10). Source: `docs/evidence/isi5693-session-stitch.md` §8.1; `loadtests/wkf10640-astroshop-frontend/merge-plan.json` (`extrapolationFactor: 1.2735`, `samplingRatio: 1.0`).
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
This is the glitch in the Matrix. *(Trinity quote on screen.)* Déjà vu — you see the same cat twice — means they changed something. In telemetry, the thing that "changed" is that you're not seeing every request; you're seeing a sample. And here's the trap that bites every performance engineer: you take your sampled trace count and multiply by one-over-the-rate to "extrapolate" back to production volume. That works for exactly one kind of sampling. **Head sampling** — the decision is made up front, probabilistically — you can recover the real count, *if* the probability is propagated. OpenTelemetry's own spec gives you the math: the *adjusted count* of a sampled span is the reciprocal of its sampling probability. One over the rate. That's sanctioned. But **tail sampling** — keep the errors, keep the slow ones, decide *after* the trace finishes — is biased by construction and throws the reweighting factor away. You cannot extrapolate counts from tail-sampled data. Full stop. A respected OTel engineer, Goutham, put it bluntly: there is no way to generate accurate metrics from tail-sampled data — the metrics have to be generated *before* the sampling happens. So the fix, the rule we bake into the methodology: compare *rates*, not raw counts, and normalize every dataset by its own sampling ratio before you compare. Mismatched, unrecorded sampling is the number-one cause of a false "out of tolerance" verdict. And hold onto that *discipline* — reconcile your sources, record the factor — because in a minute I'll show you the same trap bite us on an **un-sampled** tenant, where nothing was sampled away and a second source *still* only saw part of the picture. That's a different glitch with the same cure. Remember the number one-point-two-seven.

### Slide 7 — State of RUM (10:00–12:00)
There's a second source of truth the trace stream doesn't have, and it's the one closest to your user: RUM. Real User Monitoring sits in the browser and the mobile app and records what *actually* happened to real people — the real journeys, the real arrival curve, the real device, geography, and network mix. Here's the proof point I like for this room: Google doesn't rank your site on Lighthouse — a lab test, synthetic. It ranks on *field* Core Web Vitals, from the Chrome User Experience Report, at the seventy-fifth percentile of real sessions. A page can ace the lab and fail the field. That gap — lab versus field — is exactly the gap between a synthetic load test and production. Now, the honest part, because you'll ask: OpenTelemetry *can* do RUM in the browser today, but the browser SDK and the session semantic conventions are still marked "Development" — not stable — and the vendor implementations ship as technical preview. So the production-grade RUM truth today still lives in your observability backend. In our case, that's two specific objects. Which is my second question.

### 💬 Slide 10 note — [Discussion #2 is slide 10; see below] — continue to slide 8 first.

### Slide 8 — Where the truth is stored: spans + RUM (12:00–14:00)
*(This is the "residual self image" slide.)* Here's the key mental model. Everything we build is a *projection* of reality — and like Neo's residual self image in the Construct, it's only as complete as the data behind it. Two stores feed the projection. Server-side traces live in **spans** — the service graph, fan-out, backend latency. The real user truth lives in **RUM** — and in our backend that's two DQL objects: `user.sessions`, one row per real session, and `user.events`, the ordered actions *inside* a session. Both keyed by `dt.rum.session.id`. Spans tell you what the services did; RUM tells you what the humans did. You need both, because each is blind where the other sees.

### Slide 9 — DQL: querying both worlds (14:00–16:00)
And you query both with one language — DQL. *(Show the three snippets.)* `fetch spans` for the service-side shape. `fetch user.sessions` for the real session population — live, that's thirty-five thousand sessions a day across five apps, web and mobile, and it's accessible right now. And `fetch user.events`, filtered by the session id, for the ordered journey and the exact think-times between actions. One honest caveat, on the slide: on our read token `user.events` is scope-gated — it needs a storage scope we've requested and haven't been granted yet. So the *ordered-journey* piece is proven in design and waiting on an admin. But — and this matters — the request-volume merge and that one-point-two-seven factor need only `user.sessions` plus spans, and those are live today. Which is where I earn the number.

### 💬 Slide 10 — Discussion #2 (16:00–17:30)
Second question, and this is the one I actually want to fight about. Do you trust a *single* source to size a load test? *(Let the room go. Expect a split. Push both sides.)* Here's my position, and you just saw the receipts. On Astroshop the spans are **un-sampled** — sampling ratio one-point-zero — so you'd think I'm safe from everything I just warned you about. But my richest journey source, RUM, only saw twenty-six requests a second where the spans saw thirty-three. That's a one-point-two-seven gap — RUM captured seventy-nine percent of the real traffic — and *not because anything was sampled away*. RUM and spans simply capture different slices of reality. If I'd sized the test off RUM counts alone, I'd have under-loaded the system by twenty-one percent and called it a pass. *That's* the glitch in the Matrix — not that a source was sampled, but that I believed one source. Reconcile them, record the factor — one-point-two-seven — and move on. Same cure as the sampling slide, different disease.

### Slide 11 — Let's use a skill (17:30–19:00)
So how do we make this repeatable instead of a one-off heroics project? We give an agent a *skill* — a versioned, deterministic capability — and a scope contract. The skill reads the telemetry and proposes a workload model: the journeys, their weights, the arrival shape, the think-times, the dataset sizing. The agent does the boring, mechanical extraction. But — and this is the spine of the whole method — the agent proposes; it does not decide. It operates inside a written contract: what it may read, hard caps, and a human gate before anything runs. Telemetry proposes. You dispose.

### Slide 12 — The engine: telemetry in, model out (19:00–21:00)
*(The Construct slide.)* "This is the Construct. It's our loading program. We can load anything." That's the engine. It's three layers, and the split is deliberate. A backend-specific **input adapter** pulls the raw telemetry — DQL for us, but it could be Tempo, Jaeger, Envoy logs — and normalizes it into one neutral schema. Then the **engine** — completely backend-agnostic, deterministic, offline-testable — turns that neutral telemetry into a workload model: front-end discovery, scenario clustering to about eighty percent coverage, per-scenario load via Little's Law, ramp shaping, dataset sizing. Telemetry in, model out, nothing about Dynatrace or k6 inside it. That determinism is the point — same telemetry, same model, every time.

### Slide 13 — Architecture: the stack in our cluster (21:00–21:45)
Before I run it, thirty seconds on what's actually wired up — because none of this is a slideware diagram, it's running in our cluster right now. *(Walk the arrows.)* The system under test is the **OpenTelemetry Demo** — Astroshop, a frontend and about fifteen microservices, instrumented with OTel. Its telemetry flows out over OTLP to an **OpenTelemetry Collector**, and the Collector ships it to **Dynatrace Grail**. Grail is where the two truths live: the **`spans`** table — the traces — and **RUM**, in `user.sessions` and `user.events`. On top of that sits the part we built: an **agent** that drives a versioned **skill**, which runs the **engine** — DQL in, workload model out — and then the **renderers** that materialize the model into k6 and JMeter. Two honest annotations on this diagram, because this room will look for them: the **logs** leg is drawn dashed — on this tenant the access-log probe comes back empty, so we're spans-and-RUM here, not logs. And the `user.events` arrow is dashed too — that's the scope-gated one, the glitch I'll hit live in a minute. Everything on the read path is **read-only, extraction-only, non-production**. All of this — the engine, the renderers, this exact demo — is in the repo; links are on screen and on the last slide.

### Slide 14 — One model, many worlds (21:45–22:45)
And once you have the model, here's the "guns, lots of guns" moment. *(Neo quote.)* One `workload-model.json`, and a registry of **renderers** materializes it into whatever tool you run: k6, JMeter, Locust, Gatling — all four exist today and all four pass their acceptance tests. Same model, same shape, four weapons. The tool stops being the thing you argue about. The *model* is the asset; the tool is a render target. And I'm not going to tell you it works — I'm going to do it, live, right now.

### Slides 15–18 — DEMO: load the program, LIVE (22:45–27:30) — *narration; artifacts owned by C*
This is the part where I don't trust the demo either — so we build it from scratch, on stage, against the live system. *(Step 0 — one command, `run-demo-live.sh`.)* *"I know kung fu."* *(Step 1 — telemetry → model, live.)* This isn't a model I saved yesterday. Right now it's running DQL against the live Astroshop — `fetch spans` for the service shape, `fetch user.sessions` for the real journeys — and materializing the model from what it sees this second. Watch the numbers land: three hundred thousand-plus frontend root traces, the order split coming out at roughly ninety-nine percent browsers and one percent buyers — *re-derived live, not a constant I typed in* — and sampling ratio one-point-zero, because this tenant is unsampled. The G0 gate runs on those fresh numbers: twelve of twelve, green. *(Step 1, the glitch.)* And there it is — watch the scroll — `fetch user.events` returns **four-oh-three, not authorized**. That's the real glitch in the Matrix. The ordered-journey table needs a storage scope we've asked for and haven't been granted. The extractor catches it and degrades to spans plus `user.sessions` — and nothing in this model depended on `user.events`, so the degrade is lossless. I'm showing you the failure on purpose: trust the trace, not the demo. *(The gate.)* Now the engine stops and asks a human — me — to approve what it just observed. *(Temet Nosce foreshadow.)* It will not synthesize a single request until I do. I approve. *(Step 2 — model → k6.)* *"Show me."* One command, and out of that one approved model comes a k6 project: ramping-arrival-rate executor — an open model — stages scaled straight off the weights, and `synthetic=true` in baggage on every request so I can find my own load later. V2a checks pass. *(Step 3 — model → JMeter.)* Same model, different gun: out comes a `.jmx` — Concurrency Thread Group, Throughput Shaping Timer, CSV data sets for cache-busting. Static checks pass. *(Step 4 — diff.)* Side by side: same journeys, same weights, same arrival envelope, same synthetic baggage — two completely different engines, zero hand-authoring. Guns, lots of guns. The model is the program; the renderer is just the compiler back-end. *(Fallback note for Henrik: if Step 0 reports the tenant unreachable, `run-demo-live.sh` tells you to switch to `run-demo.sh` — a rehearsed recorded run of this identical flow. Narrate it the same way; say once that it's the recorded fallback. If time is short, narrate steps 1, 2, 4 and drop the JMeter detail.)*

### Slide 19 — The loop + the Oracle (27:30–29:00)
Zoom out: the whole thing is a five-stage loop. SCOPE — telemetry to model. VALIDATE — the human gate. SYNTHESIZE — model to test code. EXECUTE — the scoped run, tagged synthetic. ANALYZE — shape-diff against production, and iterate at most three times before it escalates to a human. And VALIDATE is the Oracle — you just watched it fire, mid-demo, when the engine made me approve the model before it would render anything. *(Temet Nosce — "know thyself" — on screen.)* The agent can model, generate, run, and diff all day long. But whether *this* scenario is the right thing to test is a human judgment, bound by a hash to the exact model revision — change one field and the approval is void and the gate re-opens. No auto-approval, ever. Not on confidence, not on a similarity score, not on a deadline. That's what "delegate execution, not judgment" means in practice.

### Slide 20 — Honest limits: glitches in the Matrix (29:00–30:00) [FLEX]
Before I open it up — the glitches I haven't fixed, because an expert room deserves the caveats. One: we extract *and* validate from the same telemetry, so a shared blind spot — async fan-out, websockets, fire-and-forget — is invisible on both sides. We cross-check at least one run against infra metrics, not telemetry alone. Two: mean is not peak; we model mean arrival today and a peak-envelope profile is still on the backlog. Three: the ordered-journey RUM piece — you saw it four-oh-three on stage — is waiting on a storage scope. And the deepest one — there is no spoon. The temptation, always, is to tune the test until the diff turns green. We cap iterations at three and escalate with evidence precisely so we bend the test toward reality, not toward passing.

### 💬 Slide 21 — Discussion #3 + close (30:00 → into Q&A)
So here's my last question, and then the floor is yours. If you walked out of here and took the red pill on exactly one service — one service you already observe well — which one would you red-pill first, and what's the one number in your current test for it that you've never been able to justify? *(Collect answers; tie back to the folklore from Discussion #1.)* That's the ask. Not "rebuild all your load testing." Pick one service, let the telemetry propose the model, you validate it, render it, run it scoped, diff the shape. One service. Everything you just watched — the engine, the renderers, this live demo — is open; the repo and the asset links are on the screen behind me. Stop guessing. Load the real world. Thank you.

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
- Astroshop spans are **un-sampled** (ratio 1.0) — yet RUM 25.94/s vs spans 33.03/s
- **×1.27 coverage gap** — RUM saw 79% of real traffic (not sampled away — different slice)
- Size off *one* source → under-load by 21%, call it a pass
- The cure = reconcile sources, record the factor (same as sampling, different cause)
- **Visual:** the 1.27 reveal — two bars (RUM vs un-sampled spans) with the ×1.27 bridge, labelled "coverage gap, not sampling." This is the money slide; let it breathe.

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

### Slide 13 — Architecture: the stack in our cluster *(rev2 new)*
- *"This is the Construct…"* — the real wired stack, not slideware
- Astroshop (OTel Demo: frontend + ~15 services) → **OTel Collector** → **Dynatrace Grail**
- Grail: `spans` (traces) + RUM (`user.sessions`, `user.events`) — read via **DQL / `dtctl`**
- **agent → skill → engine (DQL in, model out) → renderers (k6 · JMeter)**
- **V1 human gate** between extract and render (renderers refuse an unapproved model)
- read-only · extraction-only · non-production · tenant-isolated
- **Repo + assets:** `github.com/henrikrexed/AI-Performance-Testing` → `skills/workload-model` (extract+schema+gates) · `skills/{k6,jmeter,locust,gatling}-synthesis` + `skills/renderer-kit` (render) · `skills/loadtest-run` (execute) · `loadtests/wkf10640-astroshop-frontend/` (this demo)
- **Visual:** the cluster-stack architecture diagram (NEW primary diagram for B). Left→right pipeline. Draw the **logs** leg **dashed** = "unavailable on this tenant (spans-only)"; draw the **`user.events`** edge **dashed/glitch** = "403, scope-gated (ISI-5719)". Mark the **V1 gate** as an explicit lock between engine and renderers. Repo link + QR corner. ⚠ links must resolve in the public mirror before QR goes live (ISI-5659 publication gate).

### Slide 14 — One model, many worlds
- *"Guns. Lots of guns."*
- One `workload-model.json`
- Renderers: **k6 · JMeter · Locust · Gatling** (all pass acceptance tests)
- The model is the asset; the tool is a render target
- **Visual:** renderer fan-out diagram — one model → four tool logos. Weapon-rack motif (tasteful). This sets up the live demo.

### Slides 15–18 — DEMO: load the program, LIVE *(artifacts owned by C)*
- 15 — **Live DQL → model:** `run-demo-live.sh` runs `fetch spans` + `fetch user.sessions` on stage → materializes the model → **G0 12/12**. Live numbers (re-derived, not constants): ~321k root traces, browser ~99% / buyer ~1%, `samplingRatio` 1.0. **No pre-baked model.**
- 16 — **The glitch:** `fetch user.events` → **403** scrolls by → degrade to spans + `user.sessions` (lossless). Then the **V1 gate** fires — presenter approves, live.
- 17 — Approved model → **k6** (ramping-arrival-rate, `synthetic=true` baggage) · **JMeter** (Concurrency TG, Throughput Shaping Timer, CSV) — both green
- 18 — Side by side: same journeys/weights/arrival envelope, two engines, zero hand-authoring
- **Visual:** live terminal capture (green-on-black); keep chrome minimal. Footer flips from "LIVE — DQL against Astroshop" to a small "recorded fallback" badge only if Henrik switches to `run-demo.sh`. Highlight the **403 line** and the **gate prompt** as on-screen beats. Coordinate exact framing with Observability Agent.

### Slide 19 — The loop + the Oracle
- SCOPE → VALIDATE → SYNTHESIZE → EXECUTE → ANALYZE (≤3 iterations, then escalate)
- VALIDATE = the Oracle (you watched it fire mid-demo). **Temet Nosce — know thyself**
- Approval is hash-bound to the model revision — change a field, gate re-opens
- No auto-approval: not confidence, not similarity, not a deadline
- **Visual:** the 5-stage loop diagram (primary diagram), human gate highlighted as the Oracle. "Temet Nosce" over the gate.

### Slide 20 — Honest limits: glitches in the Matrix
- Circular ground truth — extract + validate from same telemetry (cross-check infra metrics) [R5]
- Mean ≠ peak — peak-envelope profile on backlog [R2]
- Ordered-journey RUM waiting on `storage:user.events:read` (you saw the 403 live)
- There is no spoon: don't tune the test green — bend it to reality
- **Visual:** three "⚠ field notes" cards + a closing "there is no spoon" line. Honest, credible — this slide buys trust with experts.

### Slide 21 — 💬 Discussion #3 + close
- **What would you red-pill first?**
- One service you already observe — and the one number you can't justify
- The ask: telemetry proposes → you validate → render → run scoped → diff
- **It's all open:** `github.com/henrikrexed/AI-Performance-Testing` (methodology + engine + renderers + this demo)
- **Stop guessing. Load the real world.**
- **Visual:** red pill, single CTA bar. Code-rain returns (bookend with slide 1). Repo link + **QR to repo** (same QR as #13). ⚠ QR gated on ISI-5659 public-mirror publication.

---

# Part 5 — Flags for C (technical fact-check) & open questions

*Note (rev2): C has already rebuilt the live demo + extended the accuracy review to the arch slide under [ISI-5723](/ISI/issues/ISI-5723) rev2 (commit `97913df`; `TECH-ACCURACY-REVIEW.md` §8 arch + §9 live). The items below are reconciled against that review — slide numbers updated for the +1 shift.*

**Please verify (workstream C — Observability Agent):**
1. **1.27 factor** (slide 10, Discussion #2) — confirm `25.94` RUM req/s, `33.03` span req/s, ratio `1.2735`, "~79% captured," and that it needs only `user.sessions` + spans (not `user.events`). Source: `isi5693-session-stitch.md` §8.1 + `merge-plan.json`. **RESOLVED per C's review ([ISI-5723](/ISI/issues/ISI-5723) §9):** reframed throughout as a **RUM→span *coverage* factor (samplingRatio = 1.0)**, explicitly *not* a trace-sampling inverse — sampling lives on slide 6, the 1.27 coverage gap on slide 10, and the narrative now says "same cure, different disease" so the two never conflate. *(Live-demo headline stays the observed browser/buyer split, not 1.27 — confirm that split is right to present this way.)*
2. **Head vs tail sampling claim** (slide 6) — confirm my framing of "adjusted count = 1/probability (OTel spec)" and "tail sampling cannot be extrapolated" is accurate and not overstated. Part 2 §2.1 sources.
3. **`user.events` 403 / scope-gated** (slides 9, 13, 16, 20) — confirm current state is still `missing storage:user.events:read` (per [ISI-5719](/ISI/issues/ISI-5719)) so the 403 is a reproducible on-stage beat, and the degrade to spans + `user.sessions` is lossless for this demo. (§9 confirms reproducible on cue.)
4. **35,679 sessions / 5 apps** (slide 9) — confirm still representative of the tenant; it's a 24h snapshot.
5. **Renderer matrix** (slide 14) — confirm k6 / JMeter / Locust / Gatling all currently pass acceptance tests (memory says yes: ISI-5656/57/58 + k6 done).
6. **OTel browser/session semconv = "Development"** (slide 7) — confirm wording; and ⚠ confirm the exact **Client-Side Telemetry SIG** name before we name it anywhere.
7. **Live demo numbers** (slides 15–16) — per §9 live run: ~321k frontend root traces, browser ~99% / buyer ~1%, `samplingRatio` 1.0, G0 12/12, k6 V2a + JMeter J1–J7 green. ⚠ **Live volumetrics vary by window** — narration says "what the system is doing right now," not fixed constants; confirm that's the right framing for latency/concurrency/trace-count numbers.
8. **Architecture slide #13 accuracy** (rev2 new) — confirm the pipeline (Astroshop/OTel Demo → Collector → Grail spans+RUM → agent/skill/engine → renderers) and the two dashed-edge annotations: **logs = unavailable on this tenant (spans-only)**, **`user.events` = 403 scope-gated**. The V1 gate sits between extract and render and is code-enforced. (§8.)
9. **Repo/asset links** (slides 13, 21) — confirm each path resolves in the public mirror `github.com/henrikrexed/AI-Performance-Testing` **before** the QR/links go on the slide; publication is gated on [ISI-5659](/ISI/issues/ISI-5659). Flag to Graphic Designer (B) not to bake a QR that 404s.

**Open questions for Henrik / board:**
- OK to **omit the RUM market-size figure** entirely and lead with the Google CrUX field-data point? (Recommended — stronger for this audience.)
- The **1.27 under-load framing** on slide 10 ("you'd under-load by 21% and call it a pass") — punchy and true; confirm you're comfortable saying it that bluntly to the council.
- Demo (slides 14–17) is **5 min** of a 30-min slot with 3 discussion beats — if the room runs hot on Discussion #2, I've written a fallback to compress the demo to ~3 min (drop JMeter detail). Acceptable?

**Handoff status:**
- Outline already posted to ISI-5722 for **B (UXDesigner)** — visual system + diagram list. **rev2 adds one primary diagram for B:** the slide-#13 cluster-stack architecture diagram (left→right pipeline, dashed logs + dashed `user.events` glitch edges, explicit V1 gate lock, repo/QR corner).
- This document = the full narrative + per-slide copy + research for **B to lay out** and **C to fact-check**.
- Theme locked; every themed line maps to a technical claim (Part 1 table).
- **rev2 delta (2026-10-13):** new slide #13 (architecture); demo (15–18) rewritten as **full live e2e** matching [ISI-5723](/ISI/issues/ISI-5723) `run-demo-live.sh` (live DQL → model → V1 gate → k6+JMeter), the `user.events` 403 narrated as a reproducible "glitch," recorded fallback flagged; repo/asset links on #13 and #21; all slides after 12 shifted +1 (now 21 slides).
