"""G0 exit-gate tests — including the acceptance-criterion-4 negative case."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import g0_gate as g0  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
MODEL = ROOT / "out" / "example-frontend" / "workload-model.json"
PROPOSAL = ROOT / "out" / "example-frontend" / "scenario-proposal.md"


def _rebuild():
    subprocess.run([sys.executable, str(SCRIPTS / "build_example.py")], check=True,
                   capture_output=True, cwd=SCRIPTS)


def _model():
    if not MODEL.exists():
        _rebuild()
    return json.loads(MODEL.read_text())


def _proposal():
    if not PROPOSAL.exists():
        _rebuild()
    return PROPOSAL.read_text()


def test_real_artifact_passes_g0():
    g = g0.evaluate_g0(_model(), dql_run_live=True, proposal_text=_proposal())
    assert g.passed, [c.detail for c in g.failures]
    assert len(g.checks) == 13


def test_provenance_required_fail_closed():
    # ISI-5928: a model with no provenance must fail G0 — no "unknown-but-shipped" kind.
    m = copy.deepcopy(_model())
    m["metadata"]["source"].pop("provenance", None)
    g = g0.evaluate_g0(m, dql_run_live=True, proposal_text=_proposal())
    assert not g.passed
    assert any(c.id == "provenance" and not c.passed for c in g.checks)


def test_demo_sample_dql_live_is_na_not_a_silent_pass():
    # The rebuilt example artifact is demo-stamped: dql-live records n/a (no live claim)
    # rather than silently claiming live DQL — even when the caller passes True.
    m = _model()
    assert m["metadata"]["source"]["provenance"]["kind"] == "demo-sample"
    for attest in (True, False):
        g = g0.evaluate_g0(m, dql_run_live=attest, proposal_text=_proposal())
        c = next(c for c in g.checks if c.id == "dql-live")
        assert c.passed and "no live-DQL claim" in c.detail
        p = next(c for c in g.checks if c.id == "provenance")
        assert p.passed and "demo-sample" in p.detail


def test_extracted_provenance_needs_live_attestation():
    m = copy.deepcopy(_model())
    m["metadata"]["source"]["provenance"] = {
        "kind": "extracted",
        "extractedFrom": "the SKILL.md DQL query pack (9 queries) on tenant t (3h)",
        "queryPack": ["q1"], "tenant": "t", "window": "3h",
        "ranAtIso": "2026-10-15T00:00:00Z", "dqlRunLive": True,
    }
    g = g0.evaluate_g0(m, dql_run_live=False, proposal_text=_proposal())
    assert next(c for c in g.checks if c.id == "provenance").passed
    assert not next(c for c in g.checks if c.id == "dql-live").passed
    g2 = g0.evaluate_g0(m, dql_run_live=True, proposal_text=_proposal())
    assert next(c for c in g2.checks if c.id == "dql-live").passed


def test_extracted_provenance_incomplete_fails():
    m = copy.deepcopy(_model())
    m["metadata"]["source"]["provenance"] = {"kind": "extracted"}  # no extractedFrom/tenant/window
    g = g0.evaluate_g0(m, dql_run_live=True, proposal_text=_proposal())
    assert not next(c for c in g.checks if c.id == "provenance").passed


def test_blocks_when_accesslog_unknown_and_no_caveat():
    # ACCEPTANCE CRITERION 4: availability unknown + no spans-only caveat -> G0 blocks.
    m = copy.deepcopy(_model())
    m["metadata"]["source"]["accessLogAvailability"] = "unknown"
    g = g0.evaluate_g0(m, dql_run_live=True, proposal_text="(no caveat recorded)")
    assert not g.passed
    assert any(c.id == "accesslog-availability" and not c.passed for c in g.checks)


def test_unavailable_with_caveat_passes():
    m = copy.deepcopy(_model())
    m["metadata"]["source"]["accessLogAvailability"] = "unavailable"
    g = g0.evaluate_g0(m, dql_run_live=True,
                       proposal_text="Access logs unavailable — spans-only extraction.")
    assert any(c.id == "accesslog-availability" and c.passed for c in g.checks)


def test_blocks_on_too_many_journeys():
    m = copy.deepcopy(_model())
    extra = copy.deepcopy(m["spec"]["journeys"][0])
    m["spec"]["journeys"].extend([{**extra, "id": f"extra-{i}"} for i in range(6)])  # -> 8 > 6
    g = g0.evaluate_g0(m, dql_run_live=True, proposal_text=_proposal())
    assert any(c.id == "journey-count" and not c.passed for c in g.checks)
    assert not g.passed


def test_blocks_on_littles_law_out_of_band():
    m = copy.deepcopy(_model())
    m["spec"]["arrivalProfile"]["littlesLawCheck"]["ratio"] = 7.4  # driver-wrapper mistake
    g = g0.evaluate_g0(m, dql_run_live=True, proposal_text=_proposal())
    assert any(c.id == "littles-law" and not c.passed for c in g.checks)


def test_blocks_on_dependson_without_correlates():
    m = copy.deepcopy(_model())
    co = next(j for j in m["spec"]["journeys"] if j["id"] == "buyer")
    for st in co["steps"]:
        st.pop("correlates", None)  # leave dependsOn dangling
    g = g0.evaluate_g0(m, dql_run_live=True, proposal_text=_proposal())
    assert any(c.id == "correlates" and not c.passed for c in g.checks)


def test_blocks_on_cacheprofile_missing_keycardinality():
    m = copy.deepcopy(_model())
    m["spec"]["payloads"]["product"]["cacheProfile"].pop("keyCardinality")
    g = g0.evaluate_g0(m, dql_run_live=True, proposal_text=_proposal())
    assert any(c.id == "cache-profile" and not c.passed for c in g.checks)


def test_blocks_when_dql_not_run_live():
    # ISI-5928: dql-live only applies to EXTRACTED models — an extracted model not
    # attested live must block. (The example artifact is demo-stamped: n/a, see
    # test_demo_sample_dql_live_is_na_not_a_silent_pass.)
    m = copy.deepcopy(_model())
    m["metadata"]["source"]["provenance"] = {
        "kind": "extracted",
        "extractedFrom": "the SKILL.md DQL query pack (9 queries) on tenant t (3h)",
        "queryPack": ["q1"], "tenant": "t", "window": "3h",
        "ranAtIso": "2026-10-15T00:00:00Z", "dqlRunLive": True,
    }
    g = g0.evaluate_g0(m, dql_run_live=False, proposal_text=_proposal())
    assert any(c.id == "dql-live" and not c.passed for c in g.checks)


def test_blocks_on_coverage_below_floor():
    m = copy.deepcopy(_model())
    m["spec"]["coverage"] = 0.5
    g = g0.evaluate_g0(m, dql_run_live=True, proposal_text=_proposal())
    assert any(c.id == "coverage" and not c.passed for c in g.checks)
