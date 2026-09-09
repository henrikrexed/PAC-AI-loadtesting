# PAC Presentation Outline — AI-Driven Load Testing

*ISI-4048 · Phase 5 · draft v1 · 2026-09-09*

**Working title:** *Stop Guessing: AI-Driven Load Testing Grounded in Observability*
**Alternates:** *From Traces to Load Tests: An AI Loop You Can Trust* · *Delegate the Test, Keep the Judgment*
**Format:** 30–45 min talk (35–38 min content + Q&A), ~37 slides
**Speaker:** Henrik Rexed, IsItObservable
**Reviewer:** Henrik reviews the final deck before PAC submission

## Source material mapping

| Deck act | Source | Issue |
|---|---|---|
| Evidence act | `docs/evidence/BENCHMARK.md` | [ISI-4044](/ISI/issues/ISI-4044) (done) |
| Methodology act | `docs/methodology.md` v0.2 | [ISI-4045](/ISI/issues/ISI-4045) (done) |
| Tooling act | `docs/skills-mcp-decisions.md` | [ISI-4046](/ISI/issues/ISI-4046) (done) |
| Demo act | **PLACEHOLDER** — Phase 4 in progress | [ISI-4047](/ISI/issues/ISI-4047) (in progress) |
| Foundation | `research/loadtesting-from-observability.md` | [ISI-4032](/ISI/issues/ISI-4032) |

## Narrative arc

*We already delegate execution credibly (evidence) → here is the loop that makes it repeatable (methodology) → here is the tooling that makes it cheap (skills/MCP) → here is it working end-to-end (demo, pending Phase 4).*

The through-line: **trust**. Every act answers the same skeptic question — "why would you let an AI agent near your staging environment?" — with a different proof: precedent (benchmarks), process (gates), tooling (determinism), demonstration.

## Act structure and timing

### Act 1 — Hook & problem (slides 1–6, ~5 min)
- **1 Title.** Talk title, speaker, channel.
- **2 Hook.** "Your last load test lied to you." Numbers were guesses; nobody could trace them to reality.
- **3 The guesswork problem.** Where do the numbers in your k6 script come from? Volume, mix, pacing, payloads — usually inherited folklore.
- **4 Why guesswork fails.** Test shape ≠ production shape: arrival curve, journey mix, fan-out, payload distributions. Shape mismatch = wasted run.
- **5 What changed.** Two enablers converged: full-fidelity telemetry (OTel/Dynatrace) and agents that can run scoped, audited work. The loop is now automatable — judgment doesn't have to be.
- **6 Thesis.** Three pillars on one slide. Everything after this is one of the three pillars getting evidence.

### Act 2 — The three pillars (slides 7–11, ~5 min)
- **7 Pillar 1.** Delegate execution & analysis, not judgment. Scope contract = inputs + boundaries + human gates.
- **8 Scope contract anatomy.** The contract from the fluent-bit benchmark as the concrete instance (commands whitelist, sandbox, caps, aborts, audit trail).
- **9 Pillar 2.** Tests are code. k6 in git, reviewable, CI-runnable, deterministic given model + seed. No black-box recorders.
- **10 Pillar 3.** Observability defines the scope. DQL timeframe → journeys → code-link → scenario → **human validates before anything runs**.
- **11 What the pillars buy.** Speed (40–60% faster execution), trust (audit trail), realism (telemetry-derived), safety (allowlist + caps).

### Act 3 — Evidence: we already delegate (slides 12–17, ~6 min)
- **12 Evidence intro.** Three delegated benchmark runs already happened. Same scope-contract pattern each time.
- **13 fluent-bit.** 1,200 ops/sec sustained; p50 45ms / p95 180ms / p99 450ms; 99.7% delivery; caps 500 RPS / 30 min stages; abort >5% err or p95 >2s. Honest miss: p99 over target by 12%.
- **14 otel-collector.** 4,800 spans/sec + 15,000 metrics/sec; p50 12ms / p95 85ms / p99 250ms; loss 0.02% vs 0.1% budget; error 0.8% vs 3% cap; 420MB peak vs 512MB cap.
- **15 MemoryServer.** 1,500 concurrent users at 95% efficiency; 3,200 ops/sec; 99.95% txn success vs 98% requirement; 6.2GB peak vs 8GB cap; 100% rollback success. Honest miss: p99 at max load over target by 8%.
- **16 Safety patterns ×3.** Clear scope, hard resource caps, read-only/no-destruction, live monitoring + abort, full audit trail.
- **17 Delegation payoff.** Zero production impact, zero data loss, 40–60% faster than manual, analysis included. Transition: "one-off runs prove it's possible; a loop makes it repeatable."

