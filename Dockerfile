# syntax=docker/dockerfile:1
#
# Root image for the workload-model engine (SCOPE stage).
#
# The engine is pure Python 3.12 with `jsonschema` as its only runtime dependency,
# so the image is a thin slim-Python layer + the `engine/` package. It is built and
# pushed multi-arch (linux/amd64 + linux/arm64) by `.github/workflows/docker.yml`
# — this is the single file that pipeline wraps.
#
# Usage:
#   docker run --rm -v "$PWD:/work" ghcr.io/henrikrexed/ai-performance-testing:latest \
#     --extract /work/extract.json --out /work/out --mode agentic
#
# The committed worked example ships in the image too:
#   docker run --rm ghcr.io/henrikrexed/ai-performance-testing:latest \
#     --extract examples/crewai-deepseek-agent/extract.json --out /tmp/out --mode agentic

FROM python:3.12-slim

LABEL org.opencontainers.image.title="AI-Performance-Testing workload-model engine" \
      org.opencontainers.image.description="SCOPE-stage engine: extract.json -> workload-model.json + scenario-proposal.md (G0-gated)." \
      org.opencontainers.image.source="https://github.com/henrikrexed/AI-Performance-Testing" \
      org.opencontainers.image.licenses="Apache-2.0"

# Only runtime dep; pinned to a major range so the image is reproducible.
RUN pip install --no-cache-dir "jsonschema>=4,<5"

WORKDIR /app

# The engine package (cli.py + pipeline modules + schema.json) and the worked example.
COPY engine/ ./engine/
COPY examples/ ./examples/

# Drop privileges — the engine needs no root and writes only to the --out dir the
# caller mounts/specifies.
RUN useradd --create-home --uid 10001 engine \
    && chown -R engine:engine /app
USER engine

# The CLI is the entrypoint; all args (--extract/--out/--mode) flow straight to it.
ENTRYPOINT ["python", "-m", "engine.cli"]
CMD ["--help"]
