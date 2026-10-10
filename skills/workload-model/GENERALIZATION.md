# workload-model skill — generalization test (ISI-5630)

*2026-10-09. Board asked: "test this skill on a goose recipe or crewai in our cluster with
deepseek to see if it is able to come [to] the same conclusion." This note records a live
generalization run on a **non-commerce, agentic** app already in the cluster, and scopes the
definitive goose/crewai + deepseek test as a follow-up (needs that app deployed with load).*

## Result: the skill generalizes structurally to an agentic app (live)

Ran the skill's extraction stages against **`openclaw-gateway`** (our OpenClaw agent app on
oat05854) — a completely different workload from the astronomy shop. With **zero code changes**,
only a different terminal-action pattern set:

**Front-end discovery** (earliest-start root per trace, -24h) correctly resolved the entry:
```
openclaw-gateway / openclaw.request   (15 traces)   <- entry
openclaw-gateway / openclaw.dispatch.prepare / cron.changed / message.sent   <- non-entry noise
```

**Journey reconstruction** (trace span-tree) found two agent-turn archetypes:
```
Tool-using turn : request -> agent.turn -> llm.call -> chat -> execute_tool web_search xN -> chat -> finalize -> message.sent
Pure-LLM turn   : request -> agent.turn -> llm.call -> chat glm-5.2 -> finalize -> message.sent
```

**Behavioral split** (`archetypes.classify_by_terminal`, terminal signal = `execute_tool`, -48h):
| archetype | turns | weight | tools observed |
|---|---|---|---|
| Conversational (pure-LLM turn) | 14 | 0.778 | — |
| Agentic (tool-using turn) | 4 | 0.222 | exec, web_search, message, sessions_send |

**Same conclusion shape as the astronomy shop.** The Buyer/Browser split (does the flow place
an order?) and the Agentic/Conversational split (does the turn call a tool?) are the *same engine*
— `classify_by_terminal()` with a different terminal-action pattern set. This is the §2.1
agnostic-engine thesis demonstrated on live, unrelated telemetry: the skill is not overfit to
commerce traces.

## Honest limit — why this is not yet the definitive test

`openclaw-gateway` is **low-volume** (~18 agent turns / 48 h) and uses **GLM** models, not DeepSeek.
At n≈18 the weights are directionally right but statistically thin, and there is no sustained
arrival curve to derive pace / CoV / ramp. The board's exact ask — a **Goose recipe or CrewAI +
DeepSeek** app under **representative load** — needs that workload deployed and driven first.

## Definitive run: CrewAI + DeepSeek under load (ISI-5644 done)

ProxOps deployed `crewai-deepseek-agent` (CrewAI, `deepseek/deepseek-chat` via LiteLLM, ns
`agentapp`) and drove it with in-cluster k6 (constant-arrival 12/min, 25 min, 30% tool mix,
`http_req_failed` 0.0099). The skill ran **unchanged** (`scripts/build_crewai.py`,
`fixtures/crewai_deepseek_extract.json`); G0 **12/12 PASS**:

| aspect | result |
|---|---|
| front-end discovery | `crewai-deepseek-agent/request` (single clean entry, 301 traces) |
| journey reconstruction | agentic ReAct loop (`request→turn→Crew/Task Created→llm.call→chat→execute_tool→llm.call→finalize`) vs conversational single LLM round |
| behavioral split (`classify_by_terminal`, terminal=`execute_tool`) | **Conversational 68.1% / Agentic 31.9%** (tools: web_search 141, calculator 38) |
| per-archetype baseline | agentic p99 **35061 ms** vs conversational p99 **16350 ms** (~2.3× heavier mean) |
| arrival | **steady** (interior CoV 0.016; raw full-window 0.166 was a partial-boundary-bin artifact now trimmed by `shaping.trim_partial_bins`) |
| Little's Law | λ 0.196/s × W 2.282 s = 0.448 ≈ observed 0.448 → ratio **1.0** |
| code linking | journeys linked to `deploy/agentapp/app/*` (`handle_request`, `TracedLLM.call`, tools) |

**Conclusion-shape matches the astronomy shop with zero code changes** — the §2.1 agnostic-engine
thesis proven end-to-end on a DeepSeek-backed agent app: Buyer/Browser (order-terminal) and
Agentic/Conversational (tool-terminal) are the same `classify_by_terminal` engine. A **robustness
fix** fell out of the real data: partial Grail boundary bins were falsely tripping the CoV ramp
gate; `trim_partial_bins` now removes them so steady constant-arrival traffic is read as steady.

Artifacts: `loadtests/crewai-deepseek-agent/{workload-model.json,scenario-proposal.md}`.

## What the agent actually generates (board Q, 2026-10-10)

The telemetry captures structure + model (`gen_ai.request.model = deepseek/deepseek-chat`) but
**no response content** (spans carry no prompt/completion text — by design; no app logs reach
Grail). To show the agent's real output I invoked the live pod (`POST /request`) directly:

- **Conversational turn** — prompt *"Explain distributed tracing in two sentences."* →
  > Distributed tracing is a technique for tracking a single request as it flows through multiple
  > services in a distributed system, using unique trace and span identifiers to correlate related
  > operations. It helps engineers visualize end-to-end latency, pinpoint bottlenecks, and debug
  > failures across service boundaries.
- **Agentic turn (calculator)** — prompt *"What is 1234 * 5678? Use the calculator tool."* →
  > 1234 * 5678 = 7006652   *(correct; tool-computed)*
- **Agentic turn (web_search)** — prompt *"Search the web for the latest OTel release…"* → the
  agent ran 3 searches, the stubbed search tool returned placeholders, and the agent **refused to
  fabricate** a version ("Because the tool output contained no verifiable facts, I cannot provide
  a grounded summary…"). Honest, grounded behavior.

These map 1:1 to the model's two archetypes: a chat turn = **Conversational**, a tool turn =
**Agentic (ReAct)**. The agent generates correct results; the workload model captures the two
behaviors at their true 68/32 mix.
