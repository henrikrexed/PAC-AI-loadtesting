# CI/CD workflows — design (ISI-5758)

Two pipelines publish the **workload-model engine** as GitHub artifacts, per the
board's ask (binaries + container image). ISI-5743 owns this *design*; ISI-5735 owns
*execution* against the public remote. The split below is deliberate so there is exactly
one place that pushes to GHCR (no duplicate/competing pipelines).

| Workflow | Trigger | Produces |
|---|---|---|
| [`release.yml`](release.yml) | tag `v*` (or manual) | 5 PyInstaller binaries (`linux-amd64/arm64`, `darwin-amd64/arm64`, `windows-amd64`), each with a CycloneDX SBOM, attached to a generated GitHub Release. **Builds no image.** |
| [`docker.yml`](docker.yml) | PR → build+Trivy (no push); `main` → `edge`/`main-<sha>`; tag `v*` → `{version}`,`{major}.{minor}`,`latest` + Trivy + SBOM | multi-arch (amd64+arm64) image → `ghcr.io/henrikrexed/ai-performance-testing`. **The only pipeline that pushes to GHCR.** |

## Why split (vs. one combined `release`)

- **Image builds run on PRs and `main`, not only on tags** — so a broken `Dockerfile`
  or a new CVE is caught by Trivy on the PR, long before a release is cut.
- **One push path to GHCR** — `release.yml` never touches the registry, so the two
  pipelines can never race or double-publish the same tag.
- **Security remit** — Trivy runs on every PR and every tag; SBOMs are produced for
  both the binaries (per-asset) and the released image.

## Engine CLI contract (what both workflows invoke)

Both pipelines bundle the **`engine/`** package and call its single entry point. The
contract is fixed by [`docs/engine.md`](../../docs/engine.md):

- Entry point: `python -m engine.cli` → `engine/cli.py`
- Args: `--extract <extract.json> --out <dir> [--mode agentic|commerce]`
- Outputs: `out/workload-model.json` + `out/scenario-proposal.md`; exit `0` iff G0 passes
- Only runtime dependency: `jsonschema` (bundled into both the binaries and the image)
- Data file: `engine/schema.json` (shipped via PyInstaller `--add-data` and `COPY` in the image)
- Smoke fixture: `examples/crewai-deepseek-agent/extract.json`

## ⚠️ Precondition / open coordination item

As of this design, the `engine/` package **does not yet exist in the repo** — it is
*specified* by `docs/engine.md` but not implemented, and `examples/crewai-deepseek-agent/extract.json`
is likewise absent. **Both workflows will fail at build time until the engine package and
its smoke fixture are committed.** Implementing `engine/` (cli.py + the stdlib modules
`emit/g0_gate/shaping/archetypes/clustering/source_merge` + `schema.json` + tests + a
sample extract) is engine-packaging work owned by **ISI-5735**. These workflows are
ready to go green the moment that package lands.
