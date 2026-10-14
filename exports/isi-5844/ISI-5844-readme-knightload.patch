From ffb76eca7c72f82cc823e2de8ea108ea55f99372 Mon Sep 17 00:00:00 2001
From: Henrik Rexed <henrikrexed@yahoo.fr>
Date: Wed, 14 Oct 2026 10:34:59 +0200
Subject: [PATCH] README: KnightLoad brand header + hardened Mermaid (loop +
 component diagram) + 4-step guided-flow narrative

- Add KnightLoad lockup header (light/dark <picture>, tagline 'Stop guessing.
  Load from reality.') matching the live Pages site; nav links to docs site.
- Harden the loop Mermaid: one edge per line, ASCII-only edge labels, explicit
  node captions (was a chained single-line flowchart with unicode labels that
  could fail to render).
- Add a component/architecture Mermaid diagram: agent skills -> deterministic
  engine (extract/V1 gate/render) -> target, backend as telemetry source.
- Realign narrative to the agreed 4-step guided flow (Propose+confirm/V1 ->
  Choose -> Generate -> opt-in Try it?) and the two-step onboarding model;
  exact init/install commands stay in docs/ until the engine CLI lands on main.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
---
 README.md | 116 ++++++++++++++++++++++++++++++++++++++++++++++--------
 1 file changed, 99 insertions(+), 17 deletions(-)

diff --git a/README.md b/README.md
index d4c3965..7a099ae 100644
--- a/README.md
+++ b/README.md
@@ -1,4 +1,26 @@
-# AI-Performance-Testing
+<p align="center">
+  <picture>
+    <source media="(prefers-color-scheme: dark)" srcset="website/static/img/logo-horizontal-onindigo.svg">
+    <img alt="KnightLoad" src="website/static/img/logo-horizontal-onlight.png" width="440">
+  </picture>
+</p>
+
+<p align="center">
+  <strong>KnightLoad</strong> — Stop guessing. Load from reality.<br>
+  <sub>An observability-driven, AI-agent-friendly toolkit for <strong>realistic</strong> load testing.</sub>
+</p>
+
+<p align="center">
+  <a href="https://henrikrexed.github.io/AI-Performance-Testing/">Docs site</a> ·
+  <a href="docs/methodology.md">Methodology</a> ·
+  <a href="docs/usage.md">Usage</a> ·
+  <a href="#quickstart">Quickstart</a> ·
+  <a href="https://www.youtube.com/@IsItObservable">IsItObservable</a>
+</p>
+
+---
+
+# KnightLoad — AI-Performance-Testing
 
 An observability-driven, AI-agent-friendly toolkit for **realistic** load testing —
 built around one idea: **your telemetry already knows what your real workload looks
@@ -13,8 +35,17 @@ benchmarking projects.
 
 ```mermaid
 flowchart LR
-    SCOPE -->|G0| VALIDATE -->|V1| SYNTHESIZE -->|V2a| EXECUTE -->|V2b| ANALYZE
-    ANALYZE -->|"V3 — iterate (parameter-only, ≤3×) or escalate"| SCOPE
+    SCOPE["SCOPE<br/>extract workload model"]
+    VALIDATE["VALIDATE<br/>human approves"]
+    SYNTHESIZE["SYNTHESIZE<br/>render runnable test"]
+    EXECUTE["EXECUTE<br/>confirm run, then full"]
+    ANALYZE["ANALYZE<br/>shape-diff vs baseline"]
+
+    SCOPE -->|G0| VALIDATE
+    VALIDATE -->|V1 gate| SYNTHESIZE
+    SYNTHESIZE -->|V2a| EXECUTE
+    EXECUTE -->|V2b| ANALYZE
+    ANALYZE -->|"V3: iterate or escalate"| SCOPE
 ```
 
 | Stage | What happens | Who owns it |
@@ -37,19 +68,79 @@ Why it is built this way:
   (Claude Code, opencode, Cursor, …); every consequential decision stays with a human
   or a deterministic gate.
 
+## How it works — the guided 4-step flow
+
+You give your coding agent a plain-language scope request
+(*"scope a load test for service `checkout` over the last 3 hours"*) and it drives four
+steps. **Nothing touches your system of record and no load is generated until you say
+so.**
+
+```mermaid
+flowchart TB
+    subgraph agent["Your coding agent - Claude Code / opencode / Cursor"]
+        skills["KnightLoad skills<br/>workload-model · k6/jmeter/gatling/locust synthesis<br/>baseline-diff · rum-sessions · session-stitch"]
+    end
+
+    subgraph engine["Engine - deterministic core"]
+        extract["extract, cluster, shape"]
+        gate["V1 human gate<br/>revision-bound approval"]
+        render["render runnable project"]
+    end
+
+    backend[("Observability backend<br/>Dynatrace Grail / DQL")]
+    target["Your target environment<br/>non-prod allowlist"]
+
+    backend -->|telemetry window| extract
+    extract --> gate
+    gate -->|approved model| render
+    render -->|"k6 / JMeter / Gatling / Locust (baggage: synthetic=true)"| target
+    skills -. invoke .-> engine
+```
+
+1. **Propose + confirm — the V1 human gate.** The engine extracts a workload model from a
+   clean telemetry window and shows you a readable, diff-able `scenario-proposal.md`:
+   journeys and weights, the open/closed arrival profile with its Little's-Law check,
+   payload strategy, where it will run, and the risks. You **confirm, edit, or reject**.
+   Approval is **bound to that model revision** — there is no agent self-approval, and any
+   later edit invalidates a prior approval. *Nothing is generated before you confirm.*
+2. **Choose output.** Pick the renderer — **k6** (default), **JMeter**, **Gatling**, or
+   **Locust** — one or several. Same approved model, different runnable project.
+3. **Generate.** The agent renders the full runnable test — scripts, feeders/data, config,
+   and a how-to-run — from the approved model. **Every request carries
+   `baggage: synthetic=true`** so the load is always distinguishable from real traffic.
+4. **"Try it?" — optional smoke run.** The agent offers a short, **opt-in** smoke run
+   against a non-production allowlist, under hard caps with automatic abort, and prints a
+   summary. Decline and run it yourself later — the generated project is complete either
+   way.
+
+> The gate in step 1 is the point of the whole method — keep it. The smoke run in step 4
+> is opt-in by design: the toolkit never fires load you did not ask for.
+
 ## Documentation
 
 | Doc | What it covers |
 |---|---|
 | [`docs/methodology.md`](docs/methodology.md) | The method: principles, the five-stage loop, every gate, dual-source session reconstruction, safety rules, fidelity caveats |
-| [`docs/usage.md`](docs/usage.md) | End-to-end usage — no-backend quickstart, running the loop against your own tenant, the full tutorial |
-| [`docs/engine.md`](docs/engine.md) | The workload-model engine: install per platform (binary / Docker / k8s / source) and its role in the loop |
+| [`docs/usage.md`](docs/usage.md) | End-to-end usage — no-backend quickstart, the guided 4-step flow, running the loop against your own tenant |
+| [`docs/engine.md`](docs/engine.md) | The workload-model engine: onboarding, the guided driver, install per platform (binary / Docker / k8s / source) |
 | [`docs/requirements.md`](docs/requirements.md) | Dynatrace tokens + **scopes**, `dtctl` + its agent skill, Davis AI, everything else |
 | [`docs/skills-install.md`](docs/skills-install.md) | Installing the skills into Claude Code, opencode, Cursor, or any agentskills.io agent |
 
 ## Quickstart
 
-**No backend, 10 minutes** — run the loop's first half on the bundled synthetic example:
+**Onboarding is two steps** — install the skills into your coding agent, then drive the
+guided flow:
+
+1. **Install the skills.** One-line install of the `workload-model` and
+   `k6`/`jmeter`/`gatling`/`locust` synthesis skills into your agent's skills path — see
+   [`docs/skills-install.md`](docs/skills-install.md) for the exact command per agent
+   (Claude Code, opencode, Cursor).
+2. **Drive the guided flow.** Ask your agent for a load test in plain language; it walks
+   the four steps above, stopping at the V1 gate for your approval. The full walkthrough
+   is in [`docs/engine.md`](docs/engine.md) and [`docs/usage.md`](docs/usage.md).
+
+**Try it now — no backend, ~10 minutes.** Run the loop's first half on the bundled
+synthetic example (no tokens, no live tenant):
 
 ```sh
 git clone https://github.com/henrikrexed/AI-Performance-Testing.git
@@ -88,23 +179,14 @@ k6 and run anywhere k6 runs.
 
 ## Installing
 
+- **Skills** — install `skills/*` onto your agent's skills path (Claude Code, opencode,
+  Cursor, or any agentskills.io agent): [`docs/skills-install.md`](docs/skills-install.md).
 - **Engine** — grab a released binary (linux/macOS/windows), the multi-arch Docker image
   `ghcr.io/henrikrexed/ai-performance-testing`, or run from source. All paths:
   [`docs/engine.md`](docs/engine.md).
-- **Skills** — copy `skills/*` onto your agent's skills path (Claude Code, opencode,
-  Cursor, or any agentskills.io agent): [`docs/skills-install.md`](docs/skills-install.md).
 - **Backend** — install `dtctl`, set a context, and mint the read-only DQL token:
   [`docs/requirements.md`](docs/requirements.md).
 
-## Using the skills with a coding agent
-
-The `skills/*/SKILL.md` files follow the agent-skill convention. Install them into your
-coding agent (Claude Code, opencode, Cursor, …), point `DT_ENDPOINT`/`DT_API_TOKEN` at
-your tenant, and ask for the loop: *"scope a load test for service X over the last 3
-hours"*. The agent runs the DQL and the deterministic scripts; you get the proposal at
-the VALIDATE gate. Nothing runs without your approval. Full walkthrough in
-[`docs/usage.md`](docs/usage.md).
-
 ## License
 
 [MIT](LICENSE) — © 2026 Henrik Rexed.
-- 
2.43.0

