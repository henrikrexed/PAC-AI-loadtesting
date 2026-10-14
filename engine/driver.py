#!/usr/bin/env python3
"""Guided 4-step driver + one-step onboarding for the workload-model engine.

This is the *conversational* face of the engine (methodology §2 loop). A coding
agent (or a human at a terminal) drives the engine through four discrete, gated
steps and the engine narrates each one:

  1. **Propose + confirm** — build the model from an extract and render a readable,
     diff-able summary; the operator confirms (the V1 human gate). Confirmation is
     **bound to the model revision** via a canonical hash of ``spec`` — exactly the
     binding the renderers fail-closed on. No ``--yes`` / no interactive *yes* ⇒
     nothing is approved and nothing downstream runs.
  2. **Choose output** — which renderer(s): k6 (default), jmeter, locust, gatling.
  3. **Generate** — render the runnable project (scripts + feeders + how-to-run) by
     invoking the renderer skill's headless entrypoint when its toolchain is present,
     otherwise printing the exact command (honest about what it did vs. would do).
  4. **Try it?** — *opt-in only* (``--try``): a few seconds of a real smoke run, or
     the exact command when the load tool is absent.

It also provides ``init`` — single-entry onboarding that installs the repo's skills
into a coding agent's skills directory (default ``~/.claude/skills``, matching
``docs/skills-install.md``) and verifies them, so there is no manual symlinking.

Honesty invariants (methodology §3.2 / §6): the human-confirm gate is mandatory and
revision-bound; generated requests carry ``baggage: synthetic=true`` (enforced by the
renderer); the smoke run is opt-in. This module never weakens any of them.

Pure standard library — ships unchanged inside the PyInstaller binary and the Docker
image.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# shared: the revision-bound approval (the §3.2 V1 gate, same math as
# skills/workload-model/scripts/approve_model.py so the renderers accept it)
# ---------------------------------------------------------------------------

def canonical_hash(spec: dict) -> str:
    blob = json.dumps(spec, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(blob).hexdigest()


def bind_approval(model: dict, by: str, at: str) -> tuple[int, str]:
    """Stamp a revision-bound approval onto the model in place. Returns (rev, hash)."""
    rev = model.get("status", {}).get("revision")
    if not isinstance(rev, int):
        raise ValueError("model has no integer status.revision — cannot bind approval")
    h = canonical_hash(model["spec"])
    model.setdefault("status", {})["hash"] = h
    model["status"]["approval"] = {
        "decision": "approved",
        "revision": rev,
        "decisionBy": by,
        "decisionAt": at,
        "note": (
            f"V1 human gate: operator approved the proposed model (rev {rev}, {h[:19]}…). "
            "Approval is bound to this revision — any later edit invalidates it and the "
            "renderers fail closed. Non-production; extraction-only (methodology §3.2)."
        ),
    }
    return rev, h


# ---------------------------------------------------------------------------
# skills discovery / onboarding (`init`)
# ---------------------------------------------------------------------------

# Install targets in preference order; first existing parent wins unless --dest given.
# Matches docs/skills-install.md (Claude Code user-wide is the default).
DEFAULT_DEST = Path.home() / ".claude" / "skills"


def _repo_skills_dir(explicit: str | None) -> Path | None:
    """Locate the repo's skills/ directory (bundled source), or None if not found."""
    if explicit:
        p = Path(explicit).expanduser()
        return p if (p / "workload-model" / "SKILL.md").exists() else None
    here = Path(__file__).resolve().parent  # <repo>/engine
    for cand in (here.parent / "skills", Path.cwd() / "skills"):
        if (cand / "workload-model" / "SKILL.md").exists():
            return cand
    return None


def _iter_skills(src: Path):
    for d in sorted(src.iterdir()):
        if d.is_dir() and (d / "SKILL.md").exists():
            yield d


def cmd_init(args) -> int:
    src = _repo_skills_dir(args.from_dir)
    if src is None:
        print(
            "init: could not find the repo's skills/ directory next to the engine.\n"
            "You are likely running the standalone binary. Install from a checkout:\n\n"
            "  git clone https://github.com/henrikrexed/AI-Performance-Testing.git\n"
            "  cd AI-Performance-Testing\n"
            "  python3 engine/cli.py init\n\n"
            "or run the one-liner:  curl -fsSL "
            "https://raw.githubusercontent.com/henrikrexed/AI-Performance-Testing/main/install.sh | sh",
            file=sys.stderr,
        )
        return 2

    dest = Path(args.dest).expanduser() if args.dest else DEFAULT_DEST
    dest.mkdir(parents=True, exist_ok=True)

    installed = []
    for skill in _iter_skills(src):
        target = dest / skill.name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(skill, target, ignore=shutil.ignore_patterns(
            "node_modules", "__pycache__", ".pytest_cache", "*.pyc"))
        installed.append(skill.name)

    # verify: every installed skill has a readable SKILL.md at the destination
    missing = [n for n in installed if not (dest / n / "SKILL.md").is_file()]
    print(f"init: installed {len(installed)} skill(s) into {dest}")
    for n in installed:
        print(f"  ✓ {n}")
    if missing:
        print(f"init: VERIFY FAILED — missing SKILL.md for: {', '.join(missing)}", file=sys.stderr)
        return 1

    print(
        "\ninit: verified. Next, drive the engine through the guided flow:\n\n"
        "  python3 engine/cli.py guided \\\n"
        "      --extract examples/crewai-deepseek-agent/extract.json \\\n"
        "      --out ./out --mode agentic\n\n"
        "or just ask your coding agent: "
        '"use the workload-model skill to build a model from the example extract".'
    )
    return 0


