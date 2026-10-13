# Installing the skills into a coding agent

The `skills/*` directories follow the [agentskills.io](https://agentskills.io)
convention: each is a directory with a `SKILL.md` (the instructions the agent loads) plus
deterministic scripts and tests. An agent "installs" a skill by having its directory on
the agent's skills search path.

Skills in this repo:

| Skill | Stage | What it does |
|---|---|---|
| `workload-model` | SCOPE | telemetry extract → G0-gated `workload-model.json` + proposal |
| `k6-synthesis` · `jmeter-synthesis` · `locust-synthesis` · `gatling-synthesis` | SYNTHESIZE | approved model → runnable test (one `renderer-kit` interface) |
| `loadtest-run` | EXECUTE | scoped run: allowlist, hard caps, auto-abort, run report |
| `baseline-diff` | ANALYZE | DQL shape-diff vs. baseline, accept / iterate / escalate |
| `rum-sessions` · `session-stitch` | SCOPE (RUM) | RUM session shape & ordered-action reconstruction |

Each coding agent discovers skills from a conventional directory. Install = copy (or
symlink) the skill directory there. Paths below follow the same standard the Dynatrace
CLI uses (`dtctl skills install --list`).

```bash
git clone https://github.com/henrikrexed/AI-Performance-Testing.git
cd AI-Performance-Testing
```

## Claude Code

```bash
# project-local (this project only)
mkdir -p .claude/skills
cp -r skills/* .claude/skills/

# or user-wide (all projects)
mkdir -p ~/.claude/skills
cp -r skills/* ~/.claude/skills/
```

Claude Code auto-discovers every `~/.claude/skills/<name>/SKILL.md` (or the project-local
`.claude/skills/`) and loads a skill when the task matches its description.

## opencode

```bash
# project-local
mkdir -p .opencode/skills
cp -r skills/* .opencode/skills/

# or user-wide
cp -r skills/* "$HOME/.config/opencode/skills/"   # --global location
```

## Cursor

```bash
# project-local (Cursor discovers project skills, not user-global ones)
mkdir -p .cursor/skills
cp -r skills/* .cursor/skills/
```

## Any agentskills.io-compatible agent (cross-client)

The portable location — discovered by **any** compatible agent (Claude Code, opencode,
Cursor, Copilot, Kiro, Junie, …) without per-agent copying:

```bash
# project-local
mkdir -p .agents/skills
cp -r skills/* .agents/skills/

# or user-wide
mkdir -p ~/.agents/skills
cp -r skills/* ~/.agents/skills/
```

## Verify

Ask your agent to run the bundled worked example — if the skill is installed, it will
pick it up by name:

> "Use the workload-model skill to build a model from
> `skills/workload-model/fixtures/example_extract.json`."

Or run a skill's tests directly to confirm the files are intact:

```bash
( cd skills/workload-model && python3 -m pytest -q )        # 68 passed
( cd skills/k6-synthesis   && node --test test/*.test.mjs ) # 51 passed
```

> Installing **these** skills is separate from installing the **`dtctl`** agent skill
> (which ships with the CLI via `dtctl skills install`). See
> [`requirements.md`](requirements.md) §3.
