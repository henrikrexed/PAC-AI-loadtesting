---
name: renderer-kit
description: Renderer foundation for the AI load-testing loop (ISI-5655). Defines the formal Renderer interface (name/targetTool/schemaRange/supports/render), a tool registry keyed by name, the §4 v1.1 model accessors (G-R1 request / G-P1 field target), and the shared acceptance harness every k6/JMeter/Locust/Gatling renderer conforms to. Use when building or validating a renderer, or picking a target tool. Triggers "add a renderer", "renderer interface", "register renderer", "render workload model to <tool>".
---

# renderer-kit (SYNTHESIZE → renderer foundation, ISI-5655)

The prerequisite that makes the k6 / JMeter / Locust / Gatling renderers buildable
in parallel. Grounded in `docs/workload-model-engine-research.md` §4 and
`docs/methodology.md` §4 (v1.1).

## The Renderer interface (§4.3)

A renderer is a **pure function** over an approved `workload-model.json` — no
network, no model mutation, deterministic for a given `(model, opts)`:

```
interface Renderer {
  name: string         // "k6" | "jmeter" | "locust" | "gatling"
  targetTool: string   // human label
  schemaRange: string  // compatible §4 schema versions, e.g. ">=1.0 <2.0"
  supports(model) -> { ok, unsupported: [{ feature, reason, approximation? }] }
  render(model, opts) -> { files: [{ path, content }], warnings: [] }
}
```

- **`supports()` — the capability report.** Declared BEFORE rendering so the agent
  warns the human at VALIDATE about features a tool can't natively honor (e.g.
  Locust approximating an open arrival model). `ok` is derived: `true` iff
  `unsupported` is empty.
- **`render()` — deterministic codegen.** Returns in-memory files (paths relative
  to an outDir). No disk writes, no network — the host decides where to write.

## What this package provides

| Module | Export | Purpose |
|---|---|---|
| `lib/renderer.mjs` | `defineRenderer`, `makeCapabilityReport`, `validate*` | interface contract + shape validators |
| `lib/registry.mjs` | `RendererRegistry`, `createRegistry` | tool registry keyed by name |
| `lib/acceptance.mjs` | `assertRendererConformance`, `assertGolden` | shared acceptance harness (interface + determinism) |
| `lib/model-access.mjs` | `resolveRequest`, `resolveFieldTarget`, `partitionDrivableSteps` | §4 v1.1 (G-R1/G-P1) accessors w/ pre-v1.1 fallback |
| `lib/renderers/locust-stub.mjs` | `locustStub` | trivial non-k6 renderer stub (proves the interface) |

## §4 v1.1 additive fields (landed here, ISI-5655)

All additive/optional — **a pre-v1.1 model still validates** (see
`skills/workload-model/tests/test_schema_v11.py`):

- **G-R1** `steps[].request { method, pathTemplate, queryParams, headers, bodyPayloadRef }`
  — structured request so a renderer need not string-parse `operation`. Read via
  `resolveRequest(step)` (falls back to parsing `operation`).
- **G-P1** `payloads[].fields[].target { into, as }` — explicit request-location
  binding. Read via `resolveFieldTarget(field)` (falls back to `body_field`).
- **G-D1** ramp-start convention — documented in methodology §4: a ramping stage
  ramps from the previous stage's end rate; first ramping stage starts at 0;
  `shape` is authoritative; `ramp_down` reaches 0.

## Renderer matrix (§8 row 3)

| Tool | Renderer | Status |
|---|---|---|
| k6 | `skills/k6-synthesis` (`lib/renderer.mjs` → `k6Renderer`) | **conforms** (ISI-5631 retrofit) |
| Locust | `lib/renderers/locust-stub.mjs` | **stub** — real renderer = ISI-5657 |
| JMeter | — | ISI-5656 |
| Gatling | — | ISI-5658 |

## Authoring a new renderer

```js
import { defineRenderer, makeCapabilityReport } from 'renderer-kit';
import { resolveRequest, partitionDrivableSteps } from 'renderer-kit';

export const myRenderer = defineRenderer({
  name: 'jmeter', targetTool: 'Apache JMeter', schemaRange: '>=1.0 <2.0',
  supports(model) { /* return makeCapabilityReport([...unsupported]) */ },
  render(model, opts) { /* return { files:[{path,content}], warnings:[] } */ },
});
```

Then in the renderer's test suite:

```js
import { assertRendererConformance } from 'renderer-kit';
assertRendererConformance(myRenderer, approvedModel); // interface + determinism gate
```

## Tests

`npm test` (= `node --test`). Covers the interface validators, the registry, the
§4 v1.1 accessors (both v1.1 and pre-v1.1 paths), and the locust stub via the
shared acceptance harness.
