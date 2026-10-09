# Skills vs MCP — Decision Analysis for the AI Load-Testing Loop

*Parent ISI-4032 (plan rev 1, approved 2026-09-08) · Phase 3 · issue ISI-4046
(supersedes cancelled duplicate ISI-4043) · authored by the Observability Agent · 2026-09-08*

## Purpose

Decide, per capability of the AI-driven load-testing methodology, whether to **build a
skill** (a versioned, deterministic prompt+script asset in this repo, grounded in our own
stack) or **use an MCP server** (an off-the-shelf tool surface we call). The output is a
decision table with rationale plus an implementation backlog that Phase 4 (ISI-4047, demo)
and Phase 5 (ISI-4048, deck) can build on.

Capabilities (from the issue) map onto the 5-stage loop that Phase 2 (ISI-4045,
`docs/methodology.md`, backup_Architect) is formalizing:

| Capability | 5-stage loop stage | One-line |
|---|---|---|
| (a) workload-model | **SCOPE** | production traces → journey + distribution digest (JSON) |
| (b) k6-synthesis | **SYNTHESIZE** | workload-model → k6 script + synthetic payload data |
| (c) loadtest-run | **EXECUTE** | scoped, delegated run + OTel result capture (`synthetic=true`) |
| (d) baseline-diff | **ANALYZE** | test telemetry vs production baseline, shape-diff in DQL |

The **VALIDATE** stage (stage 2, mandatory human gate — Henrik approves the scenario before
anything runs) is a workflow rule, not a tooling capability, so it has no build/use row; it
is enforced as a hard gate *between* (a) and (b) in every skill below.

---

## Decision framework: when to build a skill vs use an MCP

We applied five criteria. A capability leans **MCP** when it is a maintained commodity
engine; it leans **skill** when it is bespoke glue over our own stack that must be
deterministic and version-controlled.

| Criterion | Favours **use-MCP** | Favours **build-skill** |
|---|---|---|
| **Ownership of the logic** | Generic, upstream-maintained (e.g. "run a k6 script") | Bespoke to *our* Dynatrace tenant, schema, or harness |
| **Determinism / versioning** | Interactive, exploratory, stateless | Must be a repeatable, reviewable contract in the loop (observability-as-code) |
| **Existing asset reuse** | No local equivalent exists | We already own the CLI/pattern (dtctl, benchmark harness) |
| **Maintenance cost** | Someone else maintains the binary/protocol | We would otherwise re-implement + track a moving upstream |
| **Cardinality/PII control** | Data stays generic | Output must be sanitized/shaped to our conventions before it leaves |

**Meta-pattern that fell out of this analysis:** *MCP for the commodity k6 engine
(validate/run); skills for the Dynatrace-grounded bespoke glue (workload extraction, schema→k6
mapping, baseline-diff); reuse the benchmark harness for delegated scoped execution.* The
Dynatrace half of the loop is our differentiator and stays as versioned skills; the k6 half
is a commodity we should not rebuild.

---

## Inventory

### Existing assets we own (reuse first)

| Asset | What it is | Where | Reuse for |
|---|---|---|---|
| **dtctl** | kubectl-style Dynatrace CLI: `query` (DQL), `exec`, `apply`/`create` (workflows, documents, SLOs, notebooks), `find`, `describe`, `verify`. Installed at `~/.local/bin/dtctl`. | local | (a) SCOPE DQL extraction, (d) ANALYZE DQL diff — the Dynatrace access plane for the whole loop |
| **Dynatrace skills (this agent)** | `dt-app-dashboards` (mandatory 7-step dashboard workflow, 24-col grid), notebook/workflow/SLO creation, DQL run, discovery capabilities | agent persona | (d) render baseline-diff as a versioned dashboard/notebook; SLO gates |
| **Dynatrace MCP** (discovery/MCP-powered features) | `discover-services`, `discover-metrics`, `analyze-logs`, build-diagnostic-notebook | agent persona | interactive supplement to (a)/(d) — *not* the deterministic path |
| **Benchmark harness pattern** | Proven "delegate execution with a scope": ConfigMap-scoped campaign **Jobs** (`backoffLimit 0`, `activeDeadline`), OTel auto-instrumentation, collector `benchmark_only` tap (`^benchmark-` filter), autonomous in-cluster runs surviving teardown, `two_pass_report`, dashboard-lock via DQL diff | `/mnt/nas/project/conference-talks/memory-benchmark` (fluent-bit / otel-collector / MemoryServer benchmarks) | (c) EXECUTE — the scoped-delegated-run substrate; (d) the DQL-diff pattern (ISI-3243/ISI-3221) is directly transferable |
| **Collector redaction/SLO pipeline** | `memory_limiter`→…→redaction→`tail_sampling`→`batch`, PII double-guard, off-by-default SLO rules (ISI-3723) | k8squad helm | (c) sanitize + tag synthetic traffic; keep test telemetry off prod SLOs |

