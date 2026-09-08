# Skills vs MCP — Decision Table for the Load-Testing Loop

*ISI-4046 (PAC loadtest/AI, Phase 3) · Parent ISI-4032 (plan rev 1, approved 2026-09-08) · compiled by the O11y Engineer · 2026-09-08*

## Purpose

The methodology from [`research/loadtesting-from-observability.md`](../research/loadtesting-from-observability.md) defines a
four-capability loop that turns production observability data into realistic, self-validating load tests:

```
Dynatrace (DQL) ──▶ (a) workload-model ──▶ (b) k6-synthesis ──▶ (c) loadtest-run ──▶ (d) baseline-diff ──┐
        ▲                                                                                                 │
        └──────────────────────────────── iterate until test telemetry matches prod within tolerance ────┘
```

For each capability we must decide the **right delivery vehicle**: build a first-party **skill** (a versioned,
guardrail-carrying workflow in this repo), lean on an existing/off-the-shelf **MCP** (a live tool-calling server), or a
**hybrid** (a skill that orchestrates one or more MCPs/CLIs for data access). This document records those decisions with
rationale and an implementation backlog.

---

## Decision framework

We chose the vehicle against six axes. The heuristic:

| Signal | Favors a **skill** | Favors an **MCP** |
|--------|--------------------|-------------------|
| **Determinism** | Repeatable procedure, same inputs → same artifact | Interactive, exploratory, live tool-calling loop |
| **Ownership of logic** | Methodology, guardrails, schema contracts are *ours* | Logic lives in the external system's API |
| **Data-access surface** | Static / file-based | Live query against an evolving external system |
| **Guardrails** | PII scrub, cardinality caps, shape-match gates baked in | N/A — MCP exposes raw capability |
| **Versioning** | Must be diffable, reviewable, replayable in git | Stateless call, no artifact to version |
| **Grounding / vendor neutrality** | Source of truth must be *our* Dynatrace stack | Vendor already ships a maintained server for *their* grounding |

**Net finding:** all four capabilities are **build-skill**, because in every case the *methodology, guardrails, JSON-schema
contracts, and versioned artifacts are ours* — off-the-shelf MCPs supply data access or codegen but impose the wrong
grounding (Grafana Cloud, not Dynatrace) or omit our validation gates. The differentiator between capabilities is **which
existing MCP/CLI each skill wraps for data access**. This is the same pattern already proven by the `dt-app-dashboards`
skill (a first-party skill that orchestrates dtctl/Dynatrace for a data-backed artifact).

---

## Inventory — what we already have

### First-party skills & tooling (reuse)
| Asset | What it gives us | Relevant to |
|-------|------------------|-------------|
| **dtctl** (Dynatrace CLI, config-as-code, DQL execution) | Run DQL, apply/export DT config as YAML | (a), (d) |
| **Dynatrace MCP** (`discover-services`, `discover-metrics`, `run-dt-query`, `analyze-logs`) | Live entity/metric discovery + DQL execution in a tool loop | (a), (d) |
| **`dt-app-dashboards` skill** | Proven skill pattern: 7-step gated workflow, DQL validation before embedding, deploy script | template for all 4 skills; visualize diff output |
| **dt notebook / workflow / SLO skills** | Diagnostic notebooks, automation, `define-slos` → test-consumable KPIs | (d) tolerance gates, SLO-driven pass/fail |
| **memory-benchmark harness** (`filter/benchmark_only` collector tap, kubeletstats, tail_sampling, weaver semconv conformance, in-cluster Job → harvest `summary.json`) | Scoped-telemetry capture, synthetic-traffic isolation, two-pass diff reporting | (c) run+capture, (d) diff report shape |
| **otel-collector redaction pipeline** (`memory_limiter`→…→`redaction`/OTTL→`batch`, double-guarded PII scrub) | PII/attribute scrubbing before data leaves the loop | (a) digest sanitization, (b) synthetic-payload PII guard |

### k6 tooling
- **None in-workspace today.** `find … -iname '*k6*'` → empty. The k6 binary, the `xk6-output-opentelemetry` extension, and
  scenario templates are all net-new. This is the biggest build surface.

