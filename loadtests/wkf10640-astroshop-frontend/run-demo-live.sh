#!/usr/bin/env bash
# run-demo-live.sh — PAC "load the program" demo, FULL LIVE end-to-end (ISI-5723 rev2).
#
# telemetry -> live DQL (fetch spans + fetch user.sessions) -> materialize the Astroshop
# model -> live V1 human gate -> render k6 + JMeter. NO pre-baked workload-model.json as
# the source. The committed rev1 artifacts (run-demo.sh) remain the RECORDED FALLBACK if
# stage network/tenant is unavailable.
#
#   ./run-demo-live.sh                 # full live run, 3h window, context tenant-b
#   ./run-demo-live.sh --window 90m    # tighter window
#   DT_CONTEXT=tenant-b ./run-demo-live.sh
#
# user.events: WAS scope-gated (403) until the board granted storage:user.events:read on the
# wkf10640 token (2026-10-13, ISI-5719); it now returns rows. The model is built from spans +
# user.sessions and does NOT depend on user.events either way, so the render is identical — the
# extractor probes it live and degrades gracefully (prints AVAILABLE, or the 403 note if the
# scope is ever missing). The now-flowing user.events unlocks ordered-RUM journeys (rum-journey-model.json).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
SCRIPTS="$REPO/skills/workload-model/scripts"
CTX="${DT_CONTEXT:-tenant-b}"
WINDOW="3h"
while [ $# -gt 0 ]; do case "$1" in --window) WINDOW="$2"; shift 2;; --context) CTX="$2"; shift 2;; *) shift;; esac; done

LIVE_FIXTURE="$REPO/skills/workload-model/fixtures/wkf10640_extract.live.json"
MODEL="$HERE/workload-model.json"
NOW="$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo 2026-10-13T05:45:00Z)"

sep() { printf '\n==================== %s ====================\n' "$1"; }

sep "STEP 0 — tenant reachable? (live DQL, context=$CTX)"
dtctl query --context "$CTX" -o json \
  "fetch spans, from:now()-5m | filter service.name==\"frontend\" | summarize c=count()" \
  >/dev/null 2>&1 && echo "live telemetry reachable ✓" || {
    echo "!! tenant unreachable — fall back to the RECORDED run: ./run-demo.sh"; exit 3; }

sep "STEP 1 — telemetry -> model (LIVE DQL extraction, window=$WINDOW)"
echo "running the frontend DQL pack live against $CTX (spans + user.sessions; user.events probed → now AVAILABLE, scope granted 2026-10-13; degrades gracefully if ever missing)"
python3 "$SCRIPTS/live_extract.py" --context "$CTX" --window "$WINDOW" --out "$LIVE_FIXTURE"

sep "STEP 1b — build the Astroshop model from the LIVE extract (G0-gated)"
WKF10640_FIXTURE="$LIVE_FIXTURE" WKF10640_GENERATED_AT="$NOW" \
  python3 "$SCRIPTS/build_wkf10640.py" | tail -3

sep "STEP 1c — live V1 human gate (presenter approves the observed model)"
python3 "$SCRIPTS/approve_model.py" "$MODEL" --by "presenter (PAC live demo)" --at "$NOW"

sep "STEP 2 — model -> k6  (renderer refuses unapproved models)"
node "$REPO/skills/k6-synthesis/bin/synthesize.mjs" "$MODEL" "$HERE"

sep "STEP 3 — model -> JMeter"
node "$REPO/skills/jmeter-synthesis/bin/synthesize.mjs" "$MODEL" "$HERE"

sep "STEP 4 — diff: same LIVE model, two tools"
echo "k6     : ramping-arrival-rate executor + syntheticParams() baggage=synthetic=true"
grep -o 'ramping-arrival-rate' "$HERE/k6/"*.js | head -1
echo "JMeter : Concurrency Thread Group + Throughput Shaping Timer + Header Manager baggage=synthetic=true"
grep -o 'ConcurrencyThreadGroup\|VariableThroughputTimer' "$HERE/jmeter/"*.jmx | sort -u
echo
echo "Live model: $(python3 -c "import json;m=json.load(open('$MODEL'));s=m['spec'];print('journeys',[ (j['id'],round(j['weight'],4)) for j in s['journeys']],'| LL ratio',s['arrivalProfile']['littlesLawCheck']['ratio'])")"
echo "See DEMO-DIFF.md for the full comparison table. Guns. Lots of guns."
