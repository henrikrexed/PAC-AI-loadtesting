"""Fail-closed environment probe (ISI-5928) — run BEFORE any extraction.

The workload-model skill must extract from the user's REAL telemetry or stop. This probe
checks, in order:

  1. dtctl is installed and on PATH
  2. the DQL backend is reachable and authenticated for the given context
  3. the target service is actually observed in the window (or, without --service, prints
     the observed entry services and asks the operator to pin one)

It NEVER falls back to a bundled fixture, an existing workload-model.json, or any
examples/ sample. On any failure it exits non-zero with the exact remediation.

Success prints a JSON block that the extract adapter MUST copy into the neutral extract
as its `provenance` field — this is how `extracted-from: <query pack> on tenant <Y>
(<window>)` gets stamped onto the model (emit.make_extracted_provenance shape).

Run:  python3 env_probe.py --context <dtctl-context> [--service <name>] [--window 3h]
Exit: 0 = environment OK (JSON summary on stdout)
      1 = fail-closed (actionable guidance on stderr)
      2 = reachable, but no --service pinned (discovery table printed; pick one, rerun)
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone

PROBE_TIMEOUT_S = 30


def _fail(msg: str, hint: str) -> int:
    print(f"[env-probe] FAIL — {msg}", file=sys.stderr)
    for line in hint.strip().splitlines():
        print(f"           {line}", file=sys.stderr)
    print("           (The workload-model skill is fail-closed: it will NOT fall back to "
          "example/demo data.)", file=sys.stderr)
    return 1


def _parse_window_seconds(window: str) -> int:
    m = re.fullmatch(r"(\d+)([hmsd])", window)
    if not m:
        raise SystemExit(f"[env-probe] bad --window {window!r} (use e.g. 90m, 3h, 2d)")
    n, unit = int(m.group(1)), m.group(2)
    return n * {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]


def _dtctl(args: list[str], timeout: int = PROBE_TIMEOUT_S) -> subprocess.CompletedProcess:
    return subprocess.run(["dtctl", *args], capture_output=True, text=True, timeout=timeout)


def _query(context: str, dql: str) -> dict:
    proc = _dtctl(["query", "--context", context, "-o", "json", dql])
    out = (proc.stdout or "").strip()
    if out.startswith("{"):
        payload = json.loads(out)
        if "records" in payload:
            return payload
        raise RuntimeError(f"DQL error envelope: {json.dumps(payload.get('error', payload))[:300]}")
    raise RuntimeError(f"dtctl produced no JSON records.\nstdout={out[:200]}\n"
                       f"stderr={(proc.stderr or '')[:200]}\nreturncode={proc.returncode}")


def main() -> int:
    ap = argparse.ArgumentParser(prog="env-probe")
    ap.add_argument("--context", required=True, help="dtctl context name (the tenant to extract from)")
    ap.add_argument("--service", default=None,
                    help="target service name; omit to run discovery and print candidates")
    ap.add_argument("--window", default="3h", help="lookback window for the service check (default 3h)")
    a = ap.parse_args()

    # --- 1. dtctl installed --------------------------------------------------
    if shutil.which("dtctl") is None:
        return _fail(
            "dtctl not found on PATH — the DQL backend driver is required for extraction.",
            "Install dtctl:  https://github.com/dynatrace-oss/dtctl (or brew install dtctl).\n"
            "If you only wanted to try the skill on synthetic data, that is an explicit\n"
            "opt-in:  workload-engine --demo --out <dir>  (output is stamped demo-sample).",
        )

    # --- 2. backend reachable + authenticated for this context ----------------
    try:
        reach = _query(a.context, "fetch spans, from:-5m | summarize c=count()")
    except RuntimeError as e:
        return _fail(
            f"DQL backend not reachable/authenticated for context '{a.context}': {e}",
            "Check the context with:   dtctl ctx list\n"
            "Configure one with:       dtctl config set-context   (then dtctl auth login,\n"
            "                          or set DT_ENDPOINT / DT_API_TOKEN), and re-run the probe.",
        )
    except subprocess.TimeoutExpired:
        return _fail(
            f"DQL backend timed out (> {PROBE_TIMEOUT_S}s) for context '{a.context}'.",
            "Verify network reachability of the tenant endpoint, then re-run the probe.",
        )

    # --- 3. target service observed in the window ------------------------------
    wsec = _parse_window_seconds(a.window)
    fr = f"from:now()-{a.window}"
    # G1-C two-stage form (validated on tenant wkf10640, SKILL.md): earliest-start root span
    # per trace, then count traces per entry service.
    disc = _query(
        a.context,
        f'fetch spans, {fr} '
        f'| filter request.is_root_span == true '
        f'| sort start_time asc '
        f'| summarize entryService = takeFirst(service.name), by: {{ trace.id }} '
        f'| summarize traces = count(), by: {{ entryService }} '
        f'| sort traces desc',
    )["records"]
    services = [(r.get("entryService"), int(r.get("traces") or 0)) for r in disc]

    if not a.service:
        print("[env-probe] backend OK — target service not pinned. Observed entry services "
              f"(last {a.window}):")
        for svc, n in services[:10]:
            print(f"           {svc or '<unknown>':<40} {n:>8} traces")
        print("           Re-run with:  env_probe.py --context " + a.context +
              " --service <name>   (extraction is fail-closed: no silent target choice)",
              file=sys.stderr)
        return 2

    hits = [n for svc, n in services if svc == a.service]
    if not hits:
        top = ", ".join(f"{s} ({n})" for s, n in services[:5]) or "<none observed>"
        return _fail(
            f"service '{a.service}' has no root spans in the last {a.window} on context "
            f"'{a.context}'.",
            f"Observed entry services: {top}\n"
            "Check the service name / window, or scope to a context where the service is "
            "instrumented. Extraction refuses to guess a target.",
        )

    ok = {
        "ok": True,
        "tool": "dtctl",
        "context": a.context,
        "service": a.service,
        "window": a.window,
        "windowSeconds": wsec,
        "rootTraces": hits[0],
        "ranAtIso": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        # Copy this block into the neutral extract as `provenance` (add your queryPack):
        "provenanceTemplate": {
            "kind": "extracted",
            "extractedFrom": f"<query pack> on tenant {a.context} ({a.window})",
            "queryPack": ["<paste the SKILL.md DQL pack you ran>"],
            "tenant": a.context,
            "window": a.window,
            "ranAtIso": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "dqlRunLive": True,
        },
    }
    print(json.dumps(ok, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
