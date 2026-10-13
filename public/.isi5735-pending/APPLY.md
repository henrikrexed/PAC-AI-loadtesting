# ISI-5735 — pending push to the public repo

> **ISI-5758 design update (2026-10-13).** The combined `release.yml` captured in this
> bundle/patch is **superseded** by the split design in
> [`public/.github/workflows/`](../.github/workflows/) — `release.yml` (binaries + GitHub
> Release + per-binary SBOM, **no image**) and `docker.yml` (the single GHCR push path,
> with Trivy on every PR/tag + image SBOM). When pushing, apply those two files instead of
> the bundle's `release.yml`. **Precondition both pipelines share:** the `engine/` package
> that `docs/engine.md` specifies (and `examples/crewai-deepseek-agent/extract.json`) does
> **not yet exist** — implement it (engine-packaging, ISI-5735) before tagging, or both
> workflows fail at the build step. See `public/.github/workflows/README.md`.


The deliverable commit is **built, verified, and committed** but could **not be pushed**:
both git credentials (`~/.git-credentials` `x-access-token`, and `~/.github_pat`) return
`403 denied to henrikrexed`. The App token from ISI-5665 was short-lived and has expired.

**Commit:** `35579874abe8434d7e6a184eafbf397a54823dfa`
(base: `6e7d3f5`, current public `main` HEAD)

## What it contains (ISI-5735 parts 1–4)
- `.github/workflows/release.yml` — on `v*` tag: PyInstaller binaries
  (linux-amd64/arm64, darwin-amd64/arm64, windows-amd64) attached to the GitHub Release
  + multi-arch Docker image → `ghcr.io/henrikrexed/ai-performance-testing`.
- `Dockerfile`, `.dockerignore` — python:3.12-slim, jsonschema, non-root.
- `.env.example` — Dynatrace tokens/scopes.
- `docs/requirements.md`, `docs/skills-install.md`, `docs/engine.md`.
- `README.md` — Requirements + engine install + skills-install sections.

## Unblock requirement
A fine-grained PAT (or GitHub App token) for `henrikrexed/AI-Performance-Testing` with
**both**:
- `Contents: write` (push commits), **and**
- `Workflows: write` (required specifically to push files under `.github/workflows/` —
  a Contents-only token 403s on the workflow file).

## Apply + push once a write token is available
```bash
git clone https://github.com/henrikrexed/AI-Performance-Testing.git
cd AI-Performance-Testing
git am < /mnt/nas/projects/PAC-AI-Loadtest/public/.isi5735-pending/isi5735.patch
# or: git pull /mnt/nas/projects/PAC-AI-Loadtest/public/.isi5735-pending/isi5735.bundle
git push origin HEAD:main           # needs the write+workflows token

# then trigger the release:
git tag v0.1.0 && git push origin v0.1.0
# the `release` workflow builds all 5 binaries + the GHCR image and publishes the Release.
```
Rotate the token after use.