### Act 4 — Demo (slides 18–19, ~4–5 min) — **PLACEHOLDER until [ISI-4047](/ISI/issues/ISI-4047) lands**
- **18 What the demo shows.** The 5 stages end-to-end on one target: DQL scope → scenario approval (the human gate, on screen) → generated k6 → scoped run with synthetic=true → DQL shape-diff verdict.
- **19 [DEMO RECORDING SLOT].** Placeholder slide; swap in the Phase 4 recording/artifacts when available.

### Act 5 — The methodology (slides 20–28, ~10 min)
- **20 The loop.** SCOPE → VALIDATE → SYNTHESIZE → EXECUTE → ANALYZE diagram; per-stage owner and exit gate table.
- **21 SCOPE.** Timeframe sanity (deploy/incident-free windows), DQL baseline pack, journey clustering to ≥80% coverage, code linking (`path#symbol`), Little's Law sanity check, `workload-model.json` + proposal. Gate G0 machine checks.
- **22 VALIDATE.** The human gate. Structured confirmation hash-bound to the model revision; any change re-opens the gate; no auto-approval, ever. "Never skipped, never retro-active."
- **23 SYNTHESIZE.** Model → k6: arrival-rate executors for open models, VU executors for closed; think times from the model; synthetic payloads (PII-free by construction, seeded for determinism). Gate V2a static checks; hallucinated endpoints fail here.
- **24 EXECUTE.** Scoped delegated run: `run-config.json` fixes blast radius — allowlist-only targets, max RPS/VUs/duration, armed abort thresholds. Gate V2b pre-flight.
- **25 ANALYZE.** Shape-diff in DQL, filtered by synthetic=true: five dimensions with tolerances (WMAPE ≤0.20; latency Δ ≤25/30/35%; fan-out ≥90% edges; error Δ ≤+1pp; journey TVD ≤0.15).
- **26 Iterate or escalate.** Parameter-only fixes loop ≤3 times; structural changes re-open VALIDATE; 4th miss escalates to human with diff evidence. No silent tuning forever.
- **27 Gate summary.** G0 / V1 / V2a / V2b / V3 table. Invariant: V1 approval hash-bound to model revision — every later gate re-verifies it.
- **28 The gotchas.** Baggage is not a span attribute by default — promote `synthetic=true` or ANALYZE matches nothing; sampling parity (compare rates, not counts); explicit scaling factor. These bite everyone the first time.

### Act 6 — Tooling: skills vs MCP (slides 29–32, ~5 min)
- **29 Decision framework.** Five criteria: ownership of logic, determinism/versioning, asset reuse, maintenance cost, cardinality/PII control.
- **30 Inventory.** What we own: dtctl, Dynatrace skills, benchmark harness pattern. Gap: k6 not installed. Off-the-shelf scanned: mcp-k6, Grafana Assistant (pattern), Tracetest (stretch), Speedscale (market reference).
- **31 Decision table.** Build `pac-workload-model`; use `grafana/mcp-k6` + thin `pac-k6-synth`; build `pac-loadtest-run` (harness reuse); build `pac-baseline-diff`. Net: 3 skills + 1 hybrid, one MCP adopted, zero authored.
- **32 Meta-pattern.** MCP for the commodity engine (k6 validate/run); skills for the Dynatrace-grounded glue. The Dynatrace half is the differentiator and stays versioned in-repo.

### Act 7 — Guardrails, limits, roadmap, close (slides 33–37, ~4 min)
- **33 Guardrails recap.** Non-production allowlist; hard caps + automatic aborts; synthetic=true on 100% of traffic; synthetic-only payloads; everything committed.
- **34 Honest limits.** mcp-k6 is preview; DQL pack not yet tenant-validated; schema open questions (multi-service journeys, think-time ergonomics); methodology itself awaits board validation; demo pending.
- **35 Roadmap.** S0 k6 runtime → S1 mcp-k6 wiring → S3–S6 the four skills → S7 human gate wiring; Tracetest stretch.
- **36 Summary + ask.** Three pillars, one loop, evidence-backed. The ask: run the loop on one service you already observe.
- **37 Thank you / Q&A.** Links: repo, methodology doc, mcp-k6, IsItObservable.

## Flex cuts (to hit 30–35 min)
1. Slide 11 (pillars payoff) — fold into slide 6 transition.
2. Slide 16 (safety patterns) — compress into slide 17.
3. Slide 28 (gotchas) — tease in talk, details in blog post.
4. Demo act — if Phase 4 recording is short, 2 min instead of 5.

## Handoff
- Henrik reviews outline + slides draft + speaker notes (this folder).
- After approval: render final deck via ppt-master (design confirmations at that point), drop in Phase 4 demo artifacts when [ISI-4047](/ISI/issues/ISI-4047) lands.
