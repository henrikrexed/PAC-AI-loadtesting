# Phase 4 — End-to-End Demo Runbook (lean otel-demo path)

*ISI-4047 · Phase 4 of the PAC "Loadtesting & AI" track ([ISI-4032](/ISI/issues/ISI-4032), plan rev 1, approved 2026-09-08)*
*Applies [`docs/methodology.md`](methodology.md) (Phase 2, ISI-4045 — **validated/done**) · consumes [`docs/skills-mcp-decisions.md`](skills-mcp-decisions.md) (Phase 3, ISI-4046)*

**Status:** ready to execute pending one input — target environment (cluster + Dynatrace tenant). Approach confirmed by Henrik's 2026-09-08 direction (deploy otel-demo → load → capture → analyze 24h later).

---

## 0. Why this runbook (product decision)

The Phase-4 **plan document** on the issue describes the full loop and lists a heavier
enablement path (build 5 reusable skills: BL-1…BL-8 / ISI-4050…4057). This runbook is the
**lean demo path** Henrik proposed on 2026-09-08:

> "deploy the opentelemetry demo, trigger the load, capture the traces in dynatrace, then start
> the process to analyze the traces produced … 24h after the deployment — we could test our
> process and methodology."

**A Phase-4 *demo* does not need 5 polished skills.** It needs the loop run **once, end-to-end,
on one target**, with every number traced to telemetry and the human gate exercised. We run it
with direct tooling (dtctl DQL by hand/agent, k6 authored directly, DQL diff). The 5-skill build
(BL-1…BL-8) is **post-demo productionization** — it makes the loop cheap and repeatable, and can
proceed in parallel if the board wants it, but it is **not a prerequisite for the demo**.

The clever part of Henrik's framing: **otel-demo ships its own load generator** (Locust-based,
hitting `frontend-proxy`). We let that run for 24h → it *is* the "production" baseline. Then our
methodology-generated k6 traffic (`synthetic=true`) is diffed against that baseline. Self-contained,
disposable, obviously non-prod, and it kills the plan's #1 risk ("no telemetry history").

---

## 1. Roles at each stage

| Stage | Owner | This runbook |
|---|---|---|
| Deploy otel-demo + wire baggage→attribute promotion + start 24h baseline | **DevOps + Observability** | §3 |
| SCOPE — DQL analysis → `workload-model.json` + proposal | delegated agent run | §4 |
| **VALIDATE — approve/adjust the scenario** | **Henrik** (Gate V1, `request_confirmation`) | §5 |
| SYNTHESIZE — k6 + payloads from approved model | delegated agent run | §6 |
| EXECUTE — scoped k6 run, `synthetic=true` | delegated agent run | §7 |
| ANALYZE — DQL shape-diff + before/after report | delegated agent run | §8 |
| Demo packaging (recording + diff report) | PM / Architect | §9 |

---

## 2. Prerequisites (confirm before §3)

- [x] **Phase 2 methodology validated** — ISI-4045 `done`.
- [ ] **Target cluster** — a non-prod k8s cluster to host otel-demo. *(Needs Henrik: internal CI/registry has been flaky — ISI-3913, ISI-4040. Confirm a healthy target.)*
- [ ] **Dynatrace tenant/profile** — dtctl profile + tenant that receives the otel-demo OTLP export. *(Needs Henrik.)*
- [ ] **Blast-radius caps** for our k6 run (max RPS / VUs / duration). *(Needs Henrik; default proposal in §7.)*
- [ ] **Non-prod allowlist entry** for `frontend-proxy` of the deployed otel-demo (methodology P5).

## 3. Deploy + wire promotion + 24h baseline (DevOps + Observability)

1. **Deploy otel-demo** to the target cluster (helm chart `open-telemetry/opentelemetry-demo`),
   OTLP export pointed at the Dynatrace tenant. Keep the bundled `load-generator` **on** — it is
   our production-baseline traffic source.
2. **Wire baggage→attribute promotion (HARD prerequisite, methodology P4/§7.7).** In the demo's
   OTel Collector, add a processor that copies baggage member `synthetic` onto spans as a
   queryable attribute, so DQL can separate our test traffic from the loadgen baseline:

   ```yaml
   processors:
     transform/baggage:
       trace_statements:
         - context: span
           statements:
             - set(attributes["synthetic"], "true") where instrumentation_scope.name != "" and attributes["baggage.synthetic"] == "true"
   ```

   (Or the SDK baggage span processor / collector `baggage` processor — whichever the tenant's
   pipeline supports. Owner: Observability Agent, per methodology §7.7.)
