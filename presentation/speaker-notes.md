# PAC Deck — Speaker Notes v1

*ISI-4048 · Phase 5 · first person, spoken register · target ≈ 35 min + Q&A*

Timing budget is cumulative. [FLEX] marks optional material to cut for a 30-minute slot.

---

### Slide 1 — Title (0:00–0:30)
Hi, I'm Henrik Rexed, and this channel is IsItObservable. Today's talk is about load testing — specifically, about why most load tests are fiction, and about a loop we've built that derives them from production telemetry instead. AI agents run the loop. You keep the judgment. Thirty-five minutes, three benchmarks of evidence, one honest demo of the limits. Let's go.

### Slide 2 — Hook (0:30–1:15)
Your last load test lied to you. Not on purpose — nobody sets out to build a misleading test. But open that k6 script and ask one question: where did the ten thousand requests per second come from? Who chose the endpoint mix? In almost every team I've worked with, the honest answer is a shrug. The numbers were inherited, guessed, or copy-pasted from a script someone wrote years ago. And then we make capacity decisions based on that.

### Slide 3 — Where do the numbers come from? (1:15–2:15)
Break a typical test down and it's folklore all the way down. Volume: "let's do ten times peak" — peak of what, measured when? Mix: three endpoints in the script, forty in production. Pacing: whatever the thread-group defaults happened to be. Payloads: three hardcoded JSON blobs. Each of those is a guess multiplied by every other guess. The test runs, the dashboard goes green, and none of it was ever connected to your actual traffic.

### Slide 4 — Why guesswork fails (2:15–3:30)
Here's the failure mode that costs real money. The run passes. Production still burns a week later. Why? Shape. If your synthetic arrival curve is a flat ramp and production has a jagged, seasonal, bursty curve — same average, completely different reality — your test exercised the system in a state it never occupies. Wrong journey mix, same problem: the test never touches the fan-out that actually breaks. A load test that doesn't match production shape doesn't test your system. It tests your imagination.

### Slide 5 — What changed (3:30–4:45)
Two things changed recently, and their intersection is this talk. First, telemetry got complete. With OpenTelemetry everywhere, we have traces, metrics, and logs that are actually queryable — in our case through Dynatrace and DQL. Second, AI agents got to the point where they can execute real, scoped, audited work — run commands, write files, analyze results — not just chat about it. The loop I'll show you — extract, model, generate, run, diff — has always been boring, mechanical work. Boring and mechanical is exactly what agents are good at. What was never boring is deciding what's worth testing. That stays with you.

### Slide 6 — Thesis (4:45–5:30)
The whole talk sits on three pillars. One: delegate execution and analysis, never judgment — every agent run happens inside a written scope contract. Two: tests are code, only — versioned, reviewed, deterministic; no black-box recorders. Three: observability defines the scope — telemetry proposes a scenario, a human validates it before a single request flies. Everything after this slide is one of those three pillars getting evidence. Keep score.

### Slide 7 — Pillar 1 (5:30–6:30)
We already delegate execution. Not in theory — we've done it, three times, on real systems, which I'll show shortly. The trick is the scope contract. It has three sections. Inputs: exactly what the agent may consume. Boundaries: hard caps, a whitelist of allowed commands, abort thresholds. And human gates: pre-approval, live oversight during the run, results review after. The agent executes and analyzes within that contract. The decisions — what to test, whether the result is acceptable — those never leave the human.

### Slide 8 — Scope contract anatomy (6:30–7:45)
This is a real one, from our fluent-bit benchmark. Inputs: the staging configuration, a seven-day peak-inclusive telemetry window, and read access to Dynatrace through dtctl. Boundaries: max five hundred requests per second, max thirty minutes per stage, automatic abort if error rate crosses five percent or p95 crosses two seconds, strictly read-only operations. Commands whitelisted to dtctl, curl, jq, and the fluent-bit CLI. Filesystem sandboxed to the test directory. And every single command logged. This isn't a proposal slide. This contract executed. The evidence act is coming.

