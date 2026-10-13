# Observability-driven load-testing methodology

The toolkit is built around one idea:

> **Your telemetry already knows what your real workload looks like. Extract it, have a
> human approve it, then replay it faithfully — and keep the generated traffic
> identifiable so you can prove the replay matched reality.**

This document is the method. The scripts and skills in this repo are one implementation
of it; the gates and principles below are what matter even if you swap tools.

---

## 1. Principles (normative)

- **P1 — The human gate is mandatory.** No test executes against any environment before
  the workload model is explicitly approved by a responsible human (Gate **V1**). Never
  skipped, never retro-active, never auto-approved by telemetry or an agent heuristic.
- **P2 — Tests are code.** Every generated artifact is committed, diffable, reviewable.
  Regenerating is deterministic given the same workload model (+ seed). No black-box
  recorders.
- **P3 — Every number comes from telemetry.** Rates, journey mixes, latencies, and
  payload shapes are derived from observability data. LLM-assisted synthesis is always
  shape-validated against the baseline; hallucinated patterns are rejected, not patched
  by hand.
- **P4 — Test traffic is always identifiable.** All generated requests carry OTel baggage
  `synthetic=true` (propagated as the W3C `baggage` header). Because baggage is a
  context-propagation mechanism and *not* a queryable attribute by default, the pipeline
  **MUST promote it** to a span/resource attribute (SDK span processor, or a collector
  `transform` step — see [`../tutorial/otel-demo/collector.yaml`](../tutorial/otel-demo/collector.yaml)).
  Without that promotion the ANALYZE filter matches nothing.
- **P5 — Never production by default.** Targets MUST come from a non-production allowlist.
  Any production exception is an explicit, recorded human decision — never agent
  discretion.

---

## 2. The loop

```
SCOPE ──G0──▶ VALIDATE ──V1──▶ SYNTHESIZE ──V2a──▶ EXECUTE ──V2b──▶ ANALYZE ──V3──┐
  ▲                                                                              │
  └──────────────── iterate (parameter-only, ≤3×) or escalate ◀───────────────────┘
```

| Stage | Owner | Input → Output | Gate |
|---|---|---|---|
| **SCOPE** | you / your agent | clean telemetry window → `workload-model.json` + `scenario-proposal.md` | **G0** extraction self-check |
| **VALIDATE** | **a human, always** | reads the proposal → approval bound to the model revision | **V1** human approval |
| **SYNTHESIZE** | you / your agent | approved model → runnable test + synthetic payload pools | **V2a** static checks |
| **EXECUTE** | you / your agent | small confirmation run, then a capped, abort-guarded full run | **V2b** smoke gate |
| **ANALYZE** | machine + human cap | shape-diff of test vs baseline → accept / iterate / escalate | **V3** tolerance eval |

---

## 3. SCOPE — telemetry → workload model

Point a backend adapter at a **clean telemetry window** `(service, timeframe,
environment)` and extract the facts a realistic test needs:

- **Journeys** — the regular request chains (span trees), linked to code where possible.
- **Archetype split** — the dominant behavioural classes and their weights (e.g. Browser
  vs. Buyer; Conversational vs. Agentic).
- **Arrival profile** — per-minute arrival counts → an open- or closed-model profile with
  a **Little's-Law** consistency check (λ · think-time ≈ concurrency).
- **Think-times** — measured per step where a session signal is present, not assumed.
- **Payload strategy** — cache-avoidance pools (e.g. Zipf-distributed ids) so the replay
  does not trivially hit warm caches.
- **Baselines** — the six shape dimensions the ANALYZE step will later diff against.

Prefer **two sources fused**: spans give topology and trace structure; access logs
(e.g. Istio/Envoy sidecar + ingress) give the authoritative, instrumentation-independent
HTTP request record (method, path, status, duration) and a request-id correlation
backbone. Spans alone miss un-instrumented hops and abstract exact paths into span names.

**Gate G0** is the engine's own exit criteria — coverage, per-step evidence source,
Little's-Law consistency, a schema-valid model. The engine exits non-zero if G0 fails, so
you can gate a pipeline on it. Details in [`engine.md`](engine.md).

### Sidebar — dual-source session reconstruction

Real realism needs **session boundaries, action order, and think-times**, which raw spans
alone do not give you. The toolkit reconstructs sessions from whatever signal is present,
in preference order:

1. **RUM ordered user actions** (`skills/session-stitch`, `rum-sessions`) — when the
   backend exposes a RUM user-event stream keyed by a session id, you get real browser
   journeys with measured per-page think-times. This is the richest signal; it needs the
   read token's RUM scopes (see [`requirements.md`](requirements.md) §1).