**Gap:** **k6 is not installed** on this host (`which k6` → none). Gatling/Locust likewise
absent. Any execution path needs k6 provisioned (container image or binary) — backlogged
below.

### Off-the-shelf evaluated

| Option | What it gives | Verdict |
|---|---|---|
| **`grafana/mcp-k6`** (official k6 MCP server, Go, *preview*) | `validate_script` (1 VU/1 iter smoke), `run_script` (VUs/duration/stages), k6 docs browsing, guided script generation — callable from any MCP client | **OPTIONAL dev-loop convenience — NOT a dependency** (revised per board direction [ISI-5622](/ISI/issues/ISI-5622), 2026-10-09). We do **not** use it to *generate* scripts (generation is our own deterministic renderer) nor rely on it for execution (the **k6 binary** in our scoped harness is the engine). May be used ad hoc for a `validate_script`/`run_script` dev smoke. Exact capability (launch-only vs also validate/generate) to be confirmed under [ISI-5635](/ISI/issues/ISI-5635). |
| **Grafana Assistant — NL→k6 script authoring** | Proves the pattern: natural language + telemetry → validated k6 scripts, grounded in Grafana Cloud telemetry | **Pattern reference, do not adopt as tool.** Grafana-Cloud-bound; our telemetry is in Dynatrace. We replicate the *pattern* (LLM + validation loop) locally, grounded in our workload-model + `mcp-k6` `validate_script`. |
| **Tracetest** (trace-based assertions; k6 integration) | Trigger request → wait for trace → assert on spans; strongest dedicated trace-based-testing tool in 2026 | **Optional Phase 4+ add-on**, not a core loop capability. Complements (d) with internal-span assertions during load; parked as a stretch backlog item, not a decision-table row. |
| **Speedscale** | OTel-trace-based traffic replay + CI release gates | **Commercial reference only** (per issue). Closest off-the-shelf to "replay from observability"; cite in the deck as the market comparison, do not adopt. |
| `grafana/xk6-mcp` | k6 extension to *load-test MCP servers* | **Not relevant** — inverse of our need. Noted to avoid confusion. |

---

## Decision table (core deliverable)

