# renderer-kit — test summary (ISI-5655)

Framework: `node --test` (Node built-in, zero external deps), plus the §4 schema
v1.1 regression in the Python `workload-model` suite (`jsonschema`, pytest).

## Acceptance criteria → tests

| ISI-5655 acceptance criterion | Evidence |
|---|---|
| `Renderer` interface + registry exist | `test/renderer.test.mjs`, `test/registry.test.mjs` |
| k6 renderer conforms + still passes its suite | `skills/k6-synthesis/test/renderer.test.mjs` (5 tests) + 44 original k6 tests all green |
| §4 v1.1 fields present + validated; pre-v1.1 model still validates | `skills/workload-model/tests/test_schema_v11.py` (7 tests) |
| trivial non-k6 renderer stub compiles + returns a capability report | `test/locust-stub.test.mjs` |
| shared acceptance harness every renderer reuses | `lib/acceptance.mjs` + used by both k6 and locust suites |

## Suite totals

| Suite | Tests | Result |
|---|---|---|
| renderer-kit (`node --test`) | 25 | PASS |
| k6-synthesis (`node --test`) | 49 (44 original + 5 conformance) | PASS |
| workload-model (`pytest`) | 44 (37 original + 7 schema v1.1) | PASS |

## What the shared harness enforces (`assertRendererConformance`)

1. object conforms to the `Renderer` interface (static shape)
2. `supports()` returns a well-formed capability report (`{ok, unsupported[]}`)
3. `render()` returns a well-formed `{files:[{path,content}], warnings[]}`
4. `render()` is **deterministic** — two renders of the same model are byte-identical
5. file paths are unique, relative, non-traversing

Run all:

```bash
(cd skills/renderer-kit && node --test)
(cd skills/k6-synthesis && node --test)
(cd skills/workload-model && python3 -m pytest -q)
```