### Slide 9 — Pillar 2 (7:45–8:45)
Pillar two: tests are code — and I mean only code. The workload model, the k6 scripts, the payload pools, the run configs, the shape-diffs, the reports: all of it lives in git. Same model plus same seed produces the same test, byte for byte. That's what makes it reviewable — you can actually read a diff of what changed in your load test between this week and last week. Try that with a recorder. Recorders and black-box scenario builders are banned from this loop, precisely because you can't review what you can't read.

### Slide 10 — Pillar 3 (8:45–10:00)
Pillar three is where the realism comes from: observability defines the scope. We point DQL at a clean timeframe — no deploys, no incidents, checked automatically — and extract the baseline. Top entry operations, the per-minute arrival curve, latency and error percentiles, the service-graph fan-out. Then we cluster traces into journeys until we cover at least eighty percent of entry traffic, and link every step of every journey to actual code — file path and symbol. Fit the arrival model, sanity-check with Little's Law, and out comes a proposed scenario. Proposed. The user validates it before anything runs. Telemetry proposes, you dispose.

### Slide 11 — What the pillars buy (10:00–10:45) [FLEX]
What does this buy you? Speed: the delegated benchmark runs executed forty to sixty percent faster than the manual equivalent. Trust: every number in the test traces back to telemetry, every command to an audit log. Realism: journeys, pacing, and payloads derived from measured distributions. Safety: allowlist-only targets, hard caps, automatic aborts. Nothing on this slide is a promise — all four quadrains have receipts, starting now.

### Slide 12 — Evidence intro (10:45–11:30)
Evidence act. Three systems, three delegated benchmark runs: fluent-bit for log processing under load, the OpenTelemetry Collector for pipeline throughput, and MemoryServer for concurrency and database integrity. Different systems, different failure modes — and the exact same scope-contract pattern every time. That repetition is the point: the pattern generalizes.

### Slide 13 — fluent-bit (11:30–12:45)
fluent-bit first. Sustained twelve hundred operations per second of log processing. p50 at forty-five milliseconds, p95 at one-eighty, p99 at four-fifty. Delivery rate ninety-nine point seven percent to downstream — zero data loss, zero corruption. Memory moved from a hundred-eighty to two-twenty megabytes; CPU never crossed twenty-five percent. Notice the caps along the bottom — that's the contract from slide eight, enforced. And notice the badge on p99: it came in twelve percent over target. We flagged it. That's what delegated analysis looks like when it's honest — it surfaces the miss instead of burying it.

### Slide 14 — otel-collector (12:45–14:00)
The collector run replayed a twenty-four-hour high-traffic window across ten-plus destinations. Forty-eight hundred spans per second on the trace side, fifteen thousand metrics per second on aggregation. End-to-end latency: p50 twelve milliseconds, p95 eighty-five, p99 two-fifty. Now the integrity numbers, because for a telemetry pipeline those are the whole game: data loss zero point zero two percent against a zero-point-one budget. Pipeline error rate zero point eight percent against a three percent cap. Memory peaked at four-twenty against a five-twelve cap. Every threshold had headroom, and the run proved it — not me, the run.

### Slide 15 — MemoryServer (14:00–15:15)
MemoryServer was the stress case: a ten-gigabyte dataset, up to two thousand concurrent users, one hour of peak-traffic replay. It sustained fifteen hundred concurrent users at ninety-five percent efficiency, thirty-two hundred ops per second at peak. Transaction success: ninety-nine point nine-five percent, against a ninety-eight percent requirement. Data consistency checks passed at one hundred percent. Every test transaction rolled back cleanly — that's the isolation discipline doing its job. The honest miss, again on the slide: p99 at maximum load, eight percent over target. Two of three benchmarks flagged a p99 miss. Keep that in mind for the limits act — the loop's value is that it finds these, not that it hides them.

### Slide 16 — Safety pattern (15:15–16:00) [FLEX]
Zoom out and the three runs share one skeleton. Clear scope definition, explicit inputs and boundaries and success criteria. Hard resource caps — rate, memory, duration, concurrency. No destructive operations — read-only, or transaction-isolated with rollback. Live monitoring with immediate abort. And a complete audit trail, every command logged and verifiable. Five rules, three systems, zero production impact.

