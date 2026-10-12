#!/usr/bin/env bash
# run-demo.sh — PAC "load the program" demo driver (ISI-5723).
# Deterministic, NO live cluster calls: renders k6 + JMeter from the on-disk,
# pre-approved Astroshop model and prints the model->two-tools diff.
#
#   ./run-demo.sh            # render both tools + show the diff
#
# Safe to run live on stage or to regenerate demo-transcript.txt.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
MODEL="$HERE/workload-model.json"

sep() { printf '\n==================== %s ====================\n' "$1"; }

sep "STEP 1 — telemetry -> model (pre-baked, no re-extraction)"
echo "model:  $(python3 -c "import json;m=json.load(open('$MODEL'));print(m['metadata']['name'],'rev',m['status']['revision'])")"
echo "source: DQL spans + RUM sessions (samplingRatio=1.0, evidence=span); RUM->span factor 1.2735"
python3 - "$MODEL" <<'PY'
import json,sys
m=json.load(open(sys.argv[1]))
for j in m['spec']['journeys']:
    print(f"  journey {j['id']:<8} weight={j['weight']:.4f} entry={j['entrypoint']}")
ll=m['spec']['arrivalProfile']['littlesLawCheck']
print(f"  Little's Law: expected {ll['expectedConcurrency']} ~ observed {ll['observedConcurrency']} -> ratio {ll['ratio']}")
PY

sep "STEP 2 — model -> k6"
node "$REPO/skills/k6-synthesis/bin/synthesize.mjs" "$MODEL" "$HERE"

sep "STEP 3 — model -> JMeter"
node "$REPO/skills/jmeter-synthesis/bin/synthesize.mjs" "$MODEL" "$HERE"

sep "STEP 4 — diff: same model, two tools"
echo "k6     : ramping-arrival-rate executor + syntheticParams() baggage=synthetic=true"
grep -o 'ramping-arrival-rate' "$HERE/k6/"*.js | head -1
echo "JMeter : Concurrency Thread Group + Throughput Shaping Timer + Header Manager baggage=synthetic=true"
grep -o 'ConcurrencyThreadGroup\|VariableThroughputTimer' "$HERE/jmeter/"*.jmx | sort -u
echo
echo "See DEMO-DIFF.md for the full comparison table. Guns. Lots of guns."
