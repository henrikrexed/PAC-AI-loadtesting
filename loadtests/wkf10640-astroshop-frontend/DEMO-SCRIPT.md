# PAC demo — "Load the program" (ISI-5723, child of ISI-5720)

**One observed workload model → two runnable load tests (k6 + JMeter).**
Theme: *The Matrix* 🔴💊 — *"I know kung fu." / "Show me." / "Guns. Lots of guns."*

- **Duration on stage:** ~5 min.
- **Primary = FULL LIVE (rev2):** `./run-demo-live.sh` — live DQL (`fetch spans` + `fetch user.sessions`)
  on `tenant-b`/wkf10640 → materialize the Astroshop model → **live V1 human gate** → render k6 + JMeter.
  **No pre-baked `workload-model.json` as the source.** Step 0 auto-checks tenant reachability.
- **Fallback = recorded (rev1):** `./run-demo.sh` renders both tools from the committed deterministic
  model and prints the diff; `demo-transcript.txt` is the captured run. Use only if stage network/tenant
  is down (`run-demo-live.sh` tells you when to switch).
- **The wall came down (update 2026-10-13):** `fetch user.events` **was** scope-gated → 403 until the
  board granted `storage:user.events:read` on the wkf10640 token ([ISI-5719](/ISI/issues/ISI-5719)); it now
  returns rows. The frontend demo model is built from **spans + `user.sessions`** and does **not** depend on
  `user.events` either way, so the k6/JMeter render is identical — but the extractor still probes it live and
  **degrades gracefully** if the scope is ever missing (the live script prints `user.events: AVAILABLE` or the
  degrade note). The now-flowing `user.events` unlocks the **ordered-RUM journey upgrade** (`rum-journey-model.json`:
  16 ordered templates + real measured think-times, 18,773 sessions) — a "what's next" beat, not part of this render.

---

## Step 0 — set the scene (10s) · live run
```bash
./run-demo-live.sh          # the whole pipeline; steps below narrate what scrolls by
```
> "This model is *observed*, not guessed — and we're observing it **right now**. DQL against a live Astroshop, on stage."

## Step 1 — telemetry → model, LIVE (60s) · *"I know kung fu."*
`live_extract.py` runs the frontend DQL pack against `tenant-b`/wkf10640 and materializes
`workload-model.json` from the result; `build_wkf10640.py` re-runs the **G0 gate (12/12)** on the
fresh numbers. Call out as they print:
- live **total frontend root traces** and order split **browser ~99% / buyer ~1%** (re-derived live, not a constant);
- `samplingRatio: 1.0` (this tenant is unsampled — important for the sampling slide);
- **the wall came down:** `fetch user.events` now returns rows (scope granted 2026-10-13) → *"this was a 403 wall last week; the model never needed it — it's built from spans + user.sessions — and now that user.events flows, it unlocks ordered journeys + real think-times (rum-journey-model.json)."* (If the scope is ever missing the extractor degrades gracefully and prints the 403 note — still lossless.)

Then the **V1 human gate** fires (`approve_model.py`): *"the engine won't synthesize a single request until a human approves what it observed."*

### (fallback only) pre-baked model
If Step 0 reported the tenant unreachable, run `./run-demo.sh` instead and narrate from the committed model:
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

## Artifacts under `loadtests/wkf10640-astroshop-frontend/`
**Live (rev2, primary):**
- `run-demo-live.sh` — full live e2e driver (DQL → model → gate → k6+JMeter), auto-detects tenant reachability
- live extractor + signer live under `skills/workload-model/scripts/` (`live_extract.py`, `approve_model.py`);
  `build_wkf10640.py` takes a `WKF10640_FIXTURE` override so the deterministic build runs on the live extract unchanged
- `skills/workload-model/fixtures/wkf10640_extract.live.json` — a sample captured live run (shows the extract shape; the live probe now reports `user.events: AVAILABLE`, and still degrades gracefully if the scope is absent)
- `rum-journey-model.json` + `rum-journey-sidebyside.md` — the now-unlocked ordered-RUM upgrade (ISI-5719, `user.events`)

**Recorded fallback (rev1):**
- `workload-model.json` (rev 3, V1-approved) · `scenario-proposal.md` · `merge-plan.json`
- `k6/` (script + `lib/` + `payloads/`) — V2a PASS · `jmeter/` (`.jmx` + `data/*.csv` + manifest) — J1–J7 PASS
- `DEMO-DIFF.md` — the model→two-tools comparison table · `run-demo.sh` · `demo-transcript.txt`
