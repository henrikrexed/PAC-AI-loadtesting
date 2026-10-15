"""CLI fail-closed / demo opt-in / provenance threading tests (ISI-5928).

The silent-example-fallback repro as a regression test: `workload-engine --out X` with no
`--extract` and no `--demo` must exit 2 with guidance — never produce a model from the
bundled synthetic fixture. `--demo` works but stamps demo-sample, and a real extract's
own provenance wins over `--demo`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

import cli  # noqa: E402

FIXTURE = SCRIPTS.parent / "fixtures" / "example_extract.json"


def test_no_extract_no_demo_fails_closed(tmp_path, capsys):
    rc = cli.main(["--out", str(tmp_path / "o")])
    assert rc == 2
    err = capsys.readouterr().err
    assert "fail-closed" in err
    assert "--demo" in err and "env_probe.py" in err  # actionable guidance
    assert not (tmp_path / "o" / "workload-model.json").exists()  # nothing was silently built


def test_demo_opt_in_stamps_demo_sample(tmp_path, capsys):
    rc = cli.main(["--demo", "--out", str(tmp_path / "o")])
    assert rc == 0, capsys.readouterr().out
    m = json.loads((tmp_path / "o" / "workload-model.json").read_text())
    prov = m["metadata"]["source"]["provenance"]
    assert prov["kind"] == "demo-sample"
    assert "--demo" in prov["note"]
    proposal = (tmp_path / "o" / "scenario-proposal.md").read_text()
    assert "DEMO SAMPLE" in proposal and "NOT REAL TELEMETRY" in proposal
    # the gate output must record the honest dql-live n/a, not a live claim
    out = capsys.readouterr().out
    assert "no live-DQL claim" in out


def test_extract_without_provenance_fails_g0(tmp_path):
    fx = json.loads(FIXTURE.read_text())
    fx.pop("provenance", None)
    p = tmp_path / "bare-extract.json"
    p.write_text(json.dumps(fx))
    rc = cli.main(["--extract", str(p), "--out", str(tmp_path / "o")])
    assert rc == 1  # G0 fail: no provenance
    m = json.loads((tmp_path / "o" / "workload-model.json").read_text())
    assert m["metadata"]["source"]["provenance"]["kind"] == "unknown"


def test_real_extract_provenance_wins_over_demo_flag(tmp_path):
    fx = json.loads(FIXTURE.read_text())
    fx["provenance"] = {
        "kind": "extracted",
        "extractedFrom": "the SKILL.md DQL query pack (9 queries) on tenant prod (3h)",
        "queryPack": ["q1", "q2"], "tenant": "prod", "window": "3h",
        "ranAtIso": "2026-10-15T00:00:00Z", "dqlRunLive": True,
    }
    p = tmp_path / "real-extract.json"
    p.write_text(json.dumps(fx))
    # --demo passed too, but the extract's own provenance must win
    rc = cli.main(["--extract", str(p), "--demo", "--out", str(tmp_path / "o")])
    assert rc == 0
    m = json.loads((tmp_path / "o" / "workload-model.json").read_text())
    assert m["metadata"]["source"]["provenance"]["kind"] == "extracted"
    assert m["metadata"]["source"]["provenance"]["tenant"] == "prod"
    assert "DEMO SAMPLE" not in (tmp_path / "o" / "scenario-proposal.md").read_text()
