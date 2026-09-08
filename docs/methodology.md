# AI-Driven Load-Testing Methodology

*ISI-4045 · Phase 2 of the PAC "Loadtesting & AI" track ([ISI-4032](/ISI/issues/ISI-4032), plan rev 1, approved 2026-09-08)*
*Builds on: [`research/loadtesting-from-observability.md`](../research/loadtesting-from-observability.md)*

**Version:** 0.1 (draft) · **Status:** awaiting board validation (Gate V1) on this document itself — we apply the methodology to its own delivery: nothing is "final" until a human validates it.

---

## 1. Purpose & principles

This document formalizes the loop for producing load tests that reflect production reality, with AI agents doing the telemetry analysis, test synthesis, execution, and diffing — and humans keeping the judgment calls.

Three pillars (from the approved plan):

1. **Delegate execution & analysis, not judgment.** Scoped agent runs already executed and analyzed our fluent-bit, otel-collector, and MemoryServer benchmarks (see Phase 1 evidence pack, `docs/evidence/`). The scope contract — inputs, guardrails, human gates — is the pattern this methodology generalizes.
2. **Code-driven test authoring only.** Tests live as code (k6 primary; Gatling/Locust supported alternatives), versioned in git, reviewable, CI-runnable. No black-box recorders.
3. **Observability defines the scope.** Dynatrace + dtctl (DQL) analyze a traffic timeframe → extract the most regular traces/journeys → link journeys to code → propose a test scenario → **the user validates it before anything runs**.

Operating principles (normative — "MUST"):

- **P1 — Human gate is mandatory.** No test executes against any environment before the workload model is explicitly approved by the responsible human (Gate V1). Never skipped, never retro-active, never auto-approved by telemetry or agent heuristics.
- **P2 — Tests are code.** Every generated artifact is committed, diffable, and reviewable. Regenerating must be deterministic given the same workload model + seed.
- **P3 — Every number comes from telemetry.** Rates, mixes, latencies, and payload shapes are derived from observability data. LLM-assisted synthesis is always shape-validated against baselines; hallucinated patterns are rejected, not patched by hand-waving.
- **P4 — Test traffic is always identifiable.** All generated requests carry OTel baggage `synthetic=true` (propagated as `baggage` header) so test and production telemetry can be separated in DQL.
- **P5 — Never production by default.** Targets MUST come from a non-production allowlist. Any production exception requires an explicit board approval recorded on the issue.

---

## 2. The loop at a glance

```mermaid
flowchart TD
    A[1. SCOPE\nDQL timeframe analysis\n+ code linking] --> B[2. VALIDATE\nHenrik approves/adjusts]
    B -->|approved| C[3. SYNTHESIZE\nk6 scripts + payloads]
    B -->|adjustments| A
    C --> D[4. EXECUTE\nscoped delegated run\nbaggage synthetic=true]
    D --> E[5. ANALYZE\nDQL shape-diff\nvs prod baseline]
    E -->|out of tolerance\n<= 3 iterations| C
    E -->|within tolerance| F[ACCEPT\nreport + artifacts]
    E -->|3 iterations failed| G[ESCALATE\nhuman decision with diff evidence]
```

| # | Stage | Owner | Consumes | Produces | Exit gate |
|---|-------|-------|----------|----------|-----------|
| 1 | SCOPE | agent (workload-model skill) | DQL baseline queries, service code | `workload-model.json`, `scenario-proposal.md` | **G0** machine checks |
| 2 | VALIDATE | **human** (Henrik) | `scenario-proposal.md` | approval record in model `status.approval` | **V1** scenario approval |
| 3 | SYNTHESIZE | agent (k6-synthesis skill) | approved `workload-model.json` | `k6/*.js`, `payloads/*`, static-check pass | **V2a** static checks |
| 4 | EXECUTE | agent (loadtest-run skill, scoped run) | k6 scripts, `run-config.json` | run telemetry, `run-report.md` | **V2b** pre-flight safety |
| 5 | ANALYZE | agent (baseline-diff skill) | test telemetry, prod baseline | `shape-diff.json`, accept/iterate decision | **V3** shape tolerance |

The loop is **per target service, per scenario**, and each turn of the loop is a numbered run under `loadtests/<target>/runs/`.

---

## 3. Stage specifications

Each stage below is specified tightly enough to build a skill/MCP against (see §8): inputs, procedure, outputs, exit criteria, and the skill boundary.

### 3.1 SCOPE — observability-driven workload modeling

