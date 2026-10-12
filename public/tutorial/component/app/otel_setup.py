"""OpenTelemetry bootstrap for the CrewAI + DeepSeek demo agent app.

Exports OTLP/HTTP traces to an OTLP endpoint (default: the in-cluster collector
shipped in k8s/collector.yaml, which forwards to your Dynatrace environment).
We own the span shape here so it stays deterministic — the shape the `workload-model`
skill reconstructs:

    <svc>/request  ->  agent.turn  ->  llm.call -> chat  [-> execute_tool <name> xN -> chat]  -> finalize  -> message.sent

The skill's terminal-action classifier (archetypes.AGENTIC_TOOL_PATTERNS) keys on the
substring `execute_tool` in a span/operation name, so the tool spans MUST be named
`execute_tool`. The front-end discovery keys on the earliest-start root per trace, so the
entry span MUST be the single root `<svc>/request`.
"""
from __future__ import annotations

import os

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "crewai-deepseek-agent")

_PROVIDER: TracerProvider | None = None


def init_tracing() -> trace.Tracer:
    """Idempotently install the global TracerProvider and return the app tracer."""
    global _PROVIDER
    if _PROVIDER is None:
        # OTEL_EXPORTER_OTLP_ENDPOINT points at the dedicated agent collector, e.g.
        # http://agent-collector.agentapp.svc.cluster.local:4318
        # The HTTP exporter appends /v1/traces itself.
        resource = Resource.create(
            {
                "service.name": SERVICE_NAME,
                "service.namespace": os.getenv("OTEL_SERVICE_NAMESPACE", "agentapp"),
                "service.version": os.getenv("APP_VERSION", "0.1.0"),
                # gen_ai system tag so DT groups this as an AI service.
                "gen_ai.system": "deepseek",
            }
        )
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        trace.set_tracer_provider(provider)
        _PROVIDER = provider
    return trace.get_tracer("crewai-deepseek-agent")


def shutdown_tracing() -> None:
    """Flush pending spans on shutdown so the load-window tail is not lost."""
    if _PROVIDER is not None:
        _PROVIDER.shutdown()
