# AI-Performance-Testing

An observability-driven, AI-agent-friendly toolkit for **realistic** load testing —
built around one idea: **your telemetry already knows what your real workload looks
like; extract it, have a human approve it, then replay it faithfully.**

Maintained by [Henrik Rexed](https://www.youtube.com/@IsItObservable) (IsItObservable).
The methodology and toolkit were developed and battle-tested on the
[IsItObservable](https://www.youtube.com/@IsItObservable) channel's cloud-native and AI
benchmarking projects.

## The loop

```mermaid
flowchart LR
    SCOPE -->|G0| VALIDATE -->|V1| SYNTHESIZE -->|V2a| EXECUTE -->|V2b| ANALYZE
    ANALYZE -->|"V3 — iterate (parameter-only, ≤3×) or escalate"| SCOPE
```

| Stage | What happens | Who owns it |
|---|---|---|
| **SCOPE** | extraction queries over a clean telemetry window → journeys, arrival profiles, think-times, payload strategy (`workload-model.json`) | you / your coding agent |
| **VALIDATE** | a human reads `scenario-proposal.md` and approves, adjusts, or rejects — recorded in the model, revision-bound | **a human, always** |
| **SYNTHESIZE** | approved model → runnable k6 scripts + synthetic payload pools (V2a static checks) | you / your agent |
| **EXECUTE** | small confirmation test first (six pass criteria), then a capped, abort-guarded full run | you / your agent |
| **ANALYZE** | shape-diff of test vs baseline across six dimensions → accept / iterate / escalate | machine + human cap |

Why it is built this way:

- **Realism is measured, not guessed** — journeys, pacing, and think-times come from
  your own telemetry (spans, access logs, RUM sessions, OTel `session.id`).
- **A human gate is mandatory** — no test runs against any environment before a person
  approves the workload model (Gate V1). Fail-closed everywhere downstream of it.
- **Synthetic traffic is identifiable** — generated load carries `synthetic=true`
  baggage promoted to a queryable attribute, so test and real traffic never blur.
- **AI does the legwork, not the deciding** — the skills are written for coding agents
  (Claude Code, opencode, Cursor, …); every consequential decision stays with a human
  or a deterministic gate.

## Documentation

| Doc | What it covers |
|---|---|
| [`docs/methodology.md`](docs/methodology.md) | The method: principles, the five-stage loop, every gate, dual-source session reconstruction, safety rules, fidelity caveats |
| [`docs/usage.md`](docs/usage.md) | End-to-end usage — no-backend quickstart, running the loop against your own tenant, the full tutorial |
| [`docs/engine.md`](docs/engine.md) | The workload-model engine: install per platform (binary / Docker / k8s / source) and its role in the loop |
| [`docs/requirements.md`](docs/requirements.md) | Dynatrace tokens + **scopes**, `dtctl` + its agent skill, Davis AI, everything else |
| [`docs/skills-install.md`](docs/skills-install.md) | Installing the skills into Claude Code, opencode, Cursor, or any agentskills.io agent |

## Quickstart

**No backend, 10 minutes** — run the loop's first half on the bundled synthetic example:

```sh
git clone https://github.com/henrikrexed/AI-Performance-Testing.git
cd AI-Performance-Testing

# SCOPE: synthetic extraction → G0-validated model + human-readable proposal
(cd skills/workload-model && python3 scripts/build_example.py && cat out/example-frontend/scenario-proposal.md)
```

Then continue in [`tutorial/README.md`](tutorial/README.md) — including how SYNTHESIZE
refuses the model until you (the human) approve it.

**Full experience** — your own Dynatrace trial + a DeepSeek key: the tutorial deploys a
demo CrewAI agent app, generates a baseline window, and runs all five stages for real.

## Configuration

All environment wiring is documented in [`.env.example`](.env.example) — copy to `.env`,
fill in your values, never commit a real `.env`. Two tokens by design: a read-only DQL
token and a separate OTLP ingest token. The exact **token scopes** (including
`storage:user.events:read`, the one that is easy to miss for RUM-driven journeys) and the
`dtctl` setup are in [`docs/requirements.md`](docs/requirements.md).

The backend is currently **Dynatrace (Grail/DQL)** for extraction and analysis. The
deterministic core (clustering, shaping, emission, gates) is backend-agnostic — the DQL
pack is the seam you would reimplement for another backend. Generated tests are plain
k6 and run anywhere k6 runs.

## Requirements

- Python 3.11+, Node.js 20+, k6 (only for EXECUTE; skills degrade to `node --check`)
- A Dynatrace environment (trial works) for the live loop — tokens + scopes in
  [`docs/requirements.md`](docs/requirements.md)
- Each `skills/*/` directory is self-contained with its own tests:
  `python3 -m pytest` / `node --test` inside it

## Installing

- **Engine** — grab a released binary (linux/macOS/windows), the multi-arch Docker image
  `ghcr.io/henrikrexed/ai-performance-testing`, or run from source. All paths:
  [`docs/engine.md`](docs/engine.md).
- **Skills** — copy `skills/*` onto your agent's skills path (Claude Code, opencode,
  Cursor, or any agentskills.io agent): [`docs/skills-install.md`](docs/skills-install.md).
- **Backend** — install `dtctl`, set a context, and mint the read-only DQL token:
  [`docs/requirements.md`](docs/requirements.md).

## Using the skills with a coding agent

The `skills/*/SKILL.md` files follow the agent-skill convention. Install them into your
coding agent (Claude Code, opencode, Cursor, …), point `DT_ENDPOINT`/`DT_API_TOKEN` at
your tenant, and ask for the loop: *"scope a load test for service X over the last 3
hours"*. The agent runs the DQL and the deterministic scripts; you get the proposal at
the VALIDATE gate. Nothing runs without your approval. Full walkthrough in
[`docs/usage.md`](docs/usage.md).

## License

[MIT](LICENSE) — © 2026 Henrik Rexed.