**Objective:** derive a workload model (arrival profile + weighted journeys + payload specs) from a production telemetry timeframe, linked to code.

**Inputs:**
- target service name and Dynatrace environment (dtctl profile)
- analysis timeframe (default: last 7 days, peak-inclusive; MUST exclude deploy windows and incidents)
- repo/commit of the service code (for journey→code linking)

**Procedure:**
1. **Timeframe sanity** — confirm the window is deploy-free and incident-free (DQL on deployment events / problem records). If not, shrink or shift and record why in the proposal.
2. **Baseline extraction** (DQL via dtctl; representative query pack):
   - Top entry operations by volume:
     ```sql
     fetch spans
     | filter isEntrySpan() and service.name == $service
     | summarize calls = count(), by: { service.name, span.name }
     | sort calls desc | limit 25
     ```
   - Arrival curve (per-minute request rate at entry):
     ```sql
     fetch spans
     | filter isEntrySpan() and service.name == $service
     | makeTimeseries count(), interval: 1m
     ```
   - Latency and error baseline per entry operation:
     ```sql
     fetch spans
     | filter isEntrySpan() and service.name == $service and span.name == $op
     | summarize p50 = percentile(duration, 50), p95 = percentile(duration, 95),
                 p99 = percentile(duration, 99), err = count(error)
     ```
   - Service-graph fan-out (downstream call edges and rates from traces).
3. **Journey extraction** — group traces by entry span; normalize span trees (service, operation, call type, ordering); cluster identical/nearest signatures; keep journeys until cumulative volume ≥ **80%** of entry traffic (coverage rule). Record per-journey weight (share of traffic) and think-time distribution from inter-span gaps.
4. **Code linking** — for each journey step, locate the implementing code (route handler, client call, DB/mq statement) via code search; record `codeRef` (`path#symbol`). Journeys that cannot be linked are flagged `unlinked: true` and MUST be called out in the proposal.
5. **Arrival model fit** — open model (arrival-rate) for public/queueing APIs; closed model (VU-bound) for seat-limited systems. Sanity-check with Little's Law: `concurrency ≈ arrival_rate × mean_response_time`; deviations > 2× flag a modeling error.
6. **Emit artifacts** — `workload-model.json` (schema §4) + `scenario-proposal.md` (template §5.2).

**Outputs:** `workload-model.json`, `scenario-proposal.md`.

**Exit criteria — Gate G0 (machine-checkable, enforced before VALIDATE is offered):**
- [ ] `workload-model.json` validates against the schema in §4
- [ ] cumulative journey weight ≥ 0.80 (coverage) — actual value recorded in `spec.coverage`
- [ ] every journey has `codeRef` per step, or explicit `unlinked: true` with reason
- [ ] every journey carries a `baseline` (p50/p95/p99/error-rate)
- [ ] arrival profile passes the Little's-Law sanity check
- [ ] proposal names target environment from the allowlist and the requested blast-radius caps

**Skill boundary (Phase 3 input):** dtctl/DQL query pack + timeframe sanity; span-tree clustering; code-search linking; model emission + G0 self-validation.

### 3.2 VALIDATE — mandatory human gate

**Objective:** the responsible human approves or adjusts the proposed scenario before any code is synthesized or run.

**Rules (normative):**
1. The gate decision MUST be captured as a structured, recorded confirmation (e.g., Paperclip `request_confirmation`) bound to a specific `workload-model.json` revision id — not a chat remark.
2. Approval is **hash-bound**: any change to the model after approval invalidates the approval and re-opens the gate. The agent applies adjustments as a **new revision**, which requires a **new confirmation**.
3. The approval trail is recorded in the model itself: `status.approval = { revision, decisionBy, decisionAt, decision: "approved" | "adjusted" }`.
4. **No auto-approval.** Telemetry similarity, agent confidence, deadline pressure, or repeated iterations MUST NOT satisfy this gate. Only an explicit human decision does.
5. Scope of approval = the scenario (target env, journey set + weights, arrival profile, payload specs, caps). Later parameter-level tuning during ANALYZE iterations (§3.5) does not re-open the gate; structural changes (journeys, weights, rates, target) always do.

**Skill boundary:** none — this is a Paperclip interaction, deliberately not a skill.

### 3.3 SYNTHESIZE — code-driven test authoring

**Objective:** generate versioned, reviewable load-test code from the approved model.

