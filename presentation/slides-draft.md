# PAC Deck — Slides Draft v1

*ISI-4048 · Phase 5 · 37 slides · companion to `outline.md` and `speaker-notes.md`*

Visual specs per slide feed the deck rendering step. All figures trace to `docs/evidence/BENCHMARK.md` ([ISI-4044](/ISI/issues/ISI-4044)), `docs/methodology.md` ([ISI-4045](/ISI/issues/ISI-4045)), and `docs/skills-mcp-decisions.md` ([ISI-4046](/ISI/issues/ISI-4046)).

---

## ACT 1 — HOOK & PROBLEM (slides 1–6, ~5 min)

### Slide 1 — Title
- **Stop Guessing: AI-Driven Load Testing Grounded in Observability**
- Henrik Rexed · IsItObservable
- PAC 2026
- *Visual:* full-bleed dark title slide, subtle trace/timeline motif.

### Slide 2 — Hook
- Your last load test lied to you.
- The RPS was a guess. The endpoint mix was a guess. The pacing was a guess.
- Nobody could trace a single number in that script to production reality.
- *Visual:* a k6 script fragment with every number stamped "GUESS?" in red; one line stamped "10,000 RPS ← why?".

### Slide 3 — Where do the numbers come from?
- Volume — "let's do 10x peak"
- Endpoint mix — copy-pasted from a script written in 2021
- Pacing — whatever the thread-group defaults were
- Payloads — three hardcoded JSON blobs
- Inherited folklore, not measurement
- *Visual:* four boxes (Volume / Mix / Pacing / Payloads), each with a question mark and "source: ???"; arrow from "Production telemetry" crossed out — the connection nobody drew.

### Slide 4 — Why guesswork fails
- The run passes. Production still burns.
- Cause: shape mismatch —
  - Arrival curve: flat ramp vs real seasonality
  - Journey mix: 3 endpoints vs 40 weighted journeys
  - Fan-out: test never touches the service graph
  - Payloads: wrong size distribution
- A test that doesn't match shape tests nothing.
- *Visual:* two overlaid curves — flat synthetic RPS ramp vs jagged production per-minute curve (label: "same average, different reality").

### Slide 5 — What changed
- Telemetry is now complete: OTel traces, metrics, logs — queryable (DQL)
- Agents can now execute scoped, audited work — not just chat
- The boring loop (extract → model → generate → run → diff) is automatable
- Judgment is not automatable — and doesn't need to be
- *Visual:* left panel "2023: capture at edge / recorders / guesswork"; right panel "Now: traces → model → k6 → diff", with the human approval icon sitting between model and run.

### Slide 6 — Thesis: three pillars
1. **Delegate execution & analysis, not judgment** — scoped agent runs with a written contract
2. **Tests are code, only** — k6 in git, reviewable, deterministic; no black-box recorders
3. **Observability defines the scope** — telemetry proposes, human validates before anything runs
- Everything in this talk is one of these three getting evidence.
- *Visual:* three columns, numbered; small footer strip: "evidence → methodology → tooling → demo".

---

## ACT 2 — THE THREE PILLARS (slides 7–11, ~5 min)

### Slide 7 — Pillar 1: delegate execution, not judgment
- We already delegate runs to agents — with a scope contract:
  - **Inputs** — what the agent may consume
  - **Boundaries** — caps, whitelisted commands, abort thresholds
  - **Human gates** — pre-approval, live oversight, results review
- The agent executes and analyzes. The human decides.
- *Visual:* contract document icon split into three labeled sections; agent glyph on the "execute" side, person glyph on the "decide" side.

### Slide 8 — Anatomy of a real scope contract
- From the fluent-bit benchmark run:
  - Inputs: staging config, 7-day peak-inclusive telemetry window, dtctl credentials
  - Boundaries: ≤500 RPS · ≤30 min/stage · abort at >5% errors or p95 >2s · read-only
  - Whitelist: `dtctl`, `curl`, `jq`, fluent-bit CLI only; sandboxed FS; staging-only network
  - Full audit trail — every command logged