| # | Capability | Decision | Primary tool | Bespoke glue we build | Rationale (dominant criterion) |
|---|---|---|---|---|---|
| **a** | **workload-model** (SCOPE) | **BUILD SKILL** | dtctl (`query` DQL) | `pac-workload-model` skill: parameterized DQL set → RPS profile, endpoint mix, latency p50/p95/p99, error/retry, span-tree journeys, service graph, think-time; emits **workload-model JSON** (schema owned by Phase 2) | Bespoke to our Dynatrace tenant + our JSON schema; must be deterministic & versioned (observability-as-code). No MCP maps "DT traces → workload-model." Reuses dtctl we already own + ISI-3243/3221 DQL. |
| **b** | **k6-synthesis** (SYNTHESIZE) | **BUILD SKILL (own the generation)** | our deterministic renderer + k6 binary `--dry-run`; `mcp-k6 validate_script` optional | `pac-k6-synth` renderer: map workload-model JSON → k6 scenarios (arrival-rate *open* executors for public APIs, VU *closed* for seat-limited; Little's Law check) + PII-free synthetic payloads matching prod distributions; **own static checker (V2a)** | Generation must be deterministic & golden-testable → we own the renderer, not an MCP (board direction ISI-5622). No dependency on `mcp-k6` guided generation. |
| **c** | **loadtest-run** (EXECUTE) | **BUILD SKILL (reuse harness)** | Benchmark harness pattern (scoped K8s Job) + k6 runtime; `mcp-k6 run_script` for dev loop | `pac-loadtest-run` skill: package a k6 script as a **scoped** run (ConfigMap Job, `backoffLimit 0`), OTel metrics/traces export, **`synthetic=true`** resource attr/baggage, artifact capture | This *is* the parent's "delegate execution with a proper scope" thesis — our harness already proves it (fluent-bit/otel-collector/MemoryServer). No new MCP; wrap what we own. `mcp-k6 run_script` covers only the local dev loop, not scoped/delegated in-cluster runs. |
| **d** | **baseline-diff** (ANALYZE) | **BUILD SKILL** | dtctl (`query` DQL) + `dt-app-dashboards` skill | `pac-baseline-diff` skill: DQL comparing `synthetic=true` test window vs prod baseline window — RPS shape, latency histograms, service fan-out, error rates — against tolerance thresholds → pass/fail + iterate signal; optional versioned DT dashboard/notebook | Direct transfer of the ISI-3243/ISI-3221 dashboard-lock DQL-diff pattern. Must be deterministic, thresholded, versioned — a skill, not interactive MCP. Dynatrace MCP is a discovery supplement only. |

**Summary:** 4 skills to build (a, b, c, d) — **script generation is ours** (deterministic
renderers), not delegated to any MCP (board direction [ISI-5622](/ISI/issues/ISI-5622),
2026-10-09). `grafana/mcp-k6` is an **optional dev-loop convenience, not a dependency**; the k6
**binary** is the execution engine. Zero net-new MCP servers authored. dtctl carries both
Dynatrace-facing stages.

---

## Per-capability rationale (detail)

### (a) workload-model → BUILD SKILL `pac-workload-model`
The digest is only as good as the DQL behind it, and that DQL is specific to *our* tenant's
span/metric attributes and to the workload-model JSON contract Phase 2 defines. A skill lets
us version the query set, review it, and re-run it deterministically each loop iteration —
core to "observability as code." Dynatrace MCP `discover-services`/`discover-metrics` is
useful for the *first* interactive pass to find the right entities, but the repeatable digest
must be a fixed DQL skill. Cardinality guard: cap journey enumeration to the top-N most
regular traces (the issue's "most regular traces") to avoid dimensional explosion.

### (b) k6-synthesis → BUILD `pac-k6-synth` renderer (own the generation; MCP is not a dependency)
**Revised per board direction ([ISI-5622](/ISI/issues/ISI-5622), 2026-10-09): do not rely on the
k6 MCP to generate scripts.** Script generation is our own **deterministic renderer** (model →
k6), so output is reproducible and golden-testable — we never delegate generation to `mcp-k6`'s
"guided generation" or any LLM-authoring surface. The bespoke core is translating our
workload-model JSON into correct k6 executors (open arrival-rate vs closed VU, ramp shapes,
think-time) and generating synthetic payloads matching production distributions **without PII**.
Validation of the generated script is done by a **deterministic static checker we own** (V2a); a
k6 `validate_script` (via `mcp-k6` *or* `k6 --dry-run` on the binary) may be used as an *optional*
extra smoke in the local dev loop, but is **not** required or depended upon. Gated behind stage-2
human VALIDATE. (Whether `mcp-k6` even offers more than launch is being confirmed under
[ISI-5635](/ISI/issues/ISI-5635).)

### (c) loadtest-run → BUILD SKILL `pac-loadtest-run` (reuse benchmark harness)
This capability is the literal demonstration of the parent's first thesis: *test execution
can be delegated with a proper scope, exactly as we did on the fluent-bit / otel-collector /
MemoryServer benchmarks.* The harness pattern (ConfigMap-scoped Job, `backoffLimit 0`,
`activeDeadline`, autonomous in-cluster, OTel-instrumented, `benchmark_only` collector tap)
transfers almost unchanged; we swap the bench-driver for a k6 container. Requirements the
skill enforces: k6 OTel output (`xk6-output-opentelemetry` / native OTel metrics), a
`synthetic=true` resource attribute + W3C baggage on all generated traffic so the ANALYZE
stage and prod SLOs can separate test from real, and artifact capture (summary JSON + run id).
`mcp-k6 run_script` is fine for the local dev inner-loop but is **not** the scoped/delegated
in-cluster path.

### (d) baseline-diff → BUILD SKILL `pac-baseline-diff` (dtctl + dt-app-dashboards)
We have already built this exact shape twice (ISI-3243 dashboard-lock, ISI-3221 comparative
dashboard): keyed DQL comparison of two windows over latency histograms, throughput, resource,
error rate. Here the key is the time window + `synthetic=true` filter (test) vs the prod
baseline window. The skill outputs a thresholded pass/fail plus an iterate signal that feeds
back into (a)/(b); optionally it materializes a versioned dashboard/notebook via the mandatory
`dt-app-dashboards` 7-step workflow. Deterministic and thresholded → skill, not MCP.

---

## Implementation backlog

Proposed epic **PAC-LT-TOOLING: "AI load-testing loop — skills & MCP wiring"**, feeding
Phase 4 demo (ISI-4047). Ordered by dependency.

| # | Story | Capability | Type | Depends on | Acceptance |
|---|---|---|---|---|---|
| S0 | Provision k6 runtime (container image with `xk6-output-opentelemetry`; pin version) | c | infra | — | `k6 version` runs in a repo-pinned image; OTel output verified to collector |
| S1 | Adopt `grafana/mcp-k6`: add to MCP config, smoke `validate_script` + `run_script` | b,c | mcp-wiring | — | agent can validate & run a trivial k6 script via MCP |
| S2 | Ratify workload-model JSON schema with Phase 2 (ISI-4045) | a | contract | Phase 2 | schema committed once, referenced by (a),(b),(d) |
| S3 | Build `pac-workload-model` skill (dtctl DQL → workload-model JSON, top-N journeys, Little's Law annotation) | a | skill | S2 | on a real DT timeframe, emits valid JSON; top-N cap enforced |
| S4 | Build `pac-k6-synth` skill (workload-model → k6 scenarios + synthetic payloads; validate via `mcp-k6`) | b | skill | S1,S2,S3 | generated script passes `validate_script`; open/closed executor chosen per model; no PII in payloads |
| S5 | Build `pac-loadtest-run` skill (scoped Job wrapper, `synthetic=true` tag, OTel export, artifact capture) | c | skill | S0,S4 | scoped run emits tagged telemetry + summary artifact; run survives driver teardown |
| S6 | Build `pac-baseline-diff` skill (DQL shape-diff, tolerance thresholds, iterate signal; optional DT dashboard) | d | skill | S5 | pass/fail + iterate signal on a real test-vs-prod window; dashboard via `dt-app-dashboards` |
| S7 | Wire the human VALIDATE gate (stage 2) between (a) and (b) as an explicit approval step | — | workflow | S3 | synthesis refuses to proceed without recorded approval |
| S8 | *(stretch)* Evaluate Tracetest for in-load internal-span assertions | d+ | spike | S5 | go/no-go note; not required for Phase 4 demo |

**Critical path to the Phase 4 demo:** S0 → S1 → S2 → S3 → S4 → S5 → S6, with S7 gating S4.
S8 is optional. S2 is the only hard cross-phase dependency (needs backup_Architect's schema).

---

## Coordination & open questions

- **Phase 2 (ISI-4045, backup_Architect):** the workload-model JSON schema (S2) is a shared
  contract — (a) produces it, (b)/(d) consume it. `docs/methodology.md` is not yet committed;
  this analysis assumes the 5-stage loop as described in the ISI-4045 issue. **Ask:** please
  own the schema in `docs/methodology.md` and confirm field names so the skills bind to it.
- **k6 provisioning (S0):** needs a target cluster/namespace decision — reuse the
  benchmark-substrate cluster or a dedicated loadtest namespace? Defer to Phase 4.
- **Dynatrace tenant/timeframe:** SCOPE and ANALYZE assume the same tenant carries both prod
  baseline and synthetic test telemetry, separated by `synthetic=true`. Confirm the demo
  target app's telemetry lands in a queryable DT tenant.
- **`mcp-k6` is preview:** acceptable for the demo; flag upstream-churn risk in the deck.

## References
- grafana/mcp-k6 (official k6 MCP server, preview): https://github.com/grafana/mcp-k6
- Configure your AI assistant for k6: https://grafana.com/docs/k6/latest/set-up/configure-ai-assistant/
- Grafana Assistant NL→k6 authoring: https://grafana.com/blog/generate-test-scripts-from-natural-language-with-grafana-assistant-introducing-k6-script-authoring/
- Load tests from production telemetry (Grafana Cloud k6): https://grafana.com/blog/how-to-generate-real-world-load-tests-using-grafana-cloud-k6-and-production-telemetry/
- Tracetest + k6: https://docs.tracetest.io/tools-and-integrations/k6
- Speedscale OTel trace replay / CI gates (commercial reference): https://speedscale.com/blog/otel-trace-testing-ci-release-gates/
- Companion research note: `research/loadtesting-from-observability.md`
