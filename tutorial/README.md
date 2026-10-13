# Tutorial: the AI-Performance-Testing loop, end to end

This walkthrough takes you from an empty machine to a **completed, analyzed load test** of
an AI agent service, using your own observability backend as the source of truth.

You will:

1. Clone the toolkit and configure `.env`
2. Deploy a small demo component (a CrewAI + DeepSeek agent app) and wire its telemetry
   to **your own** Dynatrace environment
3. Generate a realistic baseline traffic window
4. Run the five-stage loop — **SCOPE → VALIDATE → SYNTHESIZE → EXECUTE → ANALYZE** —
   against that telemetry
5. Interpret the results and decide what happens next

Two ways to run it:

- **Live mode** (the full experience): demo component + your Dynatrace trial + your
  DeepSeek key. Takes about 90 minutes, most of it a hands-off 45-minute traffic window.
- **Offline warm-up** (no backend, no keys): run the SCOPE→VALIDATE→SYNTHESIZE stages
  against the bundled synthetic example and see every artifact. Stage 5.1 below. Ten
  minutes.

The five stages, who owns each, and the gate between them:

| # | Stage | Owner | Input | Output | Gate |
|---|---|---|---|---|---|
| 1 | **SCOPE** | you / your coding agent | telemetry window (DQL) | `workload-model.json` + `scenario-proposal.md` | G0 (machine) |
| 2 | **VALIDATE** | **a human — you** | `scenario-proposal.md` | approval record in the model | V1 (human) |
| 3 | **SYNTHESIZE** | you / your agent | approved model | runnable k6 scripts + payload pools | V2a (machine) |
| 4 | **EXECUTE** | you / your agent | k6 scripts + `run-config.json` | run reports + telemetry | V2b-smoke, V2b (machine) |
| 5 | **ANALYZE** | you / your agent | test + baseline telemetry | `shape-diff.json` + verdict | V3 (machine + human cap) |

---

## 1. Prerequisites

| Need | Why | Get it |
|---|---|---|
| Dynatrace environment (trial is fine) | telemetry backend for the loop | dynatrace.com free trial |
| Dynatrace **read token**: `storage:spans:read`, `storage:logs:read` | DQL queries in SCOPE/ANALYZE | Settings → API tokens |
| Dynatrace **ingest token**: `ingestion:otlp:write` | component telemetry export | Settings → API tokens |
| DeepSeek API key | powers the demo agent's LLM turns | platform.deepseek.com (a few cents for the whole tutorial) |
| `kubectl` + a cluster + pullable registry **or** just Docker | deploy the component | Path A / Path B in the component README |
| `k6` | traffic driver + synthesized tests | grafana.com/docs/k6 |
| Python 3.11+, Node 20+ | the toolkit scripts | |

## 2. Clone and configure

```sh
git clone https://github.com/henrikrexed/AI-Performance-Testing.git
cd AI-Performance-Testing
cp .env.example .env
# edit .env — every key is documented inline
```

The complete key reference (also in [`.env.example`](../.env.example)):

| Key | Used by | Meaning |
|---|---|---|
| `DT_ENDPOINT` | DQL clients you point at your tenant | `https://<your-environment>.live.dynatrace.com` |
| `DT_API_TOKEN` | same | **read-only** token: `storage:spans:read`, `storage:logs:read` (+ `storage:user.events:read` only if you use RUM events) |
| `DT_TIMEFRAME` | workload-model | default extraction window, DQL syntax (`-3h`) |
| `BASE_URL` | generated k6 scripts | entry-point URL of the system under test |
| `K6_BINARY` | k6-synthesis | k6 binary name/path (optional; `node --check` fallback) |
| `WORKLOAD_OUT` | workload-model | output override for the worked example (optional) |
| `DT_OTLP_ENDPOINT` | tutorial component collector | `https://<your-environment>.live.dynatrace.com/api/v2/otlp` |
| `DT_OTLP_API_TOKEN` | tutorial component collector | **ingest** token, scope `ingestion:otlp:write` |
| `DEEPSEEK_API_KEY` | tutorial component app | your DeepSeek key |
| `DEEPSEEK_MODEL` / `DEEPSEEK_BASE_URL` | tutorial component app | defaults `deepseek/deepseek-chat`, `https://api.deepseek.com` |
| `RATE_PER_MIN` / `DURATION` / `TOOL_RATIO` | baseline driver defaults | `20` / `45m` / `0.30` |

Two Dynatrace tokens on purpose: one **writes** telemetry in, one **reads** it out. Keep
the read token out of anything that deploys.

