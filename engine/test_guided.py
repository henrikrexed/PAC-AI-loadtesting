#!/usr/bin/env python3
"""Self-check for the guided 4-step driver + `init` onboarding (ISI-5839).

Runnable with plain `python3 engine/test_guided.py` (no framework, no fixtures beyond
the shipped synthetic extract). Asserts the three honesty-critical invariants:

  * `init` installs the repo's skills into a dest dir and verifies them.
  * the guided flow refuses to approve without a confirm (non-interactive, no --yes)
    and runs nothing downstream.
  * with --yes it binds a revision-locked approval (the V1 gate) and emits the project;
    the k6 renderer (when node is present) stamps baggage synthetic=true.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ENGINE = Path(__file__).resolve().parent
REPO = ENGINE.parent
EXTRACT = REPO / "examples" / "crewai-deepseek-agent" / "extract.json"
PY = sys.executable


def run(args, **kw):
    return subprocess.run([PY, str(ENGINE / "cli.py"), *args],
                          capture_output=True, text=True, cwd=REPO, **kw)


def test_init_installs_and_verifies():
    with tempfile.TemporaryDirectory() as d:
        dest = Path(d) / "skills"
        r = run(["init", "--dest", str(dest)])
        assert r.returncode == 0, f"init failed: {r.stderr}"
        assert (dest / "workload-model" / "SKILL.md").is_file(), "workload-model not installed"
        assert "verified" in r.stdout, "init did not report verification"
        # at least the SCOPE skill and one renderer land
        names = {p.name for p in dest.iterdir() if (p / "SKILL.md").exists()}
        assert "workload-model" in names and "k6-synthesis" in names, names
    print("  ✓ init installs + verifies skills")


def test_confirm_gate_fails_closed():
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "out"
        # no --yes, stdin is not a tty here -> must NOT approve, must exit non-zero
        r = run(["guided", "--extract", str(EXTRACT), "--out", str(out), "--mode", "agentic"],
                stdin=subprocess.DEVNULL)
        assert r.returncode == 3, f"expected refusal exit 3, got {r.returncode}: {r.stdout}{r.stderr}"
        model = json.loads((out / "workload-model.json").read_text())
        assert "approval" not in model.get("status", {}), "model was approved without a human gate!"
        state = json.loads((out / "guided-state.json").read_text())
        assert state["steps"]["2_confirm"]["approved"] is False
    print("  ✓ confirm gate fails closed without --yes (no self-approval)")


def test_guided_flow_end_to_end():
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "out"
        r = run(["guided", "--extract", str(EXTRACT), "--out", str(out),
                 "--mode", "agentic", "--yes", "--renderers", "k6"])
        assert r.returncode == 0, f"guided flow failed: {r.stdout}\n{r.stderr}"
        model = json.loads((out / "workload-model.json").read_text())
        appr = model["status"]["approval"]
        assert appr["decision"] == "approved"
        # approval is bound to the current revision and the canonical spec hash
        assert appr["revision"] == model["status"]["revision"]
        import importlib.util
        spec = importlib.util.spec_from_file_location("driver", ENGINE / "driver.py")
        driver = importlib.util.module_from_spec(spec); spec.loader.exec_module(driver)
        assert model["status"]["hash"] == driver.canonical_hash(model["spec"]), "hash not bound to spec"

        state = json.loads((out / "guided-state.json").read_text())
        assert state["steps"]["2_confirm"]["approved"] is True
        assert state["steps"]["5_try"]["ran"] is False, "smoke must be opt-in (no --try)"

        gen = state["steps"]["4_generate"][0]
        if shutil.which("node"):
            assert gen["status"] == "generated", f"k6 generate: {gen}"
            scripts = list((out / "k6").glob("*.js"))
            assert scripts, "no k6 script generated"
            body = scripts[0].read_text()
            assert "synthetic" in body and "true" in body, "generated script missing synthetic=true baggage"
            print("  ✓ guided flow: V1 gate bound + k6 generated with synthetic=true baggage")
        else:
            assert gen["status"] in ("toolchain-absent", "generated"), gen
            print("  ✓ guided flow: V1 gate bound (node absent — k6 generate reported honestly)")


if __name__ == "__main__":
    print("guided-driver self-check:")
    test_init_installs_and_verifies()
    test_confirm_gate_fails_closed()
    test_guided_flow_end_to_end()
    print("ALL PASS")