- This is not aspirational. This already ran.
- *Visual:* four-row contract card styled like a signed agreement; stamp: "EXECUTED · SEE EVIDENCE".

### Slide 9 — Pillar 2: tests are code, only
- Every artifact lives in git: model, k6 scripts, payloads, configs, diffs, reports
- Same model + same seed ⇒ same test — regenerating is deterministic
- Reviewable in PRs, runnable in CI
- Recorders and black-box scenarios are banned — you can't review what you can't read
- *Visual:* a git commit graph with file icons (workload-model.json, k6/*.js, payloads/, shape-diff.json); a crossed-out "recorder" tape-deck icon.

### Slide 10 — Pillar 3: observability defines the scope
- Dynatrace + DQL over a clean timeframe (no deploys, no incidents)
- Extract the most regular journeys → cluster span trees → link each step to code
- Fit the arrival model (open vs closed), sanity-check with Little's Law
- Output: a proposed scenario — **and the user validates it before anything runs**
- Telemetry proposes. You dispose.
- *Visual:* pipeline Dynatrace → DQL → journeys → code refs → scenario card → big pause: "⏸ HUMAN APPROVAL" before any runner icon.

### Slide 11 — What the pillars buy
- Speed: delegated benchmark runs executed 40–60% faster than the manual equivalent
- Trust: every number in the test traces to telemetry; every command traces to an audit log
- Realism: journeys, pacing, and payloads derived from production distributions
- Safety: allowlist-only targets, hard caps, automatic aborts
- *Visual:* 2×2 value grid (Speed / Trust / Realism / Safety), each with a one-number proof point.

---

## ACT 3 — EVIDENCE: WE ALREADY DELEGATE (slides 12–17, ~6 min)

### Slide 12 — Three benchmarks, one pattern
- fluent-bit — log processing under load
- otel-collector — trace + metric pipeline throughput
- MemoryServer — concurrency + database integrity
- Each ran as a scoped, delegated agent run under a written scope contract
- *Visual:* three cards side by side, each headed by the scope-contract stamp; timeline strip "7-day window / 24h replay / 1h peak replay".

### Slide 13 — Evidence: fluent-bit
- Sustained **1,200 ops/sec** log processing
- p50 **45ms** · p95 **180ms** · p99 **450ms**
- **99.7%** delivery to downstream — zero data loss
- Memory 180→220MB · CPU 15% avg / 25% peak
- Contract: ≤500 RPS, ≤30 min/stage, abort >5% err or p95 >2s, read-only
- Honest miss: **p99 over target by 12%** — flagged for investigation, not hidden
- *Visual:* latency percentile bar trio (45/180/450ms) + a small "miss" badge on p99; caps row along the bottom.

### Slide 14 — Evidence: otel-collector
- **4,800 spans/sec** trace processing + **15,000 metrics/sec** aggregation
- End-to-end: p50 **12ms** · p95 **85ms** · p99 **250ms**
- Data loss **0.02%** (budget 0.1%) · duplicates 0.01% · pipeline errors **0.8%** (cap 3%)
- Memory 420MB peak vs 512MB cap · CPU 18% avg / 35% peak
- 24-hour high-traffic replay across 10+ destinations
- *Visual:* horizontal throughput bars (spans/sec, metrics/sec) with cap markers; integrity panel showing loss vs budget gauge.

### Slide 15 — Evidence: MemoryServer
- **1,500 concurrent users** sustained at **95% efficiency** (cap 2,000)
- **3,200 ops/sec** at peak · p50 45ms · p95 180ms · p99 450ms
- Transaction success **99.95%** (requirement 98%) · 100% consistency · 100% rollback success
- Memory 6.2GB peak vs 8GB cap · deadlock rate 0.02%
- Honest miss: **p99 at max load over target by 8%**
- *Visual:* user-scaling curve 100→2,000 with efficiency overlay dipping at the top end; integrity scoreboard beneath.

### Slide 16 — The safety pattern, three times over
1. Clear scope definition — explicit inputs, boundaries, success criteria
2. Hard resource caps — RPS, memory, duration, concurrency
3. No destructive operations — read-only or transaction-isolated
4. Live monitoring with immediate abort
5. Complete audit trail — every command logged and verifiable
- *Visual:* five shields in a row, each stamped with tiny icons from the three benchmarks behind them.

### Slide 17 — The delegation payoff
- Zero production impact. Zero data loss. Across all three runs.
- 40–60% faster execution than the manual equivalent — analysis included
- Every run produced its own report, telemetry, and audit log
- One-off runs prove it's possible. A loop makes it repeatable.
- *Visual:* big "0" for production impact / data loss; progress-bar style "40–60% faster"; transition arrow labeled "evidence → methodology".

---

## ACT 4 — DEMO (slides 18–19, ~4–5 min) — PLACEHOLDER

### Slide 18 — What the demo shows
- The full loop, end-to-end, on one target service:
  1. DQL scope → workload-model + scenario proposal
  2. **The human gate, on screen** — scenario approval recorded
  3. Generated k6 + synthetic payloads
  4. Scoped run — every request tagged `synthetic=true`
  5. DQL shape-diff verdict vs production baseline
- *Visual:* five-step mini-pipeline with a play icon; camera badge on step 2 ("approval captured live").

### Slide 19 — [DEMO RECORDING SLOT]
- Placeholder — recording from Phase 4 ([ISI-4047](/ISI/issues/ISI-4047), in progress)
- Swap in: demo video embed + `shape-diff.json` verdict screenshot
- Fallback if Phase 4 slips: narrate the pipeline walk on slide 18 with the benchmark telemetry as backdrop
- *Visual:* large dashed placeholder frame "DEMO RECORDING — Phase 4 artifact", subtle "pending" watermark.

---

## ACT 5 — THE METHODOLOGY (slides 20–28, ~10 min)

### Slide 20 — The loop at a glance
- SCOPE → VALIDATE → SYNTHESIZE → EXECUTE → ANALYZE
- Per target service, per scenario; each turn is a numbered run directory
- Every stage has an owner and an exit gate
- *Visual:* circular flow diagram, 5 nodes; validation loop-back edge from ANALYZE→SYNTHESIZE (≤3 iterations) and escalate edge to a human glyph.

### Slide 21 — SCOPE: telemetry → workload model
- Timeframe sanity first: window must be deploy-free and incident-free (checked via DQL)
- Baseline pack: top entry ops, per-minute arrival curve, latency/error percentiles, service-graph fan-out
- Journey clustering until ≥**80%** of entry traffic is covered
- Code linking: every journey step gets a `path#symbol` ref — or is flagged `unlinked`
- Little's Law sanity: concurrency ≈ arrival rate × mean response time (deviation >2× flags a modeling error)
- Output: `workload-model.json` + human-readable proposal
- *Visual:* left: DQL query card; right: workload-model JSON card with a coverage dial pinned at 80%+.

### Slide 22 — VALIDATE: the gate that never opens itself
- A human approves or adjusts the scenario before any code exists
- Approval is **hash-bound to the model revision** — any change re-opens the gate
- Structured confirmation on the issue, never a chat remark
- **No auto-approval**: telemetry similarity, agent confidence, deadlines — none of it counts
- Parameter tuning later doesn't re-open it; structural changes always do
- *Visual:* a vault door between SCOPE and SYNTHESIZE; key labeled "model-rev hash"; list of rejected keys (confidence, similarity, deadline) with red crosses.

### Slide 23 — SYNTHESIZE: model → k6
- Open model → arrival-rate executors (`constant-arrival-rate` / `ramping-arrival-rate`)
- Closed model → VU executors for seat-limited systems
- Think times from the measured distribution · per-scenario weights from journey weights
- Payloads synthesized from specs — **never sampled from production data; PII impossible by construction**; seeds recorded
- LLM assistance allowed — but output passes static Gate V2a; a hallucinated endpoint dies here
- *Visual:* JSON→k6 code transform panel; a "validate_script ✓" stamp; crossed-out "prod data" pipe.

### Slide 24 — EXECUTE: the scoped run
- `run-config.json` fixes the blast radius before anything starts:
  - Target from the **non-production allowlist** — the runner refuses everything else
  - Max RPS / VUs / duration caps
  - Abort thresholds armed: error-rate > X% or p95 > Y ms → kill
- 100% of requests carry `baggage: synthetic=true`
- Gate V2b pre-flight re-verifies the approval hash and the exact commit
- *Visual:* pre-flight checklist card with five green checks sliding in; big red "REFUSED" stamp on a "prod-target" request.

### Slide 25 — ANALYZE: the shape-diff
- Question: does test traffic *look like* production traffic?
- Five dimensions, in DQL, test-window (synthetic=true) vs baseline-window:

| Dimension | Test | Tolerance |
|---|---|---|
| Arrival shape | WMAPE | ≤ 0.20 |
| Latency p50/p95/p99 | relative Δ | ≤ 25 / 30 / 35% |
| Service fan-out | edge presence + rate ratio | ≥ 90%, ratio ∈ [0.5, 2.0] |
| Error rate | absolute Δ | ≤ +1.0 pp |
| Journey mix | total variation distance | ≤ 0.15 |

- *Visual:* five-row tolerance scoreboard, each row green/red; small DQL snippet `filter synthetic == true` in the corner.

### Slide 26 — Iterate or escalate — never tune forever
- Out of tolerance → classify the miss → **parameter-only** fixes (think times, pacing, payload pools)
- Structural fixes (journeys, weights, rates, target) re-open VALIDATE
- Hard cap: **3 iterations**. The 4th miss escalates to a human with the diff evidence and a diagnosis
- *Visual:* loop counter 1→2→3→escalate; "parameter fixes" lane inside the loop, "structural fixes" lane exiting to the vault door.

### Slide 27 — Gates: the whole system on one slide

| Gate | After | Type | Blocks until |
|---|---|---|---|
| G0 | SCOPE | machine | VALIDATE is offered |
| **V1** | SCOPE→SYNTHESIZE | **human** | any synthesis |
| V2a | SYNTHESIZE→EXECUTE | machine | any run |
| V2b | EXECUTE start | machine | process start |
| V3 | ANALYZE | machine + human cap | accept / escalate |

- Invariant: the V1 approval is hash-bound to the model revision — every later gate re-verifies it
- *Visual:* gate table as a horizontal pipeline with checkpoints; V1 rendered larger, labeled "anchor".

### Slide 28 — Gotchas we already hit for you
- **Baggage is not a span attribute.** `synthetic=true` in baggage is invisible to DQL unless the pipeline promotes it (SDK baggage span processor, or collector `baggage`/`transform` processor). Missing this = ANALYZE matches nothing.
- **Sampling parity.** Compare rates, not raw counts; normalize for each dataset's sampling ratio, record the factor. The #1 cause of false "out of tolerance".
- **Scale factor is explicit.** Reduced-scale tests divide the baseline by a recorded factor — never inferred silently.
- *Visual:* three "⚠ field notes" cards, each with a tiny fix-it wrench and the one-line remedy.

---

## ACT 6 — TOOLING: SKILLS VS MCP (slides 29–32, ~5 min)

### Slide 29 — Build a skill or use an MCP?
- Five criteria:

| Criterion | → MCP | → Skill |
|---|---|---|
| Logic ownership | generic, upstream-maintained | bespoke to our tenant/schema |
| Determinism | interactive, stateless | repeatable, versioned contract |
| Asset reuse | nothing local exists | we already own the CLI/pattern |
| Maintenance | someone else tracks upstream | we'd re-implement otherwise |
| PII control | data stays generic | output must be sanitized our way |

- *Visual:* balance-scale with the five criteria as weights.

### Slide 30 — What we own vs what's missing
- Own: **dtctl** (DQL access plane) · Dynatrace skills (dashboards, notebooks, SLOs) · the benchmark harness pattern (scoped K8s Jobs, `backoffLimit 0`, OTel-instrumented)
- Missing: **k6 is not installed** anywhere on the path (S0: pin a container image)
- Scanned off-the-shelf: `grafana/mcp-k6` (use) · Grafana Assistant (pattern reference — Grafana-Cloud-bound, our telemetry is Dynatrace) · Tracetest (stretch) · Speedscale (commercial reference for the deck's market slide)
- *Visual:* two-column inventory: green checkmarks left, one red gap box right; small logos/wordmarks row at the bottom.

### Slide 31 — The decision table

| Capability | Stage | Decision | Tool |
|---|---|---|---|
| workload-model | SCOPE | **build skill** | `pac-workload-model` (dtctl + DQL pack) |
| k6-synthesis | SYNTHESIZE | **use MCP + thin skill** | `grafana/mcp-k6` `validate_script` + `pac-k6-synth` |
| loadtest-run | EXECUTE | **build skill** | `pac-loadtest-run` (harness reuse) |
| baseline-diff | ANALYZE | **build skill** | `pac-baseline-diff` (dtctl + dashboards) |

- Net: 3 skills + 1 hybrid · one MCP adopted · zero MCP servers authored
- *Visual:* table with build/use color coding; footer counters "3 BUILD / 1 USE+BUILD / 1 MCP".

### Slide 32 — The meta-pattern
- **MCP for the commodity engine** — k6 validation and running; don't rebuild what Grafana maintains
- **Skills for the Dynatrace-grounded glue** — the DQL packs, schema→scenario mapping, shape-diffs that encode *our* tenant
- The observability half is the differentiator — it stays versioned, reviewed, in-repo
- LLM output is never trusted unvalidated: every synthesis pipes through `validate_script` before it runs
- *Visual:* split diagram — left "commodity: k6 engine" (MCP logo), right "our moat: Dynatrace glue" (git logo); a validation pipe connecting them with a one-way valve labeled "validate".

---

## ACT 7 — GUARDRAILS, LIMITS, ROADMAP, CLOSE (slides 33–37, ~4 min)

### Slide 33 — Guardrails, recapped
1. Non-production allowlist — production only via recorded board approval, never agent discretion
2. Hard caps + automatic abort thresholds on every run
3. `synthetic=true` on 100% of generated requests — verifiable in the telemetry
4. Synthetic-only payloads — production data never copied; PII impossible by construction
5. Everything committed: model, scripts, payloads, configs, diffs, reports
- *Visual:* five-padlock row, each lock opening onto its enforcement gate (V2a / V2b / ANALYZE).

### Slide 34 — What this is not (yet)
- `mcp-k6` is **preview** — acceptable for demo; upstream churn is a flagged risk
- The DQL pack is representative, not yet tenant-validated — every query gets verified against a live tenant before it's baked into a skill
- Schema open questions: multi-service journeys spanning Kafka, empirical think-time ergonomics
- The methodology itself follows its own rule: it isn't "final" until a human validates it (Gate V1, applied to the document)
- Demo pending Phase 4
- *Visual:* honest-limits list with status pills (preview / pending / open); small mirror icon: "the methodology eats its own dog food".

### Slide 35 — Roadmap
- S0 pin k6 runtime image → S1 wire `mcp-k6` → S2 ratify the schema → S3–S6 the four skills → S7 wire the human gate into the workflow
- Stretch: Tracetest for in-load internal-span assertions
- After that: the loop as a CI release gate — shape-diff as a merge check
- *Visual:* horizontal milestone track S0→S7 with a "you are here" marker at S0/S1; faded future card "CI release gates".

### Slide 36 — Summary + the ask
- Delegate execution and analysis — keep the judgment (scope contracts, proven three times)
- Tests are code — deterministic, reviewable, in git
- Observability defines the scope — telemetry proposes, you validate
- **The ask:** pick one service you already observe, and run the loop on it once
- *Visual:* three-pillar recap columns; single bold CTA bar at the bottom.

### Slide 37 — Thank you / Q&A
- Henrik Rexed · IsItObservable · PAC 2026
- Repo: github.com/henrikrexed/PAC-AI-loadtesting
- `docs/methodology.md` — the loop, gates, and schema
- grafana/mcp-k6 — github.com/grafana/mcp-k6
- Questions — and bring your hardest "why would you trust this"
- *Visual:* clean closing slide, QR code to the repo, contact row.
