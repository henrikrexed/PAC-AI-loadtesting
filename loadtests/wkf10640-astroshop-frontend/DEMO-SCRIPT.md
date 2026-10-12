# PAC demo — "Load the program" (ISI-5723, child of ISI-5720)

**One observed workload model → two runnable load tests (k6 + JMeter).**
Theme: *The Matrix* 🔴💊 — *"I know kung fu." / "Show me." / "Guns. Lots of guns."*

- **Duration on stage:** ~4 min. **No live cluster calls** — everything below is pre-baked and deterministic.
- **Source model:** `loadtests/wkf10640-astroshop-frontend/workload-model.json` — live Astroshop frontend, tenant `wkf10640`, G0 12/12, real RUM→span extrapolation factor **1.27**.
- **Driver:** `./run-demo.sh` renders both tools from the model and prints the diff. Safe to run live or play the captured `demo-transcript.txt`.

---

## Step 0 — set the scene (10s)
> "This model was *observed*, not guessed. DQL spans + RUM sessions on a live Astroshop, extracted earlier — we are not re-extracting on stage."

Show `scenario-proposal.md` header + the Little's Law line: expected 3.6755 ≈ observed 3.6776 → **ratio 0.9994**. The model is physically consistent with the system it came from.

## Step 1 — telemetry → model (45s) · *"I know kung fu."*
```bash
sed -n '1,30p' workload-model.json      # metadata.source.queries — the real DQL
```
Call out:
- `evidenceSources: ["span"]`, `samplingRatio: 1.0` (this tenant is unsampled — important for the sampling slide).
- Two journeys, **weights from real outcomes**: `browser` 0.9908 / `buyer` 0.0092 (303,223 vs 2,810 of 306,033 root traces).
- `merge-plan.json`: browser journey is **RUM-primary**, scaled by **extrapolationFactor 1.2735** (span 33.03/s ÷ RUM 25.94/s) to the unsampled span truth.

## Step 2 — model → k6 (45s) · *"Show me."*
```bash
node ../../skills/k6-synthesis/bin/synthesize.mjs workload-model.json .
sed -n '24,52p' k6/otel-astroshop-frontend-wkf10640.js
```
Point at: `executor: "ramping-arrival-rate"` (open model), stages `29.24 → 43 → 38.93 → 0` (weight-scaled), `syntheticParams()` → `baggage: synthetic=true` on every request, `chain.js` correlation with fail-fast. **V2a: PASS.**

## Step 3 — model → JMeter (45s) · *same program, different gun*
```bash
node ../../skills/jmeter-synthesis/bin/synthesize.mjs workload-model.json .
grep -n "ConcurrencyThreadGroup\|VariableThroughputTimer\|baggage\|CSVDataSet" jmeter/*.jmx | head
```
Point at: **Concurrency Thread Group + Throughput Shaping Timer** (open model), `load_profile` rows `29.24 → 43 → 38.93 → 0`, Header Manager `baggage: synthetic=true`, CSV Data Sets (Zipf, K=10). **static check J1–J7: PASS.**

## Step 4 — diff (45s) · *"Guns. Lots of guns."*
```bash
sed -n '1,40p' DEMO-DIFF.md
```
> Same model. Same arrival envelope. Same journey mix. Same synthetic baggage. Same correlation. **Two engines, zero hand-authoring.** The model is the program; the renderer is the compiler back-end.

---

## Artifacts committed under `loadtests/wkf10640-astroshop-frontend/`
- `workload-model.json` (rev 3, V1-approved) · `scenario-proposal.md` · `merge-plan.json`
- `k6/` (script + `lib/` + `payloads/`) — V2a PASS
- `jmeter/` (`.jmx` + `data/*.csv` + manifest) — J1–J7 PASS
- `DEMO-DIFF.md` — the model→two-tools comparison table
- `run-demo.sh` · `demo-transcript.txt` — reproducible driver + captured run