3. **Warm-up probe:** after our k6 emits any traffic (§7), assert a **non-zero** count of
   `synthetic == true` spans in DQL **before** trusting any diff. Zero ⇒ promotion missing, not
   "shapes match."
4. **Let the loadgen run ≥24h** to build a deploy/incident-free baseline window. Record the exact
   ISO interval used as the baseline.
5. **Validate the DQL query pack** (methodology §3.1) against live field names on this tenant
   (entry-span identification, error counting, `service.name`) before baking into SCOPE/ANALYZE —
   the O11y query-validation gate.

## 4. SCOPE (delegated agent run)

Run the methodology §3.1 DQL pack over the deploy/incident-free baseline window on `frontend`
(otel-demo entrypoint service):
- top entry operations by volume; per-minute arrival curve; p50/p95/p99 + error per entry op;
  service-graph fan-out from traces.
- cluster traces into journeys to ≥80% coverage (otel-demo gives a real mix: browse product →
  view cart → checkout → payment/shipping fan-out).
- link each journey step to code (`codeRef`) in the otel-demo services.
- fit open vs closed arrival model + Little's-Law sanity check.
- emit `loadtests/otel-demo/workload-model.json` (+ `scenario-proposal.md`); self-check **Gate G0**.

## 5. VALIDATE (Henrik — Gate V1)

`request_confirmation` bound to the `workload-model.json` revision. Henrik approves/adjusts.
Hash-bound: any model change re-opens the gate. No auto-approval (methodology §3.2).

## 6. SYNTHESIZE (delegated agent run)

From the **approved** model: one k6 scenario per journey group; arrival-rate executors (open) /
VU executors (closed); think times + weights from the model; seeded synthetic payloads (no prod
data). **Every request carries `baggage: synthetic=true`.** Static **Gate V2a**
(`k6 inspect`, baggage present, caps respected, committed to `loadtests/otel-demo/k6/`).

## 7. EXECUTE (delegated scoped run)

`run-config.json` fixes the blast radius against `frontend-proxy` (allowlist, ≠ prod). Proposed
default caps (Henrik to confirm/adjust): **maxRps 200, maxVUs 100, duration 30m**, abort on
`errorRate > 5%` or `p95 > 2500ms`. Pre-flight **Gate V2b**; warm-up probe (§3.3) asserts
`synthetic==true` spans exist before the diff. Emit `runs/<ts>/run-report.md`.

## 8. ANALYZE (delegated agent run)

DQL shape-diff of test traffic (`synthetic==true`) vs the 24h loadgen baseline across the five
dimensions (arrival shape / latency / fan-out / error rate / journey mix), with sampling-parity
and scale-factor normalization recorded in `shape-diff.json` (methodology §3.5). Within tolerance
→ ACCEPT + **before/after diff report** (the headline deliverable). Out → classify + iterate
(params only, ≤3) or escalate.

## 9. Demo packaging

- **Recorded run** (primary): narrated capture of the five stages — the DQL queries, the Gate V1
  confirmation card, the generated k6, and the final before/after diff.
- **Optional live replay** for PAC: reduced-scale re-run against the same non-prod target using
  the committed artifacts + `run-config.json`.
- **Before/after diff report**: side-by-side baseline vs test across the 5 dimensions with
  tolerance verdicts — the headline artifact for the deck.

## 10. Deliverables (all under `/mnt/nas/projects/PAC-AI-Loadtest`)

`loadtests/otel-demo/workload-model.json` · `scenario-proposal.md` · recorded Gate V1 approval
trail · `k6/*.js` + `payloads/*` · `run-config.json` + `runs/<ts>/run-report.md` ·
`runs/<ts>/shape-diff.json` + before/after diff report · demo recording (+ optional live-replay
script).

## 11. Critical path / what's actually gating

1. **Henrik: target env** (cluster + Dynatrace tenant) + caps → unblocks §3.
2. §3 (deploy + baggage promotion + 24h capture) is a **~24h elapsed** step → the natural pacing
   of the demo; everything downstream (SCOPE→ANALYZE) is same-day agent work once the baseline
   exists.
3. Baggage→attribute promotion is the one technical prerequisite that, if skipped, makes ANALYZE
   meaningless — wired in §3.2 before any k6 traffic.
