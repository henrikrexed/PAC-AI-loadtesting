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

## Follow-up

Child issue created to deploy a Goose recipe or CrewAI + DeepSeek agent app in the cluster,
instrument it (OTel → Dynatrace), and generate representative load, after which this skill runs
unchanged to produce its workload model. The skill side is ready; the blocker is the app+load.
