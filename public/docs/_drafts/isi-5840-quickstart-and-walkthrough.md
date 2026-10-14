<!--
DRAFT — DO NOT PUBLISH YET.
ISI-5840 (Docs: 2-command quickstart + 4-step guided-flow walkthrough).
BLOCKED BY ISI-5839 (Engine: guided 4-step driver + `init`/`install.sh` onboarding).

This file is the ready-to-merge copy AND the command-surface contract with the engine
author. Every command below is a PROPOSAL until ISI-5839 lands the real `init`,
`install.sh`, and 4-step driver. The instant the engine confirms the surface (names,
flags, install paths, printed next-prompt), the two sections below drop verbatim into
`skills-install.md`, `engine.md`, `requirements.md`, and `usage.md`, and this draft is
deleted. Do NOT merge any command here into the public docs until it is real and
reproduced on a clean box.
-->

# ISI-5840 — quickstart + guided-flow walkthrough (draft + contract)

## A. Command-surface contract (needs Engine / ISI-5839 confirmation)

Docs will document exactly the following surface. If the engine lands anything
differently, ping ISI-5840 and I will reconcile the copy — the point of this contract is
that docs, the engine, and the Content Writer demo (ISI-5841) all say the same words.

| # | What docs will promise | Engine must provide (ISI-5839) | Confirmed? |
|---|---|---|---|
| C1 | `curl -fsSL <raw install.sh URL> \| sh` installs all skills in one line | `install.sh` at repo root, fetch-and-run, idempotent, non-interactive | ☐ |
| C2 | `python engine/cli.py init` is the no-curl equivalent (from a clone) | `init` subcommand on `engine/cli.py` | ☐ |
| C3 | `init` installs `workload-model` + `k6`/`jmeter`/`gatling`/`locust`-synthesis (and `loadtest-run`, `baseline-diff`, `rum-sessions`, `session-stitch`?) into the agent skills dir | exact skill set `init` installs | ☐ |
| C4 | Default install path is `~/.claude/skills` (user-wide); flag for project-local `.claude/skills` and cross-client `.agents/skills` | `init` flags, e.g. `--project` / `--cross-client` / `--for <agent>` | ☐ |
| C5 | `init` **verifies** the install and **prints the next prompt** to paste to the agent | verify step + the exact printed prompt string | ☐ |
| C6 | Command 2 of the quickstart is that first prompt, which kicks off the guided loop | the driver reacts to a natural-language scope request | ☐ |
| C7 | Step names in the 4-step flow: **Propose+confirm (V1)** → **Choose output** → **Generate** → **"Try it?" (opt-in smoke)** | driver step labels + prompts match these | ☐ |
| C8 | The confirm step **binds the approved revision** (no self-approval; edits invalidate) | V1 gate wired to `approve_model` / revision binding (ISI-5723) | ☐ |
| C9 | Every generated request carries `baggage: synthetic=true`; the smoke run is **opt-in** | honesty invariants preserved in the driver | ☐ |

Open questions for the engine author (answer on ISI-5840 or ISI-5839):
1. Is the onboarding entry point `python engine/cli.py init`, or a thinner wrapper
   (`workload-engine init` on the released binary)? Docs should name whichever is real.
2. Exact `install.sh` raw URL / branch it pins (`main`? a tag?).
3. Does `init` print a single copy-paste prompt, or a short menu? Docs mirror that.
4. Does the 4-step driver run as a skill the agent invokes, or as `engine/cli.py`
   subcommands the agent shells out to? This changes whether the walkthrough shows
   prompts (agent-driven) or commands (cli-driven).

---

## B. Draft copy — `skills-install.md` quickstart (replaces the manual `cp -r` steps)

> Lands as a new top section in `skills-install.md`; the per-agent `cp -r` blocks stay
> below it as the **manual / advanced** path.

### Quickstart — two commands

```bash
# 1. install the toolkit's skills into your coding agent (one line, no manual symlinks)
curl -fsSL https://raw.githubusercontent.com/henrikrexed/AI-Performance-Testing/main/install.sh | sh
```

`install.sh` fetches the repo and runs `python engine/cli.py init`, which copies the
`workload-model` and `k6` / `jmeter` / `gatling` / `locust` synthesis skills into
`~/.claude/skills`, verifies they load, and prints the prompt to start with. From a clone
you can skip the curl and run `init` directly:

```bash
git clone https://github.com/henrikrexed/AI-Performance-Testing.git
cd AI-Performance-Testing
python engine/cli.py init            # add --project for .claude/skills, --cross-client for .agents/skills
```

```bash
# 2. paste the printed prompt to your agent to start the guided loop, e.g.
#    "Scope a load test for service checkout over the last 3 hours."
```

That is the whole onboarding. The agent now has the skills and will walk the four-step
guided flow (see [`engine.md`](engine.md) §"Guided flow"). The manual per-agent copy
steps below remain for CI, locked-down boxes, or non-Claude agents.

---

## C. Draft copy — `engine.md` §"Guided flow" (the 4-step walkthrough)

> Lands as a new section in `engine.md` between §1 Install and §2 Use, and is mirrored as
> the numbered list in `usage.md` §2. Wording kept in lockstep with the Content Writer
> demo script (ISI-5841) so docs and the video match.

### The guided flow — four steps

After `init`, give the agent a plain-language scope request and it drives these four
steps. Nothing touches your system of record and no load is generated until you say so.

1. **Propose + confirm (the V1 human gate).** The engine extracts a workload model from a
   clean telemetry window and the agent shows you a readable, diff-able
   `scenario-proposal.md` — journeys and weights, the open/closed arrival profile with its
   Little's-Law check, payload strategy, where it will run, and the risks. You **confirm,
   edit, or reject**. Approval is **bound to that model revision** — there is no agent
   self-approval, and any later edit invalidates a prior approval. *Nothing is generated
   before you confirm.*
2. **Choose output.** Pick the renderer: **k6** (default), **JMeter**, **Gatling**, or
   **Locust** — one or several. Same approved model, different runnable project.
3. **Generate.** The agent renders the full runnable test — scripts, feeders/data, config,
   and a how-to-run — from the approved model. **Every request carries
   `baggage: synthetic=true`** so the load is always distinguishable from real traffic.
4. **"Try it?" — optional smoke run.** The agent offers a short, **opt-in** smoke run
   against a non-production allowlist, under hard caps with automatic abort, and prints a
   summary. You can decline and run it yourself later; the generated project is complete
   either way.

> The gate in step 1 is the point of the whole method — keep it. The smoke run in step 4
> is opt-in by design: the toolkit never fires load you did not ask for.

---

## D. `requirements.md` touch

Add one line under §5 "Everything else" (or a new §0) pointing at the quickstart so the
reading order is: *two-command quickstart → this page only if you need backend tokens*.
No command changes in `requirements.md` itself — the `dtctl` + token setup is unchanged;
it just stops being step 1 of onboarding.

---

## E. Honesty invariants (must survive the rewrite — verbatim checklist)

- `synthetic=true` baggage on every generated request (step 3). ✔ kept
- V1 human-confirm gate, revision-bound, no self-approval (step 1). ✔ kept
- Smoke run is opt-in (step 4). ✔ kept
- No fabricated commands: nothing in §B/§C ships to public docs until reproduced on a
  clean box against the real ISI-5839 engine.
