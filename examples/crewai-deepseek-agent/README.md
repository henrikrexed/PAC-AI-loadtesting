# Example: `crewai-deepseek-agent` — agentic workload extract

`extract.json` in this directory is the **worked example** for the `workload-model`
engine and the reference for the generic **extract contract** the engine CLI consumes.
It describes a CrewAI + DeepSeek agent app observed over one clean, deploy-free load
window; the behavioral split comes from whether a turn invokes a tool (ReAct loop) or
stays pure-LLM.

Run it (this is exactly what the release build smoke-tests):

```bash
workload-engine --extract examples/crewai-deepseek-agent/extract.json --out out --mode agentic
# from source, equivalently:
python -m engine.cli --extract examples/crewai-deepseek-agent/extract.json --out out --mode agentic
```

It writes `out/workload-model.json` + `out/scenario-proposal.md` and exits `0` iff the
G0 gate passes (it does — 12/12 checks).

## The `extract.json` contract

`extract.json` is the engine's only input: the facts you pull from your telemetry
(Dynatrace DQL, OTel spans, access logs) for one application over one deploy-free window.
It is a superset-friendly JSON document — unknown keys are ignored. Full field notes live
in [`docs/engine.md`](../../docs/engine.md); the essentials:

| Field | Req | Meaning |
|---|---|---|
| `name` | ✓ | model name (`^[a-z0-9][a-z0-9-]*$`) |
| `targetService` |  | service analyzed (defaults to `name`) |
| `environment` | ✓ | tenant/environment analyzed |
| `timeframe` | ✓ | the window analyzed |
| `accessLogAvailability` |  | `available` / `unavailable` / `unknown` |
| `samplingRatio` |  | R1: source sampling ratio (1.0 = unsampled) |
| `dqlRunLive` |  | attest queries ran live (G0 criterion; default `true`) |
| `queries` |  | the queries that produced these facts (recorded in the model) |
| `coverage` |  | share of entry traffic covered (defaults to Σ archetype weights) |
| `arrival` | ✓ | `arrivalRateTps`, `meanServerResponseMs` (server span!), `observedConcurrency` |
| `perMinuteCounts` | ✓ | per-minute arrival curve (drives the CoV ramp gate G3) |
| `archetypes` | ✓ | behavioral journeys (see below) |
| `payloads` |  | synthetic payload pools keyed by id |
| `caps` |  | `maxRps`/`maxVus` + `maxDuration` (default `{maxRps:2,maxVus:20,maxDuration:"30m"}`) |
| `exclusions` / `targetEnv` / `abortNote` / `risks` |  | proposal prose overrides |

Each **archetype** carries its id, `weight` (share of covered traffic), `entrypoint`,
entry `codeRef`, `evidenceSource` (`span`/`accesslog`/`both`), a server-span `baseline`
(`p50Ms`/`p95Ms`/`p99Ms`/`errorRate`), and the ordered, telemetry-reconstructed `steps`
(each with `id`/`service`/`operation`/`callType`, and a `codeRef` + optional `payloadRef`).

The engine assembles one journey per archetype, shapes the arrival profile, runs the
Little's-Law concurrency check, and self-validates everything with the G0 gate before it
will emit. `--mode` names the terminal signal the archetypes were split on (`agentic` =
tool-use; `commerce` = order) — same engine, different signal (methodology §2.1).
