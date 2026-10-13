# `/examples` — sanitized synthetic sample outputs

These files show the **expected shape** of each artifact the AI-Performance-Testing
loop produces, so you can see what "good" looks like before you run it against your
own backend.

> **100% synthetic. Zero real data.**
> Every tenant/service/customer name is invented (`demo-tenant`, `shop-frontend`,
> `checkout-service`, …), every session id is a fake opaque uuid, and every
> number is representative — nothing here was extracted from any real tenant,
> user, or production run. These are illustrative fixtures, not evidence.

Each file maps to a step of the [Phase 6b tutorial](../tutorial/README.md).

| File | What it is | Tutorial step | Produced by |
|---|---|---|---|
| [`workload-model.example.json`](workload-model.example.json) | A complete, schema-valid workload model: open-model arrival profile, two weighted journeys (browse 0.85 / buyer 0.15) with per-step baselines, think-times, a G2 cart→checkout correlation, G4 cache-avoidance payload pools, and an `approved` V1 gate. | [§5 SCOPE](../tutorial/README.md#5-scope--turn-telemetry-into-a-workload-model) + [§6 VALIDATE](../tutorial/README.md#6-validate--the-human-gate-in-plain-terms) | `skills/workload-model` |
| [`k6/shop-frontend-example.js`](k6/shop-frontend-example.js) + [`k6/lib/`](k6/lib) + [`payloads/`](payloads) | The runnable k6 script generated **from the model above**: one `ramping-arrival-rate` scenario per journey, request chaining with fail-fast, Zipf cache-avoidance pools, and `baggage: synthetic=true` on every request. Passes the V2a static gate. | [§7 SYNTHESIZE](../tutorial/README.md#7-synthesize--generate-the-k6-test) | `skills/k6-synthesis` |
| [`baseline-diff.example.json`](baseline-diff.example.json) | A shape-diff verdict: the six tolerance dimensions (arrival shape, latency, service fan-out, error rate, journey mix) plus the mandatory R5 infra cross-check, ending in an `accept` decision. | [§9 ANALYZE](../tutorial/README.md#9-analyze--compare-shapes-then-decide) | `skills/baseline-diff` |
| [`session-reconstruction.example.json`](session-reconstruction.example.json) | Dual-source session reconstruction with **fake** session ids and timings: RUM (`user.events`) ordered journeys + OTel span-stitch fallback, `source.rumSessionCoverage`, measured per-page think-times, and the per-endpoint RUM⟗span merge. | [Sidebar: dual-source session reconstruction](../tutorial/README.md#sidebar-dual-source-session-reconstruction-in-plain-terms) | `skills/workload-model` (`rum_events.py` / `session_stitch.py` / `source_merge.py`) |

## Reproduce the k6 example yourself

The k6 artifacts in [`k6/`](k6) were generated from the model — regenerate them to
confirm:

```bash
# validate the model against the §4 schema
python3 -c "import json,jsonschema; \
  jsonschema.validate(json.load(open('examples/workload-model.example.json')), \
  json.load(open('skills/workload-model/scripts/schema.json'))); print('schema OK')"

# render it through k6-synthesis (V2a static gate must pass, exit 0)
cd skills/k6-synthesis
node bin/synthesize.mjs ../../examples/workload-model.example.json /tmp/example-out
```

The model carries `status.approval.decision == "approved"` so synthesis does not
fail-closed on the V1 human gate — in a real run that approval is the output of
[§6 VALIDATE](../tutorial/README.md#6-validate--the-human-gate-in-plain-terms),
not a hand-edit.

## Using these as a starting point

`workload-model.example.json` is a valid input to **every** renderer in this repo
(`k6-synthesis`, `jmeter-synthesis`, `locust-synthesis`, `gatling-synthesis`) via
the shared §4 renderer contract — swap in your own service names, baselines, and
arrival profile and point a renderer at it.
