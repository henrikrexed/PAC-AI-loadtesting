# ISI-5928 (WS-C) — Real-scan integrity: E2E repro, fix, and JMeter stock-validity evidence

Date: 2026-10-15 · Branch: `isi-5928/wsc-model-integrity` (off `canonical/main` @ `12f432c`) · Parent plan: [ISI-5734](/ISI/issues/ISI-5734) rev-6 WS-C.

## 1. E2E repro — silent example fallback CONFIRMED (before the fix)

Fresh environment = no `dtctl` on `PATH`, empty `HOME`, no tenant configured. Run the
workload-model engine exactly as a new user would:

```bash
env -i PATH=/usr/bin:/bin HOME=<empty-dir> \
  python3 skills/workload-model/scripts/cli.py --out /tmp/fresh-target
```

Observed **before the fix** (main @ `12f432c`):

- **Exit 0.** `workload-model.json` + `scenario-proposal.md` written to `/tmp/fresh-target`.
- **G0 PASS 12/12** — including `dql-live: passed=true` *"all DQL queries run live against
  the tenant and field names confirmed"* — a **false claim**: zero DQL ran, no tenant
  existed. Root cause: `cli.py` defaulted `--extract` to the bundled synthetic fixture AND
  hardcoded `dql_run_live=True` into the gate (`evaluate_g0(model, dql_run_live=True, ...)`).
- **No provenance.** The output was byte-for-byte indistinguishable from a real extraction;
  `metadata.source.tool` said `dtctl`. A downstream renderer would accept it (the repo's own
  `examples/README.md` marketed the synthetic example model as "valid input to every renderer").

This is exactly the silent-example-fallback reported by Henrik, reproduced deterministically.

## 2. The fix (all on branch `isi-5928/wsc-model-integrity`)

| Scope item | Change |
|---|---|
| Fail-closed env probe (step 0) | NEW `skills/workload-model/scripts/env_probe.py`: dtctl present → DQL backend reachable/authenticated → target service observed in window (unpinned → discovery table + exit 2; never a silent choice). Non-zero exit with exact remediation on every failure. Prints the `provenanceTemplate` the extract adapter must copy. Wired into SKILL.md workflow as mandatory step 0. |
| No silent fallback | `cli.py`: `--extract` has **no default**. Without `--extract` and without `--demo` → **exit 2** with actionable guidance, nothing written. |
| Demo quarantine | NEW `--demo` explicit opt-in: bundled fixture / examples are usable ONLY through it; output stamped `provenance.kind=demo-sample` + unmissable DEMO banner in the proposal. `k6-synthesis` (`lib/model.mjs assertNotDemo`, called **before** the V1 approval gate in `synthesize.mjs` + `renderer.mjs`) **refuses demo-sample models** unless `--demo` / `WORKLOAD_MODEL_ALLOW_DEMO=1`. |
| Provenance stamping | `emit.py` `make_extracted_provenance` / `make_demo_provenance`; `metadata.source.provenance = {kind: extracted \| demo-sample, extractedFrom, queryPack, tenant, window, ranAtIso, dqlRunLive}`; additive block in `scripts/schema.json` (extracted ⇒ `extractedFrom`+`tenant`+`window` required). Retro-stamped: `fixtures/example_extract.json`, `examples/workload-model.example.json`, `examples/crewai-deepseek-agent/extract.json`. |
| Honest gate | `g0_gate.py`: criterion **13 provenance** (fail-closed without it — no "unknown-but-shipped" kind); `dql-live` now derived from provenance — demo models record `n/a — no live-DQL claim`, never a silent pass. Standalone CLI derives from the model (`--attest-live` for operators). |

**After-fix verification** (same fresh environment):

- `workload-engine --out X` → **exit 2**, guidance printed (env_probe → real run; `--demo` → demo run), **no files written**.
- `workload-engine --demo --out X` → exit 0, G0 PASS 13/13, model stamped `demo-sample`, proposal carries the DEMO banner, gate output records `no live-DQL claim`.
- `node bin/synthesize.mjs <demo-stamped model>` → refused: `demo guard (ISI-5928): … Demo data is never silently selectable as input…` (fires **before** the V1 gate). With `--demo` it proceeds.
- **Live probe against the real tenant** (`env -u XDG_CONFIG_HOME python3 scripts/env_probe.py --context tenant-b --service frontend --window 2h`): `ok: true`, `rootTraces: 183751`, provenance template emitted — the probe passes on a configured environment and fails closed (with `dtctl config set-context` guidance) on an unconfigured one.

Tests: workload-model `pytest` **84 passed** (new: `test_env_probe.py`, `test_cli_provenance.py`, provenance cases in `test_g0_gate.py` / `test_schema_v11.py`); k6-synthesis `node --test` **56 passed** (new: `test/model.demo-guard.test.mjs`).

## 3. JMeter stock-validity evidence (gates WS-D)

Re-rendered JMeter **from the REAL wkf10640 extraction** (`loadtests/wkf10640-astroshop-frontend/workload-model.json` — real DQL extraction on tenant wkf10640) via `skills/jmeter-synthesis` (isi-5844 checkout): renderer's own static gate passed (J1–J7). Then loaded with **stock JMeter 5.6.3** (`SaveService.loadTree`, JDK 17.0.20, parse-only — no test execution):

```
LOAD_FAIL: CannotResolveClassException:
  com.blazemeter.jmeter.threads.concurrency.ConcurrencyThreadGroup   (line 80)
  kg.apc.jmeter.timers.VariableThroughputTimer                       (line 92)
version: 5.6.3
```

With two third-party plugins on the classpath — `kg.apc:jmeter-plugins-casutg:3.1.1` (Custom
Thread Groups) and `kg.apc:jmeter-plugins-tst:2.6` (Throughput Shaping Timer) — the same file:

```
LOAD_OK top-level keys=1
```

**Verdict: the .jmx rendered from real extracted data is NOT valid stock JMeter 5.6.** The
renderer depends on two non-stock BlazeMeter/jpgc plugin classes. **WS-D (JMeter format
fix) fires** — fix options: emit stock `ThreadGroup`/`SetupThreadGroup` +
`PreciseThroughputTimer` (stock since 5.3), or make plugin use an explicit opt-in with the
dependency declared and installed by preflight. Evidence artifacts uploaded to
[ISI-5928](/ISI/issues/ISI-5928); loader + jar set reproducible via the commands above.

## 4. Residual notes

- `examples/` quarantine of demo data was already in place on `main` (WS-0/WS-E work);
  this change closes the *selection* hole (fail-closed engine + consumer guard + provenance).
- Legacy models without provenance pass k6-synthesis with a **warning** (back-compat);
  all newly built models are provenance-stamped and G0 fails closed without it.