### Off-the-shelf evaluated
| Option | Fit | Verdict |
|--------|-----|---------|
| **k6 core (CLI + `xk6-output-opentelemetry`)** | Native OTel metric export, open/closed executors, scenarios | **Adopt as the engine** — wrapped by (c), not an MCP |
| **Grafana Assistant — k6 script authoring** (NL→k6) | Proves the AI-codegen pattern ships, *but* grounded in **Grafana Cloud telemetry**, not Dynatrace | **Pattern reference only** — wrong grounding + vendor lock; do not adopt as our (b) engine |
| **k6 Studio / HAR-to-k6** | Per-journey recording→script | **Reference** — misses fleet-level distribution; useful to seed journey templates |
| **Tracetest** (trace-based assertions, has k6 integration) | Validates *internal* spans during load, not distribution diff | **Optional complementary integration** for (d) span-level assertions |
| **Speedscale** (OTel-trace replay + CI gates) | Closest commercial "replay from observability" | **Commercial reference only** (not adopted) |
| **k6 Cloud / Grafana Cloud k6 MCP** | Managed run + results | **Rejected** — introduces a live SaaS dependency and Grafana grounding; our run is a deterministic self-hosted CLI/Job |

---

## Decision table — build-skill vs use-MCP per capability

| # | Capability | Decision | Wraps (data access) | Why not "just use an MCP" | Reuse |
|---|-----------|----------|---------------------|---------------------------|-------|
| **(a)** | **workload-model** — trace → journey/distribution digest | **Build skill** (`workload-model`) — hybrid over MCP | Dynatrace MCP + dtctl (DQL for RPS profile, endpoint mix, latency percentiles, span-tree journeys, service graph, think-time) | MCP returns raw query rows; it does **not** produce a versioned `workload-model.json`, validate with Little's Law, fit distributions, or apply PII/cardinality guards. Those are our contract. | otel redaction pipeline (sanitize); dtctl DQL patterns from ISI-3243/ISI-3592 |
| **(b)** | **k6-synthesis** — workload model → k6 script + synthetic data | **Build skill** (`k6-synthesis`) — LLM-assisted codegen | Local (consumes `workload-model.json`); LLM for scenario + synthetic-payload synthesis | Grafana Assistant does NL→k6 but grounds on **Grafana Cloud**, not our Dynatrace-derived model, and can't emit our shape-match guardrail. Vendor-neutral codegen + validation must be ours. | k6 open/closed executor templates (net-new); redaction guard for synthetic PII |
| **(c)** | **loadtest-run** — scoped execution + result capture | **Build skill** (thin `loadtest-run`) over k6 CLI | k6 CLI + `xk6-output-opentelemetry` → collector → Dynatrace; `synthetic=true` OTel baggage for isolation | Execution is a deterministic CLI/Job — an MCP would add a live-service dependency where none is needed. k6 Cloud MCP rejected (SaaS + Grafana grounding). | memory-benchmark harness: in-cluster Job → harvest `summary.json`, `filter/benchmark_only` tap for test/prod telemetry separation |
| **(d)** | **baseline-diff** — test vs prod telemetry comparison in DQL | **Build skill** (`baseline-diff`) — hybrid over MCP | Dynatrace MCP + dtctl (paired DQL: RPS histogram shape, latency-percentile deltas, service-graph fan-out, error/retry rates); optional **Tracetest** for span assertions | MCP runs the queries; the **tolerance model, shape-match logic, pass/fail verdict, and iterate signal** are our methodology (proven in ISI-3243 dashboard-lock diff + two-pass reporting). SLO tolerances come from `define-slos`. | dt SLO/`define-slos` skill; two-pass diff reporting; `dt-app-dashboards` to visualize the diff |

### One-line summary
**4/4 build-skill.** Each skill is thin where an existing MCP/CLI already covers data access ((a),(d)→Dynatrace MCP+dtctl;
(c)→k6 CLI) and thick where the value is ours (schema contracts, guardrails, shape-match/tolerance gates, versioned
artifacts). No net-new MCP server is warranted; the only net-new *engine* is k6 + the OTel output extension.

---

## Why not net-new MCPs

- **Nothing here is an interactive, evolving external API we own.** MCPs shine when a live system needs a tool-calling loop
  (Dynatrace already has one; we reuse it). Our loop is a deterministic pipeline that produces **diffable, replayable
  artifacts** — the skill/file model fits, and a git-versioned `workload-model.json` / k6 script / diff report is a feature,
  not overhead.
