# CrewAI + DeepSeek agent app — workload-model generalization test (ISI-5644)

Deploys a **CrewAI** agent app backed by **DeepSeek**, instrumented with OpenTelemetry →
Dynatrace **oat05854**, and drives sustained load so the `workload-model` skill can run
unchanged against a non-commerce, agentic workload and reproduce the **Agentic vs
Conversational** archetype split (see `skills/workload-model/GENERALIZATION.md`).

The app emits the same span tree the skill reconstructed live on `openclaw-gateway`:

```
crewai-deepseek-agent/request
  └─ agent.turn
       ├─ llm.call ─ chat                         (gen_ai semconv: system=deepseek, model, usage)
       ├─ execute_tool  (web_search | calculator) xN   ← terminal signal (tool-using turn only)
       ├─ finalize
       └─ message.sent
```

- **Tool-using turn** (`turn_type=tool`) → contains `execute_tool` spans → **Agentic** archetype.
- **Pure-LLM turn** (`turn_type=chat`) → no `execute_tool` spans → **Conversational** archetype.

The skill's `classify_by_terminal` keys on the `execute_tool` substring (`AGENTIC_TOOL_PATTERNS`)
and on the earliest-start root per trace (`crewai-deepseek-agent/request`) — both are emitted
deterministically here.

---

## Prerequisites (BLOCKER — needs secrets, not present in the ProxOps runner)

This runbook cannot complete from the current ProxOps runner. All three are owner-provided:

1. **A valid kubeconfig** for the cluster that feeds oat05854 (the memory-benchmark cluster,
   API `https://10.0.0.72:6443`). The API is reachable, but the only stored kubeconfig
   (`…/issues/b8031f35…/2026/07/28/…-memory-benchmark.kubeconfig`) is **stale** — its CA and
   client cert are both rejected (cert rotation since 2026-07-28). Refresh it.
2. **`DEEPSEEK_API_KEY`** — a DeepSeek API key (platform.deepseek.com). Deliver via Paperclip
   `adapterConfig.secretEnv`, never commit.
3. **DT oat05854 OTLP token** — *not a new secret*: the ISI-4089 `dt-otlp-token` already exists
   in the cluster (namespace `otel-demo`) and §3 copies it into `agentapp`. Only mint a new one
   if that secret is gone.

Container build also needs a registry the cluster can pull from (`REGISTRY` below). So the real
owner-provided blockers reduce to **(1) a valid cluster kubeconfig** and **(2) a DeepSeek API key**.

---

## 1. Layout

```
deploy/agentapp/app/        CrewAI app: FastAPI /request, OTel span tree, DeepSeek via LiteLLM
deploy/agentapp/k8s/        namespace, secrets template, dedicated collector, deployment, service
loadtests/agentapp-deepseek/ k6 open-model driver + prompt bank + scenario note
```

## 2. Build & push the image

```sh
export REGISTRY=<your-registry>/<project>     # cluster-pullable
cd deploy/agentapp/app
docker build -t "$REGISTRY/crewai-deepseek-agent:0.1.0" .
docker push "$REGISTRY/crewai-deepseek-agent:0.1.0"
# then set spec.template.spec.containers[0].image in k8s/deployment.yaml to that ref
sed -i "s#REGISTRY/crewai-deepseek-agent:0.1.0#$REGISTRY/crewai-deepseek-agent:0.1.0#" ../k8s/deployment.yaml
```

## 3. Create secrets (do NOT use secret.example.yaml with real values)

```sh
kubectl apply -f deploy/agentapp/k8s/namespace.yaml

# DeepSeek key (the one true new secret — owner-provided via Paperclip secretEnv):
kubectl -n agentapp create secret generic deepseek-api \
  --from-literal=apiKey="$DEEPSEEK_API_KEY"

# DT OTLP token: REUSE the existing ISI-4089 in-cluster secret rather than minting a new one.
# Copy it from the otel-demo namespace into agentapp (no new token required):
kubectl -n otel-demo get secret dt-otlp-token -o yaml \
  | sed 's/namespace: otel-demo/namespace: agentapp/' \
  | kubectl apply -n agentapp -f -
# (Only mint a new token — and use secret.example.yaml — if that secret is absent.)
```

## 4. Deploy

```sh
kubectl apply -f deploy/agentapp/k8s/collector.yaml
kubectl apply -f deploy/agentapp/k8s/deployment.yaml
kubectl apply -f deploy/agentapp/k8s/service.yaml
kubectl -n agentapp rollout status deploy/crewai-deepseek-agent
kubectl -n agentapp rollout status deploy/agent-collector
```

## 5. Smoke test (validate span shape BEFORE the load window)

```sh
kubectl -n agentapp port-forward svc/crewai-deepseek-agent 8080:80 &
# tool-using turn -> expect execute_tool spans
curl -s localhost:8080/request -H 'Content-Type: application/json' \
  -d '{"prompt":"What is 3 * (47 + 19)?","turn_type":"tool"}' | jq .
# pure-LLM turn -> no execute_tool spans
curl -s localhost:8080/request -H 'Content-Type: application/json' \
  -d '{"prompt":"In one sentence, what is observability?","turn_type":"chat"}' | jq .
```

Then confirm in oat05854 (DQL) that both turn types landed and the tool spans are named
`execute_tool`:

```dql
fetch spans, from:-15m
| filter service.name == "crewai-deepseek-agent"
| summarize c = count(), by:{span.name}
| sort c desc
```

Expect rows for `crewai-deepseek-agent/request`, `agent.turn`, `llm.call`, `chat`,
`execute_tool`, `finalize`, `message.sent`.

> If `llm.call`/`chat` spans are missing, CrewAI's `LLM.call` signature drifted from the pin —
> bump `crewai` within its minor and re-smoke. The `execute_tool` / `request` spans (the signals
> the skill strictly needs) do not depend on that signature.

## 6. Load window (clean, deploy-free, incident-free)

```sh
cd loadtests/agentapp-deepseek
BASE_URL=http://localhost:8080 RATE_PER_MIN=20 DURATION=45m TOOL_RATIO=0.30 \
  k6 run driver.js
```

~900 turns at ~30% tool / 70% chat — enough volume for pace/CoV and a per-turn baseline, with
both archetypes well-populated. Note the start/end timestamps; hand them to the Observability
Agent as the analysis window. Do NOT deploy or disturb the namespace during the window.

## 7. Hand-off

On a clean window with telemetry confirmed in oat05854, this unblocks the parent assignee
(Observability Agent, ISI-5630) to run the `workload-model` skill against
`service.name == crewai-deepseek-agent` for the window. Expected conclusion: an **Agentic
(tool-using turn)** vs **Conversational (pure-LLM turn)** split with weights ≈ the driver's
`TOOL_RATIO`, plus per-turn baseline, G0-passing.

## 8. Teardown

```sh
kubectl delete ns agentapp
```
