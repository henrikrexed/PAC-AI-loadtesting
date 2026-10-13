# Requirements

The engine and the renderer skills are deliberately dependency-light (see
[`engine.md`](engine.md) and [`skills-install.md`](skills-install.md)). This page covers
the **backend access** and **agent tooling** they sit on top of.

A `.env.example` at the repo root lists every variable; copy it to `.env` and fill it in.
**Never commit a real `.env`.**

---

## 1. Dynatrace tokens

The reference observability backend is **Dynatrace Grail (DQL)**. You need up to two
**separate** tokens — a read-only token for extraction/analysis, and (only if you ship the
generated load's telemetry back) an OTLP ingest token.

### Read-only DQL token (required)

A platform token used for SCOPE extraction and the ANALYZE shape-diff. Minimum scopes:

| Scope | Needed for |
|---|---|
| `storage:spans:read` | journeys, archetype split, baselines — **required** |
| `storage:logs:read` | access-log entrypoint cross-check — recommended |
| `storage:user.sessions:read` | RUM session shape (`skills/rum-sessions`) |
| `storage:user.events:read` | RUM **ordered user actions** / journey stitching (`skills/session-stitch`) — add this if you want RUM-driven journeys |

> `storage:user.events:read` is the one that is easy to miss: without it the RUM
> user-action stream returns `403` and session stitching falls back to spans only. The
> full per-safety-level scope matrix lives in the dtctl **Token Scopes** doc.

Set it in `.env` as `DT_ENDPOINT` + `DT_API_TOKEN`.

### OTLP ingest token (optional, separate)

Only needed if you send the generated load's telemetry (it carries
`baggage: synthetic=true`) back to your environment for the ANALYZE step. This is a
**different** token from the DQL one above.

- Scope: `ingestion:otlp:write`
- Endpoint: `https://<env>.live.dynatrace.com/api/v2/otlp`
- Set as `DT_OTLP_ENDPOINT` + `DT_OTLP_API_TOKEN`.

### Davis AI intelligence scopes (optional)

If you let `dtctl` use Dynatrace's built-in intelligence (Davis Analyzers / Davis CoPilot
— e.g. natural-language → DQL), the read token also needs the Davis scopes, e.g.
`davis:analyzers:read`, `davis:analyzers:execute`, and
`davis-copilot:conversations:execute` (plus `davis-copilot:nl2dql:execute` for NL→DQL).
See **Dynatrace intelligence**, below.

---

## 2. `dtctl` — the Dynatrace CLI

`dtctl` is the open-source Dynatrace platform CLI
([dynatrace-oss/dtctl](https://github.com/dynatrace-oss/dtctl)). It is how the
`workload-model` skill runs the DQL extraction that produces the engine's input.

**Install:**

```bash
# Homebrew (macOS / Linux)
brew install dynatrace-oss/tap/dtctl

# or a binary from the releases page:
#   https://github.com/dynatrace-oss/dtctl/releases/latest
# or from source:
git clone https://github.com/dynatrace-oss/dtctl.git && cd dtctl && make install
```

**Authenticate & set a context:**

```bash
# OAuth (recommended — browser SSO, no token to manage)
dtctl auth login --context my-env --environment "https://abc12345.apps.dynatrace.com"

# or token-based (use the read-only DQL token from §1)
dtctl config set-context my-env --environment "https://abc12345.apps.dynatrace.com" --token-ref my-token
dtctl config set-credentials my-token --token "YOUR_READONLY_DQL_TOKEN"

dtctl doctor                 # verify configuration / connectivity / auth
dtctl query "fetch spans | limit 1"
```

---

## 3. The `dtctl` agent skill

`dtctl` **ships its own Agent Skill** (`skills/dtctl/`, agentskills.io standard) that
teaches a coding agent how to drive it. Install it with the CLI — it auto-detects your
agent, or you can target one:

```bash
dtctl skills install                 # auto-detect the current agent
dtctl skills install --for claude    # Claude Code
dtctl skills install --for cursor    # Cursor
dtctl skills install --cross-client  # shared .agents/skills/ (any compatible agent)
dtctl skills install --global        # user-wide instead of project-local
dtctl skills status                  # check what's installed
dtctl skills install --list          # list supported agents
```

This is separate from installing **this repo's** `skills/*` (workload-model,
k6/jmeter/locust/gatling-synthesis, loadtest-run, baseline-diff, rum-sessions,
session-stitch) — see [`skills-install.md`](skills-install.md) for those.

---

## 4. Dynatrace intelligence (Davis AI)

Beyond raw DQL, `dtctl` exposes Dynatrace's **Davis AI** — **Analyzers** (predictive
analytics) and **Davis CoPilot** (generative assistance, including natural-language →
DQL). These are useful when a coding agent is drafting extraction queries.

- Access from the CLI via `dtctl exec copilot nl2dql "error logs from last hour"` and the
  related `exec`/analyzer commands.
- They require the Davis scopes on your token (see §1): `davis:analyzers:read`,
  `davis:analyzers:execute`, `davis-copilot:conversations:execute`, and the specific
  CoPilot sub-scopes (`davis-copilot:nl2dql:execute`, etc.).
- The dtctl Agent Skill (above) already documents these commands, so once it is installed
  your agent can discover and use them. Dynatrace also publishes a dedicated MCP server
  for its platform intelligence; enable it per your agent's MCP configuration if you
  prefer an MCP transport over the CLI.

> The toolkit never *requires* Davis AI — plain DQL is enough to run the whole loop. The
> intelligence layer only makes query authoring faster.

---

## 5. Everything else

- **Python 3.12** — only if you run the engine *from source* (binaries and the Docker
  image bundle their runtime). See [`engine.md`](engine.md).
- **A load tool** — `k6` (native fit), or JMeter / Locust / Gatling, depending on which
  renderer you use. The synthesis skills fall back to `node --check` for static
  validation when the tool binary is absent.
- **Node.js** — to run the renderer skills' test suites (`node --test`).
- **A coding agent** — Claude Code, opencode, Cursor, or any agentskills.io-compatible
  agent. See [`skills-install.md`](skills-install.md).
