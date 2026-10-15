"""env_probe.py tests (ISI-5928) — the fail-closed environment probe.

Uses a fake `dtctl` shim on PATH to exercise every branch: missing binary, broken
auth, service discovery (unpinned), unknown service, and the happy path that emits
the provenance template the extract adapter must copy.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
PROBE = SCRIPTS / "env_probe.py"


def _run(argv: list[str], env: dict | None = None):
    return subprocess.run([sys.executable, str(PROBE), *argv],
                          capture_output=True, text=True, env=env, timeout=60)


def _fake_dtctl_dir(tmp_path: Path, *, stdout: str = "", stderr: str = "", rc: int = 0) -> Path:
    d = tmp_path / "bin"
    d.mkdir(exist_ok=True)
    shim = d / "dtctl"
    out_b64 = __import__("base64").b64encode(stdout.encode()).decode()
    err_b64 = __import__("base64").b64encode(stderr.encode()).decode()
    shim.write_text(
        "#!/bin/sh\n"
        f"echo {out_b64} | base64 -d\n"
        f"echo {err_b64} | base64 -d >&2\n"
        f'exit {rc}\n'
    )
    shim.chmod(0o755)
    return d


def _records_payload(records: list[dict]) -> str:
    return json.dumps({"records": records})


def _env_with(bin_dir: Path | None) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("DT_")}
    env["PATH"] = f"{bin_dir}:{env.get('PATH', '/usr/bin:/bin')}" if bin_dir else "/usr/bin:/bin"
    return env


def test_fails_closed_when_dtctl_missing(tmp_path):
    r = _run(["--context", "t"], env=_env_with(None))
    assert r.returncode == 1
    assert "dtctl not found" in r.stderr
    assert "will NOT fall back" in r.stderr


def test_fails_closed_when_backend_unauthenticated(tmp_path):
    d = _fake_dtctl_dir(tmp_path, stdout='{"error": "401 unauthorized"}')
    r = _run(["--context", "t", "--service", "frontend"], env=_env_with(d))
    assert r.returncode == 1
    assert "not reachable/authenticated" in r.stderr
    assert "dtctl auth login" in r.stderr  # actionable guidance


def test_discovery_mode_exits_2_when_service_unpinned(tmp_path):
    d = _fake_dtctl_dir(tmp_path, stdout=_records_payload(
        [{"entryService": "frontend", "traces": 42}, {"entryService": "cart", "traces": 7}]))
    r = _run(["--context", "t"], env=_env_with(d))
    assert r.returncode == 2
    assert "frontend" in r.stdout and "frontend" in r.stdout  # discovery table printed
    assert "no silent target choice" in r.stderr


def test_fails_closed_when_service_not_observed(tmp_path):
    d = _fake_dtctl_dir(tmp_path, stdout=_records_payload(
        [{"entryService": "frontend", "traces": 42}]))
    r = _run(["--context", "t", "--service", "nope"], env=_env_with(d))
    assert r.returncode == 1
    assert "no root spans" in r.stderr
    assert "frontend (42)" in r.stderr  # shows what WAS observed


def test_happy_path_emits_provenance_template(tmp_path):
    d = _fake_dtctl_dir(tmp_path, stdout=_records_payload(
        [{"entryService": "frontend", "traces": 1337}]))
    r = _run(["--context", "my-tenant", "--service", "frontend"], env=_env_with(d))
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)
    assert out["ok"] is True
    assert out["service"] == "frontend" and out["rootTraces"] == 1337
    tpl = out["provenanceTemplate"]
    assert tpl["kind"] == "extracted"
    assert tpl["tenant"] == "my-tenant"
    assert "my-tenant" in tpl["extractedFrom"]
    assert tpl["dqlRunLive"] is True