### Slide 17 — Delegation payoff (16:00–16:45)
Score it. Production impact: zero. Data loss: zero. Across all three runs. Execution speed: forty to sixty percent faster than doing it by hand — and that includes the analysis, the reports, the telemetry artifacts, the audit log, all produced by the run itself. So the precedent question — "would you let an agent near your staging environment?" — is answered. We did, three times, with contracts, and it worked. But one-off runs only prove possibility. To make it repeatable, you need a loop. Which brings us to the methodology.

### Slide 18 — What the demo shows (16:45–17:45)
This is where the demo goes — the full loop on a single target service, end to end. DQL scope producing the workload model and scenario proposal. Then the human gate, captured on screen: the approval, recorded and bound to the model revision. Generated k6 with synthetic payloads. The scoped run, every request tagged synthetic-equals-true. And finally the DQL shape-diff verdict against the production baseline.

### Slide 19 — Demo slot (17:45–22:00) [PLACEHOLDER]
[Placeholder — Phase 4 recording goes here, [ISI-4047](/ISI/issues/ISI-4047) in progress. Fallback narration if the recording slips: walk slide 18's pipeline against the benchmark telemetry, and close with "same gates, same contracts, one loop."] Speak over the recording: call out the approval moment — "this click is the whole governance model" — and pause on the shape-diff verdict screen.

### Slide 20 — The loop (22:00–23:00)
Here's the loop that makes it repeatable. Five stages. Scope: telemetry analysis produces the model. Validate: the human gate. Synthesize: model becomes k6 code. Execute: the scoped delegated run. Analyze: shape-diff against the production baseline. It runs per target, per scenario, and every turn is a numbered run directory in the repo — nothing ephemeral. Note the edges: iterate loops back to synthesize, but only three times, and then it escalates to a human. We'll unpack each stage.

### Slide 21 — SCOPE (23:00–24:30)
Scope starts with a sanity check people skip: is the analysis window clean? If a deploy landed mid-window or an incident was burning, your "baseline" is contaminated. DQL checks that automatically; if it fails, the window shrinks or shifts, and the proposal says why. Then the baseline pack: top entry operations by volume, the arrival curve at one-minute resolution, latency and error percentiles per operation, the service-graph fan-out. Traces get clustered into journeys — keep going until you cover at least eighty percent of entry traffic, and record each journey's weight and think-time distribution. Every journey step gets linked to code, path-and-symbol, or explicitly flagged as unlinked. Little's Law as the arithmetic sanity check: concurrency should equal arrival rate times response time; if it's off by more than two-x, the model is wrong somewhere. Output: a JSON workload model plus a proposal written for humans.

### Slide 22 — VALIDATE (24:30–25:45)
This is the slide I'd keep if I could only keep one. The gate between "proposed" and "anything happens" is a human. Not a heuristic, not a confidence score, not a deadline. Rules: the approval is a structured confirmation recorded on the issue, bound to a specific model revision by hash. Change the model afterward — even one field — the approval is invalidated and the gate re-opens. No auto-approval, ever; telemetry similarity doesn't count, agent confidence doesn't count, schedule pressure really doesn't count. And the scope is precise: parameter tuning during analysis doesn't re-open the gate, structural changes always do. This is what "delegate execution, not judgment" means in practice.

### Slide 23 — SYNTHESIZE (25:45–27:00)
From approved model to code. Open workload model — public API — you get arrival-rate executors: constant or ramping. Closed model, seat-limited systems: VU executors. Think times come from the measured distribution, not a default. Scenario weights come from the journey weights in the model. And the payloads: synthesized from field specs — types, generators, distributions — never sampled from production data. PII isn't redacted out; it's impossible by construction, because production data never enters the pipeline. The LLM is allowed to help write this code. But its output passes static gate V2A first: syntax check, every request carries the synthetic baggage tag, payload pools match specs, declared rates fit the caps, and it's committed. A hallucinated endpoint dies right here, quietly, before it can waste a run.

### Slide 24 — EXECUTE (27:00–28:00)
Execution is the scope contract, formalized as a run config that gets written before anything starts. Target environment — must be on the non-production allowlist; the runner hard-refuses anything else, and production exceptions require a recorded board approval, never agent discretion. Caps on rate, VUs, and duration. Abort thresholds armed before the process spawns: error rate over the line or p95 over the line, and it kills itself. Every request carries baggage synthetic-equals-true. And the pre-flight gate re-verifies the approval hash and checks that the static gate passed on the exact commit being run. Nothing about the blast radius is negotiable at runtime — it was all decided in the config.

### Slide 25 — ANALYZE (28:00–29:15)
Then the question that actually matters: does the test traffic look like production traffic? Five dimensions, all computed in DQL, test window filtered by synthetic-equals-true against the baseline window. Arrival shape, weighted absolute percent error, tolerance point-two. Latency deltas: twenty-five percent at p50, thirty at p95, thirty-five at p99. Fan-out: at least ninety percent of baseline downstream edges present during the test, with per-edge rates within a half to two-x band. Error rate within one point of the baseline. Journey mix, total variation distance, under point-one-five. All five green, the run is accepted. Any red, we iterate.

### Slide 26 — Iterate or escalate (29:15–30:00)
Iteration has rules, because unbounded tuning is how you get a test that matches nothing but itself. If a dimension misses, classify the miss, then adjust parameters only — think times, pacing, payload pools. Structural changes — different journeys, different weights, different rates, different target — always go back through the human gate. And the cap is hard: three iterations. The fourth miss escalates to a human with the diff evidence and a diagnosis attached. The loop is not allowed to quietly tune forever. That's a feature, not a limitation.

### Slide 27 — Gates (30:00–30:45)
The whole system on one slide. G0, machine-checked, gates the model itself — schema valid, coverage met, journeys linked, Little's Law sane. V1, the human gate, blocks all synthesis. V2A, static checks, blocks any run. V2B, pre-flight, blocks process start. V3, the shape tolerance, decides accept or escalate. And the invariant running through all of it: the V1 approval is hash-bound to the model revision, and every later gate re-verifies that hash. Anchor that and the rest of the loop can be as automated as you like.

### Slide 28 — Gotchas (30:45–31:45) [FLEX]
Three field notes before anyone hits them. One: baggage is not a span attribute. You tagged everything synthetic-equals-true and DQL sees nothing — because baggage is a context-propagation mechanism, and it needs to be promoted to a span attribute, in the SDK or in a collector processor, before any backend can filter on it. The loop asserts a non-zero synthetic span count in a warm-up probe before computing any diff — zero means your promotion is missing, not that your shapes match. Two: sampling parity. If production is sampled at five percent and your test isn't, comparing raw counts is comparing fiction. Compare rates, normalized, with the factor recorded. That's the number-one cause of false out-of-tolerance verdicts. Three: when the test runs at reduced scale, the scaling factor gets recorded explicitly — never inferred, never silent.

### Slide 29 — Build vs use (31:45–32:30)
Now the tooling question: for each capability in the loop, do we build a skill — a versioned asset in our repo — or use an MCP server someone else maintains? Five criteria decide it. Who owns the logic — generic engine, or bespoke to our tenant? Do we need determinism and versioning, or is it interactive? Do we already own a local equivalent? Who carries the maintenance? And does output need sanitizing to our conventions before it leaves? The pattern that falls out is almost embarrassingly clean.

### Slide 30 — Inventory (32:30–33:15)
What we already own: dtctl — our DQL access plane for Dynatrace; the Dynatrace skills for dashboards, notebooks, and SLOs; and the benchmark harness pattern from the evidence act — scoped Kubernetes jobs, backoff-limit zero, OTel-instrumented, surviving driver teardown. What we don't own: k6. It isn't installed anywhere on the path — first backlog item, pin a container image. We scanned the shelf: Grafana's mcp-k6 server is genuinely useful; Grafana Assistant proves the natural-language-to-k6 pattern but it's bound to Grafana Cloud and our telemetry lives in Dynatrace; Tracetest is a stretch add-on for in-load span assertions; Speedscale is the commercial reference point for what this loop does self-hosted.

### Slide 31 — Decision table (33:15–34:15)
The decisions. Workload modeling: build — the DQL is specific to our tenant and our schema, and it must be deterministic and versioned. That's a skill. k6 synthesis: use Grafana's mcp-k6 for validation and guided generation — it's a commodity, don't rebuild it — plus a thin skill that maps our model to k6 executors and shapes PII-free payloads. Execution: build, reusing the benchmark harness — this is literally the pillar-one thesis with a k6 container swapped in. Baseline diff: build — we've written this exact keyed DQL comparison twice already for dashboard locking; this adds the synthetic filter and tolerances. Net result: three skills, one hybrid, one MCP adopted, zero MCP servers authored.

### Slide 32 — Meta-pattern (34:15–35:00)
Compress that table into one sentence: MCP for the commodity engine, skills for the Dynatrace-grounded glue. The k6 half of the loop is undifferentiated heavy lifting that Grafana maintains better than we would. The observability half is our moat — the query packs and mappings that encode our tenant — and that stays versioned, reviewed, in-repo. And one rule spans both: LLM output is never trusted unvalidated. Every synthesis pipes through validate-script before it's allowed anywhere near a target.

### Slide 33 — Guardrails recap (35:00–35:40)
Quick recap of the guardrail stack, because this is the part your security team will ask about. Allowlist-only targets, production exceptions via recorded board approval. Hard caps and armed abort thresholds on every run. Synthetic-equals-true on one hundred percent of generated requests — verifiable, not aspirational. Synthetic-only payloads, so PII is impossible by construction. And everything committed — model, scripts, payloads, configs, diffs, reports. If it ran, it's in git.

### Slide 34 — What this is not (35:40–36:30)
What this is not, yet. mcp-k6 is preview software — fine for the demo, and we're flagging upstream churn as a real risk. The DQL pack you saw is representative, not yet validated against a live tenant; every query gets confirmed before it's baked into a skill. The schema has open questions — multi-service journeys spanning Kafka, think-time ergonomics. And in what I consider the best detail of this whole project: the methodology applies its own rule to itself. It's a document that demands human validation gates — so it isn't final until a human validates it. It eats its own dog food.

### Slide 35 — Roadmap (36:30–37:15)
The path from here: pin the k6 runtime image, wire up mcp-k6, ratify the schema, build the four skills in dependency order, wire the human gate into the workflow. Tracetest as a stretch. And the destination I'm most interested in: the loop as a CI release gate — shape-diff as a merge check, so "does this release still behave like production under load" becomes a build result instead of a post-incident question.

### Slide 36 — Summary + ask (37:15–38:00)
Three pillars. Delegate execution and analysis, never judgment — proven three times with scope contracts. Tests are code — deterministic, reviewable, in git. Observability defines the scope — telemetry proposes, you validate. One ask: pick a single service you already observe well, and run this loop on it once. Scope it, validate it, run it scoped, diff the shape. One service. That's how this starts.

### Slide 37 — Close (38:00–38:30 + Q&A)
Thank you. Everything is public: the repo with the methodology, the evidence pack, and the decision analysis is at github.com/henrikrexed/PAC-AI-loadtesting, and Grafana's mcp-k6 is linked too. I'm Henrik Rexed — IsItObservable. Questions — and bring the hard ones. "Why would you trust this?" is my favorite, because the answer is a hash-bound approval and an audit log, and I love showing them off.

---

## Delivery notes
- **Pacing anchors:** evidence act ends ≈16:45; demo ends ≈22:00; methodology ends ≈31:45. If you're past an anchor by more than 2 min, apply [FLEX] cuts (slides 11, 16, 28) to land ≤40 min.
- **[FLEX] cuts** trim ≈3 min combined; dropping the demo recording to 2 min (narrated pipeline walk) saves another 3.
- Numbers are sourced from the Phase 1–3 docs; do not round differently on stage than on slides.
- Phase 4 demo slot: when [ISI-4047](/ISI/issues/ISI-4047) lands, replace slide 19 and re-time Act 4.
