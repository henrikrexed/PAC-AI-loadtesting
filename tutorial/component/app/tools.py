"""CrewAI tools, each wrapped so every invocation emits an `execute_tool` span.

The span NAME is the literal `execute_tool` (the terminal signal the workload-model skill
matches via AGENTIC_TOOL_PATTERNS). The specific tool is carried as attributes
(`gen_ai.tool.name`, `tool.name`) so turns and tool invocations are both visible, mirroring
the reference agent-gateway shape (`execute_tool web_search xN`).

The tools are hermetic (no outbound network): the generalization test cares about the trace
*shape* and arrival process, not tool correctness. Deterministic-but-varied outputs keep the
app self-contained and safe to run under sustained load without hammering third parties.
"""
from __future__ import annotations

import hashlib
from typing import Type

from crewai.tools import BaseTool
from opentelemetry import trace
from pydantic import BaseModel, Field

_tracer = trace.get_tracer("crewai-deepseek-agent")


def _span_tool(name: str, query: str):
    """Open an `execute_tool` span for a single tool invocation."""
    span = _tracer.start_span("execute_tool")
    span.set_attribute("gen_ai.tool.name", name)
    span.set_attribute("tool.name", name)
    span.set_attribute("gen_ai.operation.name", "execute_tool")
    span.set_attribute("tool.query", query[:256])
    return span


class _WebSearchInput(BaseModel):
    query: str = Field(..., description="Search query")


class WebSearchTool(BaseTool):
    name: str = "web_search"
    description: str = "Search the web for recent information about a topic. Use for factual lookups."
    args_schema: Type[BaseModel] = _WebSearchInput

    def _run(self, query: str) -> str:
        span = _span_tool("web_search", query)
        try:
            # Deterministic pseudo-results keyed off the query so load is reproducible.
            h = hashlib.sha256(query.encode()).hexdigest()[:8]
            span.set_attribute("tool.result_count", 3)
            return (
                f"Top results for '{query}':\n"
                f"1. Overview article [{h}a]\n"
                f"2. Reference docs [{h}b]\n"
                f"3. Recent discussion [{h}c]"
            )
        finally:
            span.end()


class _CalcInput(BaseModel):
    expression: str = Field(..., description="Arithmetic expression, e.g. '3 * (4 + 5)'")


class CalculatorTool(BaseTool):
    name: str = "calculator"
    description: str = "Evaluate a simple arithmetic expression (+, -, *, /, parentheses)."
    args_schema: Type[BaseModel] = _CalcInput

    def _run(self, expression: str) -> str:
        span = _span_tool("calculator", expression)
        try:
            allowed = set("0123456789+-*/(). ")
            if not set(expression) <= allowed:
                span.set_attribute("tool.error", "disallowed_chars")
                return "error: expression contains disallowed characters"
            try:
                value = eval(expression, {"__builtins__": {}}, {})  # noqa: S307 - whitelisted chars
            except Exception as exc:  # noqa: BLE001
                span.set_attribute("tool.error", str(exc)[:128])
                return f"error: {exc}"
            span.set_attribute("tool.result", str(value)[:64])
            return str(value)
        finally:
            span.end()


def build_tools() -> list[BaseTool]:
    return [WebSearchTool(), CalculatorTool()]