**Rules:**
1. **k6 primary.** Gatling (Scala) / Locust (Python) only when `run-config.tool` explicitly selects them; the model is tool-agnostic, generators are per-tool.
2. Structure per model: one k6 *scenario* per journey group using arrival-rate executors (`constant-arrival-rate` / `ramping-arrival-rate`) for open models, VU executors (`constant-vus`) for closed models; think times from the model distribution; per-scenario weights from journey weights.
3. **Synthetic payloads** generated from `payloadSpec` distributions — never sampled from production data; no PII possible by construction; random seeds recorded in the run for determinism.
4. LLM assistance is allowed for authoring, but output MUST pass static checks (Gate V2a) and, later, the shape-diff (Gate V3). A hallucinated endpoint/parameter fails V2a and is rejected.
5. Test code carries the identity header by construction: `baggage: synthetic=true` on every request (k6 OTel extension / `k6/x/tracing`).

**Exit criteria — Gate V2a (static, pre-run):**
- [ ] `k6 inspect`/parse succeeds (or selected tool's syntax check)
- [ ] every request in scripts carries `baggage: synthetic=true`
- [ ] all referenced payload pools exist and match their specs
- [ ] declared max rate/VU ≤ caps from the approved model
- [ ] scripts committed to the repo (tests are code)

**Skill boundary:** model→k6 codegen; payload pool generation; V2a checker.

### 3.4 EXECUTE — delegated scoped run

**Objective:** run the synthesized test exactly as scoped — the same pattern as our fluent-bit / otel-collector / MemoryServer benchmark delegations (Phase 1 evidence: `docs/evidence/*.md`).

**Rules:**
1. Execution is a **scoped agent run** with a written scope contract: inputs, allowed commands, blast-radius caps, abort conditions, output location.
2. `run-config.json` (template §5.3) fixes the blast radius: target env (from allowlist), max RPS, max VUs, duration cap, schedule window, and abort thresholds (error-rate > X% or p95 > Y ms → kill).
3. Target MUST be on the non-production allowlist (P5). The runner refuses otherwise.
4. Telemetry emitted through the OTel pipeline with `synthetic=true` baggage, so ANALYZE can select test traffic precisely.
5. The run records its telemetry coordinates (environment, timeframe, trace filter) for ANALYZE.

**Exit criteria — Gate V2b (pre-flight, machine-enforced immediately before start):**
- [ ] target env ∈ allowlist and ≠ production
- [ ] V2a passed on the exact commit being run
- [ ] model `status.approval.decision == "approved"` for the model revision the scripts were generated from
- [ ] caps and abort thresholds loaded and armed
- [ ] run directory created (`runs/<UTC-timestamp>/`)

**Skill boundary:** scoped-run executor + supervisor (caps, abort), run-report generation.

### 3.5 ANALYZE — shape-diff against production, then iterate

**Objective:** prove (or disprove) that the test traffic *shape* matches the production baseline, in Dynatrace DQL.

**Shape-diff dimensions and default tolerances** (overridable via `run-config.tolerances`):

| Dimension | Comparison | Default tolerance |
|---|---|---|
| Arrival shape | per-minute RPS curve, test (scaled) vs baseline | WMAPE ≤ 0.20 |
| Latency | p50 / p95 / p99 per journey entry op | \|Δp50\| ≤ 25%, \|Δp95\| ≤ 30%, \|Δp99\| ≤ 35% relative |
| Service fan-out | baseline downstream edges present during test | ≥ 90% of edges present; per-edge rate ratio ∈ [0.5, 2.0] |
| Error rate | test vs baseline, per journey | absolute Δ ≤ +1.0 pp |
| Journey mix | distribution over journeys vs weights | total variation distance ≤ 0.15 |

**Decision rule:**
- **All dimensions within tolerance → ACCEPT.** Emit `shape-diff.json` + summary in `run-report.md`; loop turn is complete.
- **Any dimension out → ITERATE.** Classify the miss (shape / latency / fan-out / mix), adjust **parameters only** (think times, pacing, payload pools, per-journey pacing within ±10% of approved weights), re-run SYNTHESIZE→EXECUTE→ANALYZE. Structural fixes (journeys, weights, rates, target) require a model change → back to **VALIDATE** (rule §3.2.2).
- **Iteration cap:** max **3** iterations. On the 4th miss → **ESCALATE** to the human with the diff evidence and a diagnosis; no silent tuning forever.

**Skill boundary:** DQL diff queries (filtered by `baggage synthetic=true` vs baseline window), tolerance evaluation, iteration classifier, escalation report.

---

## 4. Workload-model JSON schema (draft v1)

Draft-07 JSON Schema. Stored as `loadtests/<target>/workload-model.json`. The `status` block is agent-maintained and carries the Gate V1 trail.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://github.com/henrikrexed/PAC-AI-loadtesting/schemas/workload-model.schema.json",
  "title": "WorkloadModel",
  "type": "object",
  "required": ["apiVersion", "kind", "metadata", "spec", "status"],
  "properties": {
    "apiVersion": { "const": "loadtest.isi/v1alpha1" },
    "kind": { "const": "WorkloadModel" },
    "metadata": {
      "type": "object",
      "required": ["name", "targetService", "environment", "source"],
      "properties": {
        "name": { "type": "string", "pattern": "^[a-z0-9][a-z0-9-]*$" },
        "targetService": { "type": "string" },
        "environment": { "type": "string", "description": "Dynatrace environment/tenant name analyzed" },
        "generatedAt": { "type": "string", "format": "date-time" },
        "source": {
          "type": "object",
          "required": ["tool", "timeframe"],
          "properties": {
            "tool": { "type": "string", "examples": ["dynatrace-dql", "dtctl"] },
            "timeframe": { "type": "string", "description": "ISO interval analyzed, e.g. 2026-09-01T00:00Z/2026-09-08T00:00Z" },
            "timeframeNotes": { "type": "string", "description": "deploy/incident exclusions applied" },
            "queries": { "type": "array", "items": { "type": "string" } }
          }
        }
      }
    },
    "spec": {
      "type": "object",
      "required": ["arrivalProfile", "journeys", "coverage"],
      "properties": {
        "arrivalProfile": {
          "type": "object",
          "required": ["model", "stages"],
          "properties": {
            "model": { "enum": ["open", "closed"] },
            "stages": {
              "type": "array",
              "minItems": 1,
              "items": {
                "type": "object",
                "required": ["duration", "rate"],
                "properties": {
                  "duration": { "type": "string", "examples": ["5m", "30m"] },
                  "rate": { "type": "number", "description": "target iterations/s (open) or VUs (closed)" }
                }
              }
            },
            "littlesLawCheck": {
              "type": "object",
              "properties": {
                "expectedConcurrency": { "type": "number" },
                "observedConcurrency": { "type": "number" },
                "ratio": { "type": "number" }
              }
            }
          }
        },
        "journeys": {
          "type": "array",
          "minItems": 1,
          "items": {
            "type": "object",
            "required": ["id", "weight", "entrypoint", "steps", "baseline"],
            "properties": {
              "id": { "type": "string" },
              "description": { "type": "string" },
              "weight": { "type": "number", "minimum": 0, "maximum": 1 },
              "entrypoint": { "type": "string", "description": "entry span name, e.g. POST /cart/checkout" },
              "codeRef": { "type": "string", "description": "path#symbol of entry handler" },
              "unlinked": { "type": "boolean", "default": false },
              "steps": {
                "type": "array",
                "items": {
                  "type": "object",
                  "required": ["id", "service", "operation", "callType"],
                  "properties": {
                    "id": { "type": "string" },
                    "service": { "type": "string" },
                    "operation": { "type": "string" },
                    "callType": { "enum": ["http", "grpc", "db", "mq", "cache"] },
                    "codeRef": { "type": "string" },
                    "payloadRef": { "type": "string", "description": "key into spec.payloads" },
                    "thinkTime": { "$ref": "#/definitions/thinkTime" },
                    "dependsOn": { "type": "array", "items": { "type": "string" } }
                  }
                }
              },
              "baseline": { "$ref": "#/definitions/baseline" }
            }
          }
        },
        "payloads": {
          "type": "object",
          "description": "synthetic payload pools keyed by id",
          "additionalProperties": { "$ref": "#/definitions/payloadSpec" }
        },
        "caps": {
          "type": "object",
          "properties": {
            "maxRps": { "type": "number" },
            "maxVus": { "type": "number" },
            "maxDuration": { "type": "string" }
          }
        },
        "coverage": { "type": "number", "minimum": 0, "maximum": 1 }
      }
    },
    "status": {
      "type": "object",
      "required": ["revision"],
      "properties": {
        "revision": { "type": "integer", "minimum": 1 },
        "hash": { "type": "string", "description": "sha256 of canonicalized spec" },
        "approval": {
          "type": "object",
          "required": ["revision", "decision", "decisionBy", "decisionAt"],
          "properties": {
            "revision": { "type": "integer" },
            "decision": { "enum": ["approved", "adjusted"] },
            "decisionBy": { "type": "string" },
            "decisionAt": { "type": "string", "format": "date-time" },
            "confirmationRef": { "type": "string", "description": "Paperclip interaction/approval id" }
          }
        }
      }
    }
  },
  "definitions": {
    "thinkTime": {
      "type": "object",
      "required": ["distribution"],
      "properties": {
        "distribution": { "enum": ["constant", "uniform", "exponential", "empirical"] },
        "meanMs": { "type": "number" },
        "minMs": { "type": "number" },
        "maxMs": { "type": "number" },
        "samples": { "type": "array", "items": { "type": "number" }, "description": "for empirical" }
      }
    },
    "baseline": {
      "type": "object",
      "required": ["p50Ms", "p95Ms", "p99Ms", "errorRate"],
      "properties": {
        "p50Ms": { "type": "number" },
        "p95Ms": { "type": "number" },
        "p99Ms": { "type": "number" },
        "errorRate": { "type": "number", "minimum": 0, "maximum": 1 },
        "arrivalShare": { "type": "number" }
      }
    },
    "payloadSpec": {
      "type": "object",
      "required": ["fields"],
      "properties": {
        "fields": {
          "type": "array",
          "items": {
            "type": "object",
            "required": ["name", "type"],
            "properties": {
              "name": { "type": "string" },
              "type": { "enum": ["string", "int", "float", "enum", "uuid", "timestamp", "null"] },
              "generator": { "type": "string", "examples": ["random", "sequence", "faker:firstName", "const"] },
              "values": { "type": "array" },
              "distribution": { "enum": ["uniform", "weighted", "normal", "zipf"] },
              "optional": { "type": "boolean", "default": false }
            }
          }
        },
        "seed": { "type": "integer" }
      }
    }
  }
}
```

**Open schema questions (for Phase 3 / first real use):** multi-service journeys spanning Kafka topics; empirical think-time ergonomics; whether `caps` belongs in the model or only in `run-config.json` (current answer: model declares, run-config enforces).

---

## 5. Artifact formats & repo layout

### 5.1 Layout

```
docs/
  methodology.md              <- this file
  evidence/                   <- Phase 1 benchmark evidence one-pagers
  skills-mcp-decisions.md     <- Phase 3 gap analysis
