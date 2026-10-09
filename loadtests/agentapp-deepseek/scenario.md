# Load scenario: crewai-deepseek-agent (ISI-5644)

Sustained open-model driver for the workload-model generalization test. See
`deploy/agentapp/README.md` for build/deploy; this note defines the load shape and the
expected skill conclusion so the Observability Agent can confirm the generalization.

## Driver (loadtests/agentapp-deepseek/driver.js)

| param | default | why |
|---|---|---|
| executor | `constant-arrival-rate` | open model — arrivals independent of DeepSeek latency, so the reconstructed arrival curve is the specified one |
| RATE_PER_MIN | 20 | ~900 turns over 45m — enough for pace/CoV + per-turn baseline |
| DURATION | 45m | one clean window |
| TOOL_RATIO | 0.30 | ~30% tool-using / ~70% pure-LLM → both archetypes well-populated |

Each turn is independent (fresh agent, no shared memory) so the arrival process is a clean
turn sequence. Tool turns force `web_search`/`calculator` (ReAct loop → `execute_tool` spans);
chat turns attach no tools (pure-LLM).

## Expected workload-model conclusion (skill unchanged)

Front-end discovery resolves the entry op `crewai-deepseek-agent/request`. The terminal-action
classifier (`AGENTIC_TOOL_PATTERNS`, terminal = `execute_tool`) splits:

| archetype | signal | expected weight |
|---|---|---|
| Agentic (tool-using turn) | trace contains `execute_tool` | ≈ `TOOL_RATIO` (0.30) |
| Conversational (pure-LLM turn) | no `execute_tool` | ≈ `1 − TOOL_RATIO` (0.70) |

Same conclusion *shape* as the openclaw-gateway live run and the astronomy-shop Buyer/Browser
split — the §2.1 agnostic-engine thesis, now on a **DeepSeek**-backed app under representative
load (the honest limit called out in GENERALIZATION.md: n≈18 / GLM → sustained / DeepSeek).

G0 expectation: coverage 1.0 (the two archetypes partition all turns), per-turn baseline p95
derived from the `agent.turn` server span (not the k6 wrapper — same Little's-Law stance as the
astronomy scenario proposal).
