# Realistic Load Testing from Observability Data — Research Note
*ISI-4032 (PAC loadtesting & AI) · 2026-09-08 · compiled by Alfred*

## Goal
Generate load tests that reflect production reality by deriving them from observability data (OTel traces, metrics, logs) instead of hand-guessed scenarios.

## 1. Workload modeling from telemetry (foundation)
Extract from production telemetry:
- RPS profile: peak/avg, hourly/daily seasonality, ramp shapes
- Endpoint mix: frequency, read/write ratios, payload size distributions
- Latency percentiles (p50/p95/p99) and error/retry rates per endpoint
- User journeys: span-tree sequences per trace (entry spans → downstream fan-out)
- Service dependency graph from traces (which calls propagate where)
- Think-time distribution from inter-span gaps within journeys

Model decisions:
- Open workload model (arrival-rate executors) for public APIs; closed model (VU-based) for seat-limited systems
- Validate with Little's Law: concurrency = arrival rate x mean response time

## 2. Trace-driven replay approaches
- **Transform, not raw replay**: extract journeys/timings/attributes from spans -> sanitize (PII, env-specific fields) -> materialize as scripted load
- **Speedscale**: OTel-trace-based traffic replay with CI release gates (closest off-the-shelf to "replay from observability")
- **GoReplay**: raw HTTP capture/replay (needs capture at edge, not trace-based)
- **HAR-to-k6 / k6 Studio**: session-recorded journeys -> k6 scripts (per-journey realism, misses fleet-level distribution)
- OTel baggage tag (synthetic=true) on generated traffic to separate test vs prod telemetry

## 3. AI-assisted generation (the PAC angle)
Pipeline: telemetry digest (journeys, distributions, seasonality) -> LLM -> k6 scenario scripts + synthetic payload data
- Grafana Assistant k6 script authoring: NL -> k6 grounded in Grafana Cloud telemetry (proof the pattern ships)
- LLM-generated synthetic payloads matching production distributions without PII
- Guardrails: LLM output must be validated against real traffic baselines (shape-match) — never trust hallucinated patterns

## 4. Validation loop ("reflecting reality" proof)
1. Run generated load against staging/canary with full OTel instrumentation
2. Compare resulting telemetry distributions vs production baseline: RPS shape, latency histograms, service-graph fan-out, error rates (DQL in Dynatrace is ideal for this shape-diff)
3. Iterate the workload model until test-time telemetry matches prod within tolerance
4. Use Tracetest for trace-based assertions during load (validate internal spans, not just client-side metrics)

## Proposed PAC pipeline (uses our stack)
Dynatrace (DQL via dtctl) -> workload-model JSON -> generator (LLM-assisted k6 synthesis) -> k6 + k6-OTel-extension -> collector -> Dynatrace baseline diff -> iterate. Scenarios versioned in this repo.

## References
- https://grafana.com/blog/how-to-generate-real-world-load-tests-using-grafana-cloud-k6-and-production-telemetry/
- https://speedscale.com/blog/otel-trace-testing-ci-release-gates/
- https://docs.tracetest.io/tools-and-integrations/k6
- https://grafana.com/docs/k6/latest/using-k6/test-authoring/create-tests-from-recordings/
- https://perfmatrix.com/performance-test-workload-modelling/
- https://grafana.com/blog/generate-test-scripts-from-natural-language-with-grafana-assistant-introducing-k6-script-authoring/
- https://opentelemetry.io/docs/demo/services/load-generator/