# ---------------------------------------------------------------------------
# renderer registry — SYNTHESIZE step 3 (headless entrypoints)
# ---------------------------------------------------------------------------

def _find_skill(name: str) -> Path | None:
    """Find an installed or bundled renderer skill directory by name."""
    cands = [
        DEFAULT_DEST / name,
        Path.home() / ".agents" / "skills" / name,
        Path.cwd() / ".claude" / "skills" / name,
        Path.cwd() / ".agents" / "skills" / name,
    ]
    src = _repo_skills_dir(None)
    if src:
        cands.append(src / name)
    for c in cands:
        if (c / "SKILL.md").exists():
            return c
    return None


def _gen_k6(skill: Path, model_path: Path, out_dir: Path) -> dict:
    """Invoke the k6-synthesis headless entrypoint if node is present."""
    entry = skill / "bin" / "synthesize.mjs"
    if not entry.exists():
        return {"renderer": "k6", "status": "skill-missing-entrypoint", "command": None}
    cmd = ["node", str(entry), str(model_path), str(out_dir)]
    if shutil.which("node") is None:
        return {
            "renderer": "k6", "status": "toolchain-absent",
            "command": " ".join(cmd),
            "detail": "node not found — run the command above where node is available",
        }
    proc = subprocess.run(cmd, capture_output=True, text=True)
    sys.stdout.write(proc.stdout)
    if proc.stderr:
        sys.stderr.write(proc.stderr)
    script = out_dir / "k6" / f"{model_path.stem.replace('workload-model', '') or 'model'}.js"
    # the generator names the script after the model; just report the k6 dir
    return {
        "renderer": "k6",
        "status": "generated" if proc.returncode == 0 else "failed",
        "exitCode": proc.returncode,
        "outDir": str(out_dir / "k6"),
        "command": " ".join(cmd),
    }


# renderer -> (handler, headless?). Only k6 ships a headless entry in this repo today.
RENDERERS = {
    "k6": _gen_k6,
    "jmeter": None,
    "locust": None,
    "gatling": None,
}


def _generate(renderers: list[str], model_path: Path, out_dir: Path) -> list[dict]:
    results = []
    for r in renderers:
        handler = RENDERERS.get(r)
        skill = _find_skill(f"{r}-synthesis")
        if skill is None:
            results.append({
                "renderer": r, "status": "skill-not-installed",
                "detail": f"{r}-synthesis not found — run `engine/cli.py init` or install it, "
                          "then hand the approved model to the skill.",
            })
            continue
        if handler is None:
            results.append({
                "renderer": r, "status": "manual",
                "detail": f"Hand the approved model to the {r}-synthesis skill "
                          f"({skill}) — see its SKILL.md for the entrypoint.",
            })
            continue
        results.append(handler(skill, model_path, out_dir))
    return results


# ---------------------------------------------------------------------------
# readable summary — step 1 render
# ---------------------------------------------------------------------------

def render_summary(model: dict) -> str:
    md = model["metadata"]
    s = model["spec"]
    ap = s["arrivalProfile"]
    ll = ap.get("littlesLawCheck") or {}
    lines = [
        f"PROPOSED MODEL  {md['name']}  (rev {model['status']['revision']})",
        f"  target service : {md.get('targetService', md['name'])}  env={md.get('environment')}",
        f"  arrival        : {ap.get('model')}  stages={len(ap.get('stages', []))}"
        + (f"  Little's-Law ratio={ll.get('ratio')}" if ll else ""),
        f"  coverage       : {s.get('coverage')}",
        f"  caps           : {json.dumps(s.get('caps', {}))}",
        "  journeys:",
    ]
    for j in s["journeys"]:
        lines.append(
            f"    - {j['id']:<16} weight={j['weight']:<8} "
            f"entry={j['entrypoint']}  steps={len(j['steps'])}  evidence={j['evidenceSource']}"
        )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# the guided flow
# ---------------------------------------------------------------------------

def _confirm(auto_yes: bool) -> bool:
    if auto_yes:
        print("confirm: --yes given — approving the proposed model.")
        return True
    if not sys.stdin.isatty():
        print(
            "confirm: no --yes and not an interactive terminal ⇒ NOT approved. "
            "The V1 human gate is mandatory; re-run with --yes to confirm, or approve "
            "interactively. Nothing downstream will run.",
            file=sys.stderr,
        )
        return False
    try:
        ans = input("\nApprove this model and proceed to generate? [y/N] ").strip().lower()
    except EOFError:
        return False
    return ans in ("y", "yes")