research/
  loadtesting-from-observability.md
loadtests/
  <target-service>/
    workload-model.json       <- schema §4, with approval trail
    scenario-proposal.md      <- human gate V1 input
    k6/
      <scenario>.js
      lib/                    <- helpers (auth, baggage, checks)
    payloads/
      <pool>.json
    runs/
      <UTC-timestamp>/
        run-config.json
        run-report.md
        shape-diff.json
```

### 5.2 `scenario-proposal.md` template

```markdown
# Scenario proposal: <target-service> rev <N>
## What was analyzed        (timeframe, env, exclusions, coverage %)
## Journeys to be tested    (table: id, weight, entrypoint, codeRef, baseline p95)
## Arrival profile          (stages, model, Little's law check)
## Payload strategy         (pools, PII stance, seeds)
## Where it will run        (target env from allowlist, caps, abort thresholds)
## Risks & unknowns         (unlinked steps, coverage gaps, assumptions)
## Decision requested       (approve as-is / adjust: <fields>)
```

### 5.3 `run-config.json` template

```json
{
  "modelRef": { "name": "checkout", "revision": 3, "hash": "…" },
  "tool": "k6",
  "target": { "baseUrl": "https://staging.internal", "environment": "staging", "allowlist": true },
  "caps": { "maxRps": 400, "maxVus": 200, "maxDuration": "30m" },
  "abort": { "errorRateGt": 0.05, "p95MsGt": 2500 },
  "syntheticTag": { "baggage": "synthetic=true" },
  "tolerances": { "arrivalWmape": 0.20, "p95Rel": 0.30, "edgePresence": 0.90, "errorDeltaPp": 1.0, "journeyTvd": 0.15 },
  "telemetry": { "environment": "staging-dt-tenant", "timeframe": "…", "filter": "baggage synthetic=true" }
}
```

### 5.4 `shape-diff.json` template

```json
{
  "run": "<timestamp>",
  "baselineTimeframe": "…",
  "dimensions": {
    "arrivalShape":   { "metric": "wmape", "value": 0.14, "tolerance": 0.20, "pass": true },
    "latency":        { "p50Rel": 0.08, "p95Rel": 0.19, "p99Rel": 0.27, "pass": true },
    "serviceFanout":  { "edgePresence": 0.95, "rateRatioRange": [0.6, 1.8], "pass": true },
    "errorRate":      { "deltaPp": 0.3, "pass": true },
    "journeyMix":     { "tvd": 0.09, "pass": true }
  },
  "decision": "accept",
  "iteration": 1
}
```

---

## 6. Gate rules summary

| Gate | After | Type | Enforced by | Blocks until |
|---|---|---|---|---|
| **G0** model integrity | SCOPE | machine | workload-model skill (schema + coverage + linking + Little's law) | VALIDATE offered |
| **V1** scenario approval | SCOPE → SYNTHESIZE | **human** | Paperclip confirmation bound to model revision | any synthesis |
| **V2a** static checks | SYNTHESIZE → EXECUTE | machine | k6-synthesis skill (parse, baggage, pools, caps, committed) | any run |
| **V2b** pre-flight | EXECUTE start | machine | loadtest-run skill (allowlist, approval-valid, caps armed) | process start |
| **V3** shape tolerance | ANALYZE | machine + human cap | baseline-diff skill; iteration ≤ 3 then human | accept / escalate |

Invariant: **V1 approval hash-bound to model revision** is the anchor of the whole loop — every later gate re-verifies it (`V2b` checks `status.approval.revision` + `hash`).

---

## 7. Safety rules

1. Non-production allowlist, checked at V2b. Production exception = board approval on the issue, never agent discretion.
2. Hard caps (RPS, VUs, duration) + automatic abort thresholds on every run.
3. `baggage: synthetic=true` on 100% of generated requests (V2a-verified, V2b-armed).
4. Synthetic payloads only — production data is never copied into payload pools; generators are PII-free by construction.
5. Runs are scheduled windows, recorded with full config for replay; abort causes are part of `run-report.md`.
6. Everything committed (P2): model, scripts, payloads, configs, diffs, reports.

---

## 8. Skill mapping (input to Phase 3, [ISI-4046](/ISI/issues/ISI-4046))

| Stage | Skill (working name) | Core capabilities | Natural interface |
|---|---|---|---|
| SCOPE | `workload-model` | dtctl/DQL query pack, timeframe sanity, span-tree journey clustering, code linking, model emission + G0 | input: service + timeframe; output: `workload-model.json` + proposal |
| VALIDATE | *(none — Paperclip interaction)* | human confirmation bound to revision | `request_confirmation` |
| SYNTHESIZE | `k6-synthesis` | model→k6 codegen, payload pools, V2a checker | input: approved model; output: `k6/` + `payloads/` |
| EXECUTE | `loadtest-run` | scoped-run executor, caps/abort supervisor, run-report | input: `run-config.json`; output: `runs/<ts>/` |
| ANALYZE | `baseline-diff` | DQL diff (synthetic filter), tolerance eval, iteration classifier, escalation report | input: run + baseline; output: `shape-diff.json` + decision |

Phase 3 decides build-skill vs use-MCP per row (e.g., Grafana Assistant / Speedscale / Tracetest as buy-side alternatives for rows 2–4).

---

## 9. Relation to Phase 1 evidence (narrative coordination)

The Phase 1 evidence pack (`docs/evidence/*.md`, one-pagers for fluent-bit, otel-collector, MemoryServer — [ISI-4044](/ISI/issues/ISI-4044)) instantiates the **EXECUTE** stage pattern with existing precedents. For narrative coherence across the PAC deck:

- each evidence one-pager exposes its **scope contract** (inputs, allowed commands, outputs) → maps 1:1 to `run-config.json` + V2b;
- its **guardrails** (caps, aborts) → §7 safety rules;
- its **outcome numbers** (delegation payoff) → the "why delegate" pillar-1 argument;
- this methodology is what those one-off runs look like **generalized and gated**.

Presentation storyline: *we already delegate execution credibly (evidence) → here is the loop that makes it repeatable (this doc) → here is the tooling to make it cheap (Phase 3) → here is it working end-to-end (Phase 4 demo).*

---

## 10. Document status

- v0.1 drafted by backup_Architect, 2026-09-08, per [ISI-4045](/ISI/issues/ISI-4045).
- Pending Gate-V1-style board validation of this document (approval of the methodology itself, mirroring §3.2).
- Phase 3 ([ISI-4046](/ISI/issues/ISI-4046)) consumes §8; Phase 4 demo ([ISI-4047](/ISI/issues/ISI-4047)) executes §3 end-to-end on one target; Phase 5 deck ([ISI-4048](/ISI/issues/ISI-4048)) narrates §1–§2.
