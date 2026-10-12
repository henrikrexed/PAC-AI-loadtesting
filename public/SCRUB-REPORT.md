# Secret-scrub & genericization report — Phase 6a

Scope: everything under `/skills` and `/utilities` in this tree, derived from an internal
PAC toolkit workspace. Goal: standalone, parameterized, zero-secret skills/utilities safe
for a public repo. Re-verify anytime with `bash tools/secret-scan.sh`.

## 1. Automated scan

`tools/secret-scan.sh` checks the whole tree for:

- Dynatrace token formats (`dt0c01…`, `dt0s01…`, `dt0a01…` and long bearer blobs)
- tenant/environment URLs (`https://<env>.live|dev.dynatrace.com`; the
  `your-environment` placeholder is allowed)
- RFC1918 private IPs (localhost excluded)
- credential-looking assignments (`token|secret|password|apikey = <16+ chars>`)
- known internal-namespace identifiers from the source workspace (list maintained in
  the scanner; deliberately not spelled out here)

**Result: PASS** (initial run 2026-10-12). Excludes generated dirs (`out/`, `runs/`,
`node_modules/`, caches) which are gitignored.

## 2. What was scrubbed (manual review inventory)

This report intentionally describes the removed material by category, not by literal
name, so the audit trail ships without echoing internal identifiers.

### Removed entirely (internal-only)
- Live tenant extraction fixtures (per-target span/journey extracts) — replaced, not
  shipped.
- Real RUM session data fixtures (per-app session populations from the source tenant).
- Build drivers bound to specific tenants, tokens and internal output paths.
- Internal evidence/QA docs (test reports, generalization notes) referencing tenants,
  clusters and internal issue trackers.

### Replaced with synthetic equivalents
- `workload-model/fixtures/example_extract.json` — same schema as a live extraction;
  OpenTelemetry-demo-shaped (public open-source app names/routes); every number
  invented and internally consistent (7,200 synthetic traces / 40 rpm steady window,
  Little's-Law-consistent baseline, 8 synthetic SKUs). Powers `build_example.py` and
  the archetype/clustering/gate tests unchanged.
- `workload-model/fixtures/example_rum_sessions.json` — synthetic per-app RUM coverage
  (generic app names: storefront-web, portal-web, trading-web, docs-web,
  shopper-mobile; 24,000 synthetic sessions).
- `workload-model/fixtures/example_session_stitch.json` — synthetic session.id
  stitching facts (generic services: ads, chat-agent-service).
- Test assertions bound to source-tenant values were re-bound to the synthetic values
  (same test count; all suites green).

### Identifier scrubs (docs/docstrings/config)
- Tenant/cluster ids, dtctl context names → generic wording ("your tenant", `$DT_*`
  env vars).
- Internal app names → generic names (agent-gateway, chat-agent-service,
  storefront-web, …).
- Internal issue-tracker IDs and internal board-review narrative → neutral design
  rationale. Internal-only doc paths removed or inlined.
- Shared test fixtures: environment fields → `example`; internal approval refs →
  placeholders.
- DQL header comments: live-tenant validation notes → generic.

### Parameterization (no hard-codes remain)
- Env vars: `DT_ENDPOINT`, `DT_API_TOKEN` (scopes documented), `DT_TIMEFRAME`,
  `BASE_URL` (k6 `__ENV.BASE_URL`), `K6_BINARY`, `WORKLOAD_OUT` — see `.env.example`.
- DQL pack uses `$entryService`, `$frontendServer`, `$entryPrefix`, `$cacheService`,
  `$keyAttr`, `$env`, `$DT_TIMEFRAME` placeholders.
- `build_example.py` is self-contained (writes `out/example-frontend/`, `--out` /
  `WORKLOAD_OUT` override); no repo-root or internal `loadtests/` path coupling.

### Structural changes for standalone shipping
- `utilities/rum_sessions.py`, `utilities/session_stitch.py` — standalone single-file
  CLIs (pure module mirrored from `skills/workload-model/scripts/` + argparse `main`);
  stdin/file input; documented DQL; no telemetry I/O.
- New skill wrappers: `skills/rum-sessions/SKILL.md`, `skills/session-stitch/SKILL.md`.
- `k6-synthesis`: renderer-interface definition + shared acceptance harness vendored
  (`lib/vendor/renderer.mjs`, `test/vendor/{acceptance,registry}.mjs`) so the skill no
  longer depends on the source workspace's renderer-kit skill; imports re-pointed.
- `test_g0_gate.py` reads artifacts from the skill-local `out/` dir (regenerates via
  `build_example.py` when absent).

## 3. Test evidence (public tree, post-scrub)

| Suite | Result |
|---|---|
| `skills/workload-model` (pytest) | **68 passed** |
| `skills/k6-synthesis` (node --test) | **51 passed** |
| `skills/loadtest-run` (pytest) | **47 passed** |
| `skills/baseline-diff` (unittest) | **20 OK** |
| `utilities` CLIs (stdin smoke) | shape/cover + stitch/cover OK |

No real RUM/customer data in any fixture; all fixtures synthetic and labelled as such.
