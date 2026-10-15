# Usage

End-to-end: from a telemetry window to an accepted load test. For the method behind each
step see [`methodology.md`](methodology.md); for the engine specifically see
[`engine.md`](engine.md).

## 0. Install — two commands

```bash
# 1 — install the skills into your coding agent (fetch + verify)
curl -fsSL https://raw.githubusercontent.com/henrikrexed/AI-Performance-Testing/main/install.sh | sh
# 2 — start the guided loop (init prints this exact command)
python3 engine/cli.py guided \
    --extract examples/crewai-deepseek-agent/extract.json --out ./out --mode agentic
```

That is the whole onboarding — details and the no-curl equivalent (`python3 engine/cli.py
init`) are in [`skills-install.md`](skills-install.md). For backend runs you also need
Dynatrace tokens/scopes + `dtctl` ([`requirements.md`](requirements.md)); the released
binary / Docker image paths are in [`engine.md`](engine.md) §1.

```bash
cp .env.example .env     # fill in DT_ENDPOINT, DT_API_TOKEN (+ OTLP token if exporting)
```

## 1. Try it with no backend (10 minutes)

Run the first half of the loop on the bundled synthetic example — no tenant, no tokens:

```bash
# SCOPE on a synthetic extract -> G0-validated model + human-readable proposal
# (output is stamped provenance.kind=demo-sample — demo data is never silently selectable)
(cd skills/workload-model && python3 scripts/build_example.py \
  && cat out/example-frontend/scenario-proposal.md)

# SYNTHESIZE the committed example model -> a runnable k6 script (V2a static gate)
# --demo: the example model is demo-stamped; renderers refuse demo data without opt-in
(cd skills/k6-synthesis \
  && node bin/synthesize.mjs ../../examples/workload-model.example.json /tmp/example-out --demo)
```

The example artifacts in [`../examples/`](../examples) show exactly what each stage
produces.

## 2. Run the loop against your own backend

This is the same gated 4-step flow the `engine/cli.py guided` command runs
([`engine.md`](engine.md) §3: **propose + confirm → choose output → generate → opt-in
try**), driven by a coding agent against a live backend instead of the bundled extract.
With an agent that has the skills installed and `DT_ENDPOINT` / `DT_API_TOKEN` pointed at
your tenant, ask for the loop in plain language:

> "Scope a load test for service `checkout` over the last 3 hours."

The agent will:

1. **SCOPE** — run the fail-closed environment probe first
   (`skills/workload-model/scripts/env_probe.py`: dtctl present · DQL reachable · target
   observed — no probe, no extraction, **never a silent fallback to example data**), then
   run the DQL extraction (via `dtctl`), build a `workload-model.json` stamped with its
   provenance (`extracted-from: <query pack> on tenant <Y> (<window>)`), and
   write a `scenario-proposal.md`. The engine self-checks with **G0**.
2. **VALIDATE** — stop and present the proposal. **Nothing runs until you approve it**
   (Gate V1). Approval is bound to the model revision; editing the model invalidates it.
3. **SYNTHESIZE** — turn the approved model into a runnable test (k6 by default; JMeter /
   Locust / Gatling via the other renderers), every request tagged `synthetic=true`.
4. **EXECUTE** — a smoke run (V2b) against a **non-production allowlist**, then a capped,
   abort-guarded full run. `skills/loadtest-run` enforces the caps.
5. **ANALYZE** — `skills/baseline-diff` shape-diffs the run against the observed baseline
   (V3) and returns **accept / iterate (≤3×) / escalate**.

## 3. Make `synthetic=true` queryable

For ANALYZE to separate test traffic from the baseline, the `synthetic` baggage must be
promoted to a queryable attribute in your pipeline. The tutorial collector does exactly
this: [`../tutorial/otel-demo/collector.yaml`](../tutorial/otel-demo/collector.yaml).
Without the promotion, the `synthetic == true` filter matches nothing (methodology P4).

## 4. Full worked tutorial

[`../tutorial/README.md`](../tutorial/README.md) walks the whole loop against a deployable
demo AI-agent component — deploy the app, generate a baseline window, and run all five
stages for real, including the V1 approval gate refusing synthesis until you sign off.

## 5. Before you share anything

Run the pre-publish scan from the repo root — it must exit clean:

```bash
bash tools/secret-scan.sh
```