def run_guided(args, build_fn) -> int:
    """Drive the 4-step flow. build_fn is engine.cli.build (extract, mode) -> (model, proposal)."""
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    state = {"steps": {}, "honesty": {
        "humanConfirmGate": "revision-bound (sec §3.2)",
        "syntheticBaggage": "enforced by renderer",
        "smokeRun": "opt-in (--try)",
    }}

    # --- Step 1: propose ---
    extract = json.loads(Path(args.extract).read_text())
    model, proposal = build_fn(extract, args.mode)
    model_path = out_dir / "workload-model.json"
    model_path.write_text(json.dumps(model, indent=2) + "\n")
    (out_dir / "scenario-proposal.md").write_text(proposal)
    print("=" * 72)
    print("STEP 1/4 — PROPOSE  (engine built the model; read & confirm)")
    print("=" * 72)
    print(render_summary(model))
    print(f"\n  full proposal → {out_dir / 'scenario-proposal.md'}")
    print(f"  model        → {model_path}")
    state["steps"]["1_propose"] = {
        "model": str(model_path), "proposal": str(out_dir / "scenario-proposal.md"),
        "revision": model["status"]["revision"],
    }

    # --- Step 1 gate: confirm (the V1 human gate, revision-bound) ---
    if not _confirm(args.yes):
        state["steps"]["2_confirm"] = {"approved": False}
        (out_dir / "guided-state.json").write_text(json.dumps(state, indent=2) + "\n")
        print("\nNot approved — stopping before SYNTHESIZE. No requests will be generated.")
        return 3
    rev, h = bind_approval(model, by=args.by, at=args.at)
    model_path.write_text(json.dumps(model, indent=2) + "\n")
    print(f"\nSTEP 1 gate ✓ — approved rev {rev}, bound to {h[:19]}… (renderers fail closed without this).")
    state["steps"]["2_confirm"] = {"approved": True, "revision": rev, "hash": h, "by": args.by}

    # --- Step 2: choose output ---
    renderers = [r.strip() for r in args.renderers.split(",") if r.strip()]
    unknown = [r for r in renderers if r not in RENDERERS]
    if unknown:
        print(f"error: unknown renderer(s): {', '.join(unknown)}; choose from {', '.join(RENDERERS)}",
              file=sys.stderr)
        return 2
    print("\n" + "=" * 72)
    print(f"STEP 2/4 — CHOOSE OUTPUT  →  {', '.join(renderers)}")
    print("=" * 72)
    state["steps"]["3_choose"] = {"renderers": renderers}

    # --- Step 3: generate ---
    print("\n" + "=" * 72)
    print("STEP 3/4 — GENERATE  (approved model → runnable project)")
    print("=" * 72)
    gen = _generate(renderers, model_path, out_dir)
    for g in gen:
        detail = g.get("detail") or g.get("outDir") or g.get("command") or ""
        print(f"  {g['renderer']:<8} {g['status']:<22} {detail}")
    state["steps"]["4_generate"] = gen

    # --- Step 4: try it (opt-in) ---
    print("\n" + "=" * 72)
    print("STEP 4/4 — TRY IT?  (opt-in smoke run)")
    print("=" * 72)
    if not args.try_run:
        print("  skipped — opt-in only. Re-run with --try for a few seconds of a real k6 smoke,")
        print("  or hand the generated project to the loadtest-run skill (allowlist + hard caps + auto-abort).")
        state["steps"]["5_try"] = {"ran": False, "reason": "opt-in (--try not given)"}
    else:
        state["steps"]["5_try"] = _smoke(out_dir)

    (out_dir / "guided-state.json").write_text(json.dumps(state, indent=2) + "\n")
    print(f"\nguided flow complete → {out_dir / 'guided-state.json'}")
    return 0


def _smoke(out_dir: Path) -> dict:
    """Opt-in: a few seconds of a real k6 run against the generated script, if k6 is present."""
    k6_dir = out_dir / "k6"
    scripts = sorted(k6_dir.glob("*.js")) if k6_dir.exists() else []
    if not scripts:
        print("  no generated k6 script found — generate with the k6 renderer first.")
        return {"ran": False, "reason": "no k6 script"}
    script = scripts[0]
    cmd = ["k6", "run", "--duration", "5s", "--vus", "1", str(script)]
    if shutil.which("k6") is None:
        print(f"  k6 not installed — would run:  {' '.join(cmd)}")
        print("  (every request carries baggage synthetic=true — see the generated script)")
        return {"ran": False, "reason": "k6 absent", "command": " ".join(cmd)}
    print(f"  running:  {' '.join(cmd)}")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    sys.stdout.write(proc.stdout[-2000:])
    return {"ran": True, "exitCode": proc.returncode, "command": " ".join(cmd), "script": str(script)}