## 3. Deploy the component and wire it to your backend

Full instructions: [`component/README.md`](component/README.md). Short version:

```sh
cd tutorial/component
# Path A (k8s): build+push image, create deepseek-api and dt-otlp secrets,
#               kubectl apply collector, deployment, service.
# Path B (docker): run the collector container, then the app container.
```

The component exports OpenTelemetry spans through a collector that:

- stamps `deployment.environment = ai-perf-tutorial` so your tutorial traffic is
  isolable in DQL no matter what else lives in the tenant, and
- **promotes k6 baggage `synthetic=true` to a queryable span attribute** — the EXECUTE
  stage's smoke gate depends on this, so don't bypass the collector.

**Verify** (smoke test in the component README): send one `tool` and one `chat` turn,
then in a Dynatrace Notebook:

```dql
fetch spans, from:-15m
| filter service.name == "crewai-deepseek-agent"
| summarize c = count(), by:{span.name}
| sort c desc
```

You should see `crewai-deepseek-agent/request`, `agent.turn`, `llm.call`, `chat`,
`execute_tool`, `finalize`, `message.sent`. No rows: check collector logs and the
`dt-otlp` secret first.

## 4. Generate the baseline window

This telemetry plays the role of "production traffic" the model will be extracted from:

```sh
cd tutorial/component/loadgen
BASE_URL=http://localhost:8080 RATE_PER_MIN=20 DURATION=45m TOOL_RATIO=0.30 \
  k6 run driver.js
```

- Open-model constant arrival rate (20 turns/min × 45 min ≈ 900 turns) — arrivals stay
  decoupled from LLM latency, which is exactly what SCOPE's pace/CoV math assumes.
- ~30% of turns use tools, ~70% are pure chat. SCOPE will rediscover this split on its
  own as two behavioral archetypes — a nice self-check of the method.
- **Write down the window's start and end timestamps.** Leave the service untouched
  during the window (no deploys, no restarts): a clean window is a SCOPE precondition.

## 5. SCOPE — turn telemetry into a workload model

Skill: [`skills/workload-model`](../skills/workload-model/SKILL.md)

### 5.1 Offline warm-up (no backend needed)

Run the worked example end to end — synthetic storefront extraction in, G0-validated
model + human-readable proposal out:

```sh
cd skills/workload-model
python3 scripts/build_example.py            # exit 0 iff G0 passes
cat out/example-frontend/scenario-proposal.md
```