- **Guardrails must ride with the workflow.** PII scrub, cardinality caps, Little's-Law validation, and shape-match
  tolerance gates are the whole point of "reflecting reality" — they belong *inside* the skill, not behind a raw MCP call.
- **Vendor neutrality / grounding.** Our source of truth is Dynatrace. Adopting Grafana Assistant or k6 Cloud MCP would
  ground synthesis and runs in Grafana Cloud, contradicting *instrument-once-export-everywhere* and adding SaaS coupling.

---

## Implementation backlog

Proposed child issues of ISI-4032 (Phase 4). Ordered by dependency; each is independently shippable and testable.

| ID (proposed) | Title | Depends on | Owner (suggested) | Acceptance |
|---------------|-------|------------|-------------------|------------|
| **BL-1** | Define `workload-model.json` schema + weaver semconv for the digest (endpoints, RPS profile, percentiles, journeys, think-time, service graph) | — | O11y Engineer | JSON Schema committed; validates against a sample DT extract; PII/cardinality fields flagged |
| **BL-2** | Build **`workload-model`** skill: DQL set (via Dynatrace MCP/dtctl) → sanitized digest → `workload-model.json`; Little's-Law check | BL-1 | O11y Engineer | Skill emits valid digest from a real DT tenant window; sanitization proven (no PII) |
| **BL-3** | Stand up k6 engine: pin k6 + `xk6-output-opentelemetry` build; open/closed executor scenario templates | — | Developer (Amelia) | k6 binary builds; sample scenario exports OTel metrics to collector→Dynatrace |
| **BL-4** | Build **`k6-synthesis`** skill: `workload-model.json` → k6 script + synthetic payloads; **shape-match guardrail** vs baseline | BL-1, BL-3 | O11y Engineer + Developer | Generated script runs; synthetic payload distributions match model within tolerance; no PII |
| **BL-5** | Build **`loadtest-run`** skill/harness: scoped in-cluster Job, `synthetic=true` baggage, `filter/benchmark_only` tap, harvest `summary.json` + telemetry link | BL-3 | Developer (Amelia) | Run produces `summary.json` + isolated test telemetry queryable in DT (not mixed with prod) |
| **BL-6** | Define SLO tolerances for the diff via `define-slos` (RPS shape, latency percentiles, fan-out, error rate) | BL-1 | O11y Engineer | Test-consumable KPI thresholds committed |
| **BL-7** | Build **`baseline-diff`** skill: paired DQL (test vs prod) → shape-match → pass/fail verdict + iterate signal; optional Tracetest span assertions | BL-2, BL-5, BL-6 | O11y Engineer | Diff report emits verdict on a real run; tolerance breaches flagged; optional dashboard via `dt-app-dashboards` |
| **BL-8** | Wire the iterate loop + CI release gate (diff verdict gates promotion) | BL-4, BL-5, BL-7 | Developer + Testing Architect | End-to-end: model→synth→run→diff→iterate demonstrated on one service |

**Critical path:** BL-1 → BL-2/BL-6 → BL-4 (needs BL-3) → BL-5 → BL-7 → BL-8. BL-3 (k6 engine) is parallelizable and is the
long pole (net-new build surface). BL-1 (schema) unblocks the most downstream work — sequence it first.

---

## Cross-agent coordination

- **backup_Architect (Phase 2):** this decision table assumes the Phase 2 architecture confirms Dynatrace as the single
  source of truth and the in-cluster Job execution model (per memory-benchmark). **Open confirmation:** does Phase 2 mandate
  any run target other than self-hosted/in-cluster (e.g., a managed k6 runner)? If yes, revisit the (c) rejection of k6
  Cloud MCP. Flagged for Architect review below.
- **Developer (Amelia):** owns BL-3/BL-5 (k6 engine + run harness); receives BL-4 jointly.
- **Testing Architect:** owns the CI release-gate semantics in BL-8; consumes BL-6 SLO KPIs.

## Guardrail conformance (O11y critical rules)

- Any collector pipeline introduced by (c) MUST keep `memory_limiter` first / `batch` last; use `filter/benchmark_only` for
  test-traffic isolation; `k8sattributes` only in-cluster.
- (a) and (b) MUST scan digests and synthetic payloads for PII before persisting/emitting.
- (d) MUST pass the 5-step query-validation gate before any trace/telemetry validation, and never invent DT field names
  without checking sample output.
