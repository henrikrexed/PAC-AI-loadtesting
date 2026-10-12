"""G0 exit gate for the SCOPE stage (methodology §3.1 exit criteria, §6).

G0 is the machine gate that must pass before VALIDATE (the human gate) is offered.
`evaluate_g0` returns a GateResult with one Check per §3.1 exit criterion so the
scenario-proposal can cite exactly which criterion blocked emission. Pure: the caller
injects the parsed model dict and a few extraction facts the model cannot carry itself
(e.g. whether all DQL ran live, the ingress cross-check result).

Mirrors the Check/GateResult shape of the sibling EXECUTE skill (skills/loadtest-run).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import jsonschema
except ImportError:  # pragma: no cover - jsonschema is available in the repo env
    jsonschema = None

_SCHEMA_PATH = Path(__file__).with_name("schema.json")

COVERAGE_MIN = 0.80
JOURNEY_MIN, JOURNEY_MAX = 1, 6
LITTLES_LAW_BAND = (0.5, 2.0)
_ACCESSLOG_CAVEAT = re.compile(r"access logs? unavailable|spans-only", re.IGNORECASE)


@dataclass
class Check:
    id: str
    passed: bool
    detail: str


@dataclass
class GateResult:
    name: str
    checks: list[Check] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    @property
    def failures(self) -> list[Check]:
        return [c for c in self.checks if not c.passed]

    def add(self, cid: str, passed: bool, detail: str) -> None:
        self.checks.append(Check(cid, bool(passed), detail))

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate": self.name,
            "passed": self.passed,
            "checks": [{"id": c.id, "passed": c.passed, "detail": c.detail} for c in self.checks],
        }


def load_schema() -> dict[str, Any]:
    return json.loads(_SCHEMA_PATH.read_text())


def evaluate_g0(
    model: dict[str, Any],
    *,
    dql_run_live: bool,
    proposal_text: str = "",
    schema: dict[str, Any] | None = None,
) -> GateResult:
    """Evaluate every §3.1 G0 exit criterion against a parsed workload-model dict.

    `dql_run_live`     — operator/skill attests all DQL ran live and field names confirmed.
    `proposal_text`    — the scenario-proposal.md body, scanned for the spans-only caveat
                         when access logs are unavailable.
    """
    g = GateResult("G0")
    spec = model.get("spec", {})
    meta = model.get("metadata", {})
    source = meta.get("source", {})
    journeys = spec.get("journeys", [])

    # 1. schema validity
    sch = schema or load_schema()
    if jsonschema is None:
        g.add("schema", False, "jsonschema not importable — cannot validate")
    else:
        errs = sorted(jsonschema.Draft7Validator(sch).iter_errors(model), key=str)
        if errs:
            first = errs[0]
            g.add("schema", False, f"{len(errs)} schema error(s); first: {first.message} at "
                                   f"{'/'.join(map(str, first.absolute_path)) or '<root>'}")
        else:
            g.add("schema", True, "validates against workload-model.schema.json (draft v1)")

    # 2. coverage >= 0.80
    cov = spec.get("coverage")
    g.add("coverage", isinstance(cov, (int, float)) and cov >= COVERAGE_MIN,
          f"coverage={cov} (min {COVERAGE_MIN})")

    # 3. journeys in [1, 6]
    nj = len(journeys)
    g.add("journey-count", JOURNEY_MIN <= nj <= JOURNEY_MAX,
          f"{nj} journeys (allowed {JOURNEY_MIN}-{JOURNEY_MAX})")

    # 4. every journey has codeRef per step OR explicit unlinked
    unlinked_ok = True
    bad = []
    for j in journeys:
        if j.get("unlinked"):
            continue
        for st in j.get("steps", []):
            if not st.get("codeRef"):
                unlinked_ok = False
                bad.append(f"{j.get('id')}::{st.get('id')}")
    g.add("code-linking", unlinked_ok,
          "all steps carry codeRef or journey flagged unlinked"
          if unlinked_ok else f"missing codeRef: {', '.join(bad[:5])}")

    # 5. every journey carries a baseline (p50/p95/p99/errorRate)
    base_ok = all(
        all(k in j.get("baseline", {}) for k in ("p50Ms", "p95Ms", "p99Ms", "errorRate"))
        for j in journeys
    )
    g.add("baseline", base_ok, "every journey carries server-span p50/p95/p99/errorRate")

    # 6. Little's Law ratio in [0.5, 2.0]
    llc = spec.get("arrivalProfile", {}).get("littlesLawCheck", {})
    ratio = llc.get("ratio")
    lo, hi = LITTLES_LAW_BAND
    g.add("littles-law", isinstance(ratio, (int, float)) and lo <= ratio <= hi,
          f"ratio={ratio} (band {lo}-{hi})")

    # 7. every dependsOn edge has a matching correlates entry (G2)
    corr_ok, missing = _check_correlates(journeys)
    g.add("correlates", corr_ok,
          "every dependsOn edge has a correlates data-flow"
          if corr_ok else f"dependsOn without correlates: {', '.join(missing[:5])}")

    # 8. payloads with cacheProfile.targetHitRatio>0 carry keyCardinality (G4)
    cache_ok, cache_bad = _check_cache_profiles(spec.get("payloads", {}))
    g.add("cache-profile", cache_ok,
          "cacheProfiles with targetHitRatio>0 carry keyCardinality"
          if cache_ok else f"missing keyCardinality: {', '.join(cache_bad)}")

    # 9. proposal names target env + caps
    caps = spec.get("caps", {})
    g.add("caps", bool(caps.get("maxRps") or caps.get("maxVus")) and bool(caps.get("maxDuration")),
          f"caps declared: {caps}")

    # 10. all DQL run live
    g.add("dql-live", bool(dql_run_live),
          "all DQL queries run live against the tenant and field names confirmed"
          if dql_run_live else "DQL not attested as run live")

    # 11. access-log availability confirmed OR spans-only caveat recorded
    avail = source.get("accessLogAvailability")
    caveat = bool(_ACCESSLOG_CAVEAT.search(proposal_text))
    accesslog_ok = avail == "available" or (avail == "unavailable" and caveat)
    g.add("accesslog-availability", accesslog_ok,
          f"accessLogAvailability={avail!r}; spans-only caveat in proposal={caveat}")

    # 12. dual-source reconciliation: each journey tagged span/accesslog/both; spanless flagged
    tag_ok = all(j.get("evidenceSource") in ("span", "accesslog", "both") for j in journeys)
    g.add("evidence-tagging", tag_ok,
          "every journey carries an evidenceSource tag"
          if tag_ok else "journey missing evidenceSource (span/accesslog/both)")

    return g


def _check_correlates(journeys: list[dict[str, Any]]) -> tuple[bool, list[str]]:
    missing: list[str] = []
    for j in journeys:
        for st in j.get("steps", []):
            deps = st.get("dependsOn") or []
            if not deps:
                continue
            corr_sources = {c.get("sourceStepId") for c in st.get("correlates", [])}
            for d in deps:
                if d not in corr_sources:
                    missing.append(f"{j.get('id')}::{st.get('id')}<-{d}")
    return (not missing), missing


def _check_cache_profiles(payloads: dict[str, Any]) -> tuple[bool, list[str]]:
    bad: list[str] = []
    for pid, pool in payloads.items():
        cp = pool.get("cacheProfile")
        if not cp:
            continue
        if cp.get("targetHitRatio", 0) > 0 and cp.get("keyCardinality") is None:
            bad.append(pid)
    return (not bad), bad


if __name__ == "__main__":  # CLI: python g0_gate.py <model.json> [proposal.md]
    import sys

    model_path = Path(sys.argv[1])
    prop = Path(sys.argv[2]).read_text() if len(sys.argv) > 2 else ""
    result = evaluate_g0(json.loads(model_path.read_text()), dql_run_live=True, proposal_text=prop)
    print(json.dumps(result.to_dict(), indent=2))
    sys.exit(0 if result.passed else 1)
