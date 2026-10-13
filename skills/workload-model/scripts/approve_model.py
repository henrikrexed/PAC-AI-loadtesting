"""approve_model.py — the live V1 human gate for the PAC demo (ISI-5723 rev2).

The renderers fail-closed: `assertApproved` refuses any model whose
`status.approval.decision != "approved"` for its current revision (k6 + JMeter
model.mjs). A pre-signed approval cannot cover a model that was extracted live on
stage — its content is fresh every run. So the demo makes the gate a *narrative
beat*: after the live model materializes, the presenter approves it, bound to the
freshly computed canonical hash. "The engine will not fire a single request until a
human approves what it observed."

This stamps an in-session approval onto a freshly-built workload-model.json:
  python3 approve_model.py <model.json> [--by "presenter (live demo)"] [--at <iso>]

Idempotent; exits non-zero if the model is missing a revision.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


def canonical_hash(spec: dict) -> str:
    blob = json.dumps(spec, sort_keys=True, separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(blob).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("--by", default="presenter (live demo gate)")
    ap.add_argument("--at", default="2026-10-13T05:45:00Z")
    args = ap.parse_args()

    p = Path(args.model)
    m = json.loads(p.read_text())
    rev = m.get("status", {}).get("revision")
    if not isinstance(rev, int):
        print("ERROR: model has no integer status.revision", file=sys.stderr)
        return 1

    h = canonical_hash(m["spec"])
    m["status"]["hash"] = h
    m["status"]["approval"] = {
        "decision": "approved",
        "revision": rev,
        "decisionBy": args.by,
        "decisionAt": args.at,
        "note": (
            f"LIVE V1 human gate: presenter approved the freshly-extracted model (rev {rev}, "
            f"{h[:19]}…) on stage. Non-production, extraction-only; tenant wkf10640 isolated per "
            "methodology §7.1. Renderers fail-closed without this approval — the gate is a feature."
        ),
    }
    p.write_text(json.dumps(m, indent=2) + "\n")
    print(f"approved {p.name}: rev {rev}, hash {h[:19]}…  decisionBy={args.by!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