2. **OTel `session.id` on spans** — Grail-native, app-agnostic, no extra token. Where an
   app propagates a `session.id`, SCOPE stitches real sessions directly from the spans it
   already extracted and derives measured think-times. Works beyond browser apps.
3. **Span-order fallback** — where no session signal exists, SCOPE falls back to span
   ordering and records the gap.

The model records which source drove each endpoint (`metadata.source.*`,
`source.rumSessionCoverage`), and merges RUM-driven and span-only endpoints transparently
so the provenance is auditable rather than blurred. See
[`../examples/session-reconstruction.example.json`](../examples/session-reconstruction.example.json)
for the shape.

---

## 4. VALIDATE — the human gate (V1)

A person reads `scenario-proposal.md` — what was analyzed, the journeys and weights, the
arrival profile, the payload strategy, where it will run, the risks, and the explicit
decision requested — and **approves, adjusts, or rejects**.

Approval is **bound to the model revision**. There is no agent self-approval, and any
later edit to the model invalidates a prior approval. Everything downstream fails closed
until this gate passes. This gate is the entire point of the methodology.

---

## 5. SYNTHESIZE — model → runnable test (V2a)

A renderer skill turns the approved model into a runnable test:

- `k6-synthesis` (native fit), plus `jmeter-synthesis`, `locust-synthesis`,
  `gatling-synthesis` — all behind one `renderer-kit` interface, with the `§4` model as
  the sole contract. Each renderer declares its approximations via a `supports()`
  capability report (e.g. mapping an open arrival model onto a closed-native tool).
- Generated tests carry `baggage: synthetic=true` on every request (P4), one arrival-rate
  scenario per journey, request chaining with fail-fast, and cache-avoidance payload
  pools.

**Gate V2a** is a static check (schema-valid model in, the tool's own static validation
out — `node --check` / tool dry-run when the binary is absent). Script generation is
always deterministic codegen we own — never an LLM "generate" prompt — so output is
reproducible and golden-testable.

---

## 6. EXECUTE — scoped, capped, abort-guarded (V2b)

`skills/loadtest-run` runs the test inside a harness that enforces:

- a **non-production allowlist** (P5) checked before anything runs,
- **hard caps** (max VUs/arrival rate, max duration, max data) and an **automatic abort**
  on breach,
- a **smoke gate (V2b)** — a small confirmation run with pass criteria — before the full
  run is allowed.

The run emits a machine- and human-readable run report.

---

## 7. ANALYZE — shape-diff then decide (V3)

`skills/baseline-diff` compares the **shape** of the test run against the observed
baseline across tolerance dimensions — arrival shape, latency distribution, service
fan-out, error rate, journey mix — plus a mandatory **R5 infrastructure cross-check** (did
the test drive the same downstream services the baseline did, or did it miss/overshoot
tiers?). The `synthetic == true` filter (P4) separates the generated traffic from the real
baseline inside the same environment.

The verdict is one of:

- **accept** — within tolerance; ship the report + artifacts.
- **iterate** — out of tolerance in a parameter-tunable way; adjust parameters only and
  re-run, bounded to **≤3×**.
- **escalate** — a structural mismatch a parameter tweak cannot fix; back to a human.

See [`../examples/baseline-diff.example.json`](../examples/baseline-diff.example.json).

---

## 8. Safety rules (summary)

- Non-production allowlist enforced at V2b; production is an explicit recorded human
  exception, never a default.
- Hard caps + automatic abort on every run.
- Secrets live in the environment / a secret store, never in committed artifacts; generated
  load telemetry is tagged `synthetic=true` and never blurred with real traffic.
- Run `tools/secret-scan.sh` before publishing or sharing any artifact.

---

## 9. Known fidelity caveats

These are carried as explicit caveats, not assumed solved — honesty about fidelity is part
of the method:

- **R1 / R2 — extraction fidelity.** Journeys and mixes are only as good as the telemetry
  window; a narrow or atypical window produces a narrow or atypical model. Choose a
  representative window and sanity-check the proposal.
- **R5 — session coverage.** Full session fidelity depends on a session signal being
  present end-to-end. Where `session.id` is sparse or RUM scopes are absent, think-times
  and ordering degrade to span-order assumptions; closing this fully is an app-side
  instrumentation ask (propagate a session id across all services).
- **Governance.** Overfitting to V3 tolerances, autonomy eroding the V1 gate, and
  non-stationarity between extract-time and run-time are governance calls for the humans
  owning the test, not something the tooling decides.