You now have, in `out/example-frontend/`: `workload-model.json` (schema-valid, G0-passed)
and `scenario-proposal.md` (the VALIDATE gate's input). Everything deterministic — same
fixture in, same model out.

### 5.2 Live: the demo component's window

The skill's contract is **you (or your coding agent) run the DQL, the scripts consume the
rows** — no script in this toolkit talks to your tenant directly. Open
`skills/workload-model/SKILL.md`: it contains the full parameterized DQL pack
(`$entryService`, `$frontendServer`, `$timeframe`, …). For the demo component the
parameters resolve to `entryService = crewai-deepseek-agent` and your recorded window.

Run the pack in a Notebook (or any DQL client using `DT_ENDPOINT`/`DT_API_TOKEN`), save
each result as JSON rows, then drive the deterministic pipeline — exactly as
`build_example.py` does with the fixture:

- step 2a front-end discovery → `scripts/archetypes.py` (behavioral archetypes, the
  Agentic/Conversational split for this component)
- step 2c session signals → `utilities/session_stitch.py` / `utilities/rum_sessions.py`
  (see the sidebar below)
- shaping + emission → `scripts/shaping.py`, `scripts/emit.py`
- self-check → `python3 scripts/g0_gate.py <target>/workload-model.json <target>/scenario-proposal.md`

If you use a coding agent (Claude Code, opencode, Cursor, …), install the skills from
`skills/` into it and it can run this whole procedure for you — the SKILL.md files are
written for exactly that. The gates still protect you: nothing proceeds without G0
passing and (next stage) your explicit approval.

**G0 in one sentence:** a machine checklist (schema valid, ≤ 6 journeys, coverage ≥ 0.80,
Little's-Law-consistent rates, every step linked, correlate + cache profiles present)
that must pass before a human is even asked to look at the model.

## 6. VALIDATE — the human gate, in plain terms

Skill output: `scenario-proposal.md`. **Read it.** It states, in plain language:

- what window was analyzed and what was excluded (and why)
- the journeys to be tested: ids, weights, entrypoints, baseline p95s
- the arrival profile (stages, open/closed model, Little's-law check)
- the payload strategy (pools, PII stance, seeds)
- where the test will run (target environment, caps, abort thresholds)
- risks and unknowns

Your decision options: **approve as-is**, **adjust** (weights, rates, think-times), or
**reject** (wrong journeys → back to SCOPE with better data). Check that:

1. The journeys match how you believe the system is actually used.
2. Weights roughly match the traffic mix you saw in the window.
3. Rates are sane for the target environment (not production).
4. Nothing PII-shaped is in the payload plan.

If the proposal looks right, record the approval **in the model file** — SYNTHESIZE
refuses unapproved models (fail closed by design):

```jsonc
// workload-model.json
"status": {
  "revision": 1,
  "hash": "sha256:…",           // already present, leave as-is
  "approval": {
    "decision": "approved",
    "revision": 1,              // must equal status.revision
    "decisionBy": "your-name",
    "decisionAt": "2026-10-12T18:00:00Z"
  }
}
```

Why so ceremonial? Every later stage checks this record (revision-bound, hash-bound).
If the model changes, the approval is invalidated and a human — you — must look again.
That is the point: **no test executes against any environment without a person having
approved what will be tested.** Never skipped, never retro-active.

## 7. SYNTHESIZE — generate the k6 test

Skill: [`skills/k6-synthesis`](../skills/k6-synthesis/SKILL.md)

```sh
cd skills/k6-synthesis
node bin/synthesize.mjs <approved-workload-model.json> ../../loadtests/<target>/
```

Try it on the worked example first: feed it the **unapproved** model from 5.1 and watch
it refuse (that is the V1 gate working); then add the approval block and re-run. Output:

- `k6/<model>.js` — one k6 scenario per journey, arrival-profile-faithful executors,
  correlated request chains (extract → inject per `correlates` edge), fail-fast on null
  extracts, `synthetic=true` baggage on every request
- `k6/lib/*.js` — runtime helpers (chaining, think-times, pools)
- `payloads/*.json` — synthetic payload pools (Zipf-distributed where cache behavior
  matters, cardinality-sized per the model)
- V2a static checks run automatically; exit 0 iff they pass

**V2a in one sentence:** parseable k6 that actually matches the approved model —
ramp-downs end at zero, caps respected, correlation chain closed, pools committed —
checked before any run is allowed.

## 8. EXECUTE — smoke first, then the full run

Skill: [`skills/loadtest-run`](../skills/loadtest-run/SKILL.md)

Write a `run-config.json` (template: `skills/loadtest-run/fixtures/run-config.sample.json`,
rendered example: `fixtures/example-runs/…/run-report.md`). For the tutorial component:

```jsonc
{
  "modelRef": { "name": "agentapp", "revision": 1, "hash": "<from workload-model.json>" },
  "tool": "k6",
  "target": { "baseUrl": "http://localhost:8080", "environment": "tutorial", "allowlist": true },
  "caps":    { "maxRps": 2, "maxVus": 40, "maxDuration": "30m" },
  "abort":   { "errorRateGt": 0.05, "p95MsGt": 60000, "p99MsGt": 90000 },
  "syntheticTag": { "baggage": "synthetic=true" },
  "telemetry": { "environment": "ai-perf-tutorial", "timeframe": "-15m", "filter": "synthetic == true" }
}
```

(LLM turns are slow; generous latency aborts avoid killing an honest run. The
`telemetry.filter` relies on the baggage promotion done by the component's collector.)

```sh
cd skills/loadtest-run
python3 scripts/loadtest_run.py \
  --run-config <runs-dir>/run-config.json \
  --model      <approved workload-model.json> \
  --runs-root  <runs-dir> \
  --run-id     "$(date -u +%Y%m%dT%H%M%SZ)" \
  --v2a-passed
```

Strict order, fail closed:

1. **Smoke** — a small confirmation test (3–5 min, 10–20% scale, all journeys).
   Six pass criteria, notably: zero 5xx / broken routes, correlation works, journey mix
   within TVD ≤ 0.30, **at least one `synthetic == "true"` span visible in your backend**
   (proves the tagging pipeline end to end), `dropped_iterations == 0`.
   Any failure → full run refused. Diagnose, fix (structural → back to VALIDATE;
   parameters → iterate), re-smoke. Max 2 retries.
2. **V2b pre-flight** — allowlist (production refused outright), approval valid for the
   exact model hash, caps armed, V2a passed on this code.
3. **Full run** under a caps/abort supervisor — hard ceilings on RPS/VUs/duration,
   automatic abort + safe teardown on the first threshold breach.
4. Artifacts land in `runs/<timestamp>/`: pinned config, `smoke-result.json`,
   `run-report.json`, `run-report.md`.

## 9. ANALYZE — compare shapes, then decide

Skill: [`skills/baseline-diff`](../skills/baseline-diff/SKILL.md)

Inputs: the run artifacts + the baseline window from stage 4. Procedure (SKILL.md holds
the DQL pack): run the extraction queries for both windows, build `diff-input.json`, then:

```sh
cd skills/baseline-diff
python3 scripts/build_shape_diff.py \
  --input <runs-dir>/diff-input.json --out <runs-dir>/shape-diff.json
# exit 0 = accept · 10 = iterate · 20 = escalate · 2 = bad input / schema failure
```

Before trusting any diff, two prerequisites the skill enforces: the **synthetic probe**
(`synthetic == "true"` count must be > 0, else the comparison is meaningless) and
**sampling parity** (compare rates, not raw counts).

### Reading the verdict

`shape-diff.json` scores six dimensions against your model's tolerances — arrival
timing, per-step latency, fan-out, error delta, journey mix, cache hit ratio — plus the
mandatory R5 infrastructure cross-check (non-telemetry evidence: does the k6 summary
agree with what the backend saw?). The decision space:

- **accept** — every dimension inside tolerance. The synthetic load reproduced the
  production shape; ship it, keep the run as the new comparison point.
- **iterate** — misses classified as parameter-only (think-times, pacing, pool mixes):
  adjust parameters, re-run SYNTHESIZE→EXECUTE→ANALYZE. Maximum 3 iterations.
- **escalate** — structural mismatch (a journey missing, weights off, latency shape
  wrong): a human decides whether the model or the system changed. You get an
  `escalation-report.md` with the evidence.

For this component specifically, a healthy run shows: journey mix ≈ your `TOOL_RATIO`
(Agentic vs Conversational), arrival paces matching the driver's, and per-turn latency
profiles close to the baseline window at the same scale.

---

## Sidebar: dual-source session reconstruction, in plain terms

*"How do you know this load is realistic?"* — the question this answers. When the loop
models pacing (think-times between actions, session lengths), it refuses to guess where
it can measure. Two complementary signals, both native to Dynatrace Grail:

1. **RUM `user.sessions`** — what real browser/mobile users actually did: actions per
   session, navigation counts, durations, bounce. Rich but client-side: it never sees
   server spans. Queryable with a plain read token
   (`utilities/rum_sessions.py` analyzes the rows).
2. **OTel `session.id` on spans** — when a front-end propagates a session id as baggage
   onto **each action's entry span**, backend spans can be grouped by it, ordered in
   time, and the gaps between consecutive actions become **measured think-times**
   (`utilities/session_stitch.py`).

Merged, they cover each other's blind spots: RUM gives session shape and boundaries,
spans give server-side journeys, and the overlap validates both. Fidelity stays auditable:
the workload model records `rumSessionCoverage` and span sampling ratio side by side, so
"70% of sessions had server-side evidence" is a number you can point at, not a vibe.

One caution the toolkit takes seriously: **measure what a session signal actually tags
before trusting it.** An id that only ever appears on one leaf call (say, an ad fetch)
gives you that call's cadence, not journeys. The stitch skill's validity check
(`session.id → trace.id → entry-op`) exists to catch exactly this.

---

## 10. Teardown and next steps

```sh
# k8s path
kubectl delete ns agentapp
# docker path
docker rm -f crewai-deepseek-agent agent-collector
```

Then, on your own systems: install the skills from `skills/` into your coding agent,
point `DT_*` at your real tenant, and start the loop at SCOPE with a window of real
traffic. The VALIDATE gate is where you stay in charge.

## Troubleshooting

| Symptom | First check |
|---|---|
| No spans in Dynatrace | collector logs; `dt-otlp` secret values; OTLP endpoint ends in `/api/v2/otlp` |
| `llm.call`/`chat` spans missing | CrewAI signature drift — bump the pin in `app/requirements.txt` (component README note) |
| Smoke fails "synthetic span not visible" | baggage promotion: is traffic going through the provided collector? |
| Smoke fails journey-mix TVD | small-sample noise at 10% scale — check the mix over the whole smoke, not the tail |
| G0 fails on coverage | window too short/deploy-disturbed — regenerate a clean baseline window |
| 403 on DQL | token scopes (`storage:spans:read`); RUM events additionally need `storage:user.events:read` |
| DeepSeek 401 | `DEEPSEEK_API_KEY` actually reached the container/pod (`kubectl -n agentapp describe pod`) |
