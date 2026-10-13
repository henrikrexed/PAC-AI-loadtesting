"""CrewAI + DeepSeek demo agent with a deterministic, archetype-friendly span shape.

Two deterministic turn types so the load driver can control the archetype mix the
workload-model skill will rediscover:

  * turn_type="tool" -> a task that requires the web_search / calculator tools (ReAct loop)
                        => the trace contains `execute_tool` spans  => Agentic archetype.
  * turn_type="chat" -> a pure-LLM question, no tools attached
                        => no `execute_tool` spans                  => Conversational archetype.

The DeepSeek backend is reached through CrewAI's LiteLLM-backed `LLM` using the
OpenAI-compatible endpoint (model `deepseek/deepseek-chat`, base_url https://api.deepseek.com).
"""
from __future__ import annotations

import os

from crewai import LLM, Agent, Crew, Process, Task
from opentelemetry import trace

from tools import build_tools

_tracer = trace.get_tracer("crewai-deepseek-agent")

DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek/deepseek-chat")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")


class TracedLLM(LLM):
    """CrewAI LLM subclass that wraps each model call in `llm.call -> chat` spans
    carrying gen_ai semconv attributes. Degrades gracefully if CrewAI changes the
    `.call()` signature across versions — the controllable request/turn/execute_tool/
    finalize spans (see run_turn / tools.py) remain correct regardless.
    """

    def call(self, *args, **kwargs):  # type: ignore[override]
        with _tracer.start_as_current_span("llm.call") as call_span:
            call_span.set_attribute("gen_ai.system", "deepseek")
            call_span.set_attribute("gen_ai.operation.name", "chat")
            with _tracer.start_as_current_span("chat") as chat_span:
                chat_span.set_attribute("gen_ai.system", "deepseek")
                chat_span.set_attribute("gen_ai.request.model", str(getattr(self, "model", DEEPSEEK_MODEL)))
                result = super().call(*args, **kwargs)
                # LiteLLM stashes last usage on the response/model; best-effort capture.
                usage = getattr(self, "_last_usage", None)
                if isinstance(usage, dict):
                    if "prompt_tokens" in usage:
                        chat_span.set_attribute("gen_ai.usage.input_tokens", int(usage["prompt_tokens"]))
                    if "completion_tokens" in usage:
                        chat_span.set_attribute("gen_ai.usage.output_tokens", int(usage["completion_tokens"]))
                return result


def _make_llm() -> LLM:
    return TracedLLM(
        model=DEEPSEEK_MODEL,
        base_url=DEEPSEEK_BASE_URL,
        api_key=os.environ["DEEPSEEK_API_KEY"],
        temperature=0.3,
    )


# Agents are cheap to build per request and keep each turn independent (no shared memory,
# so the arrival process is a clean sequence of turns — what the skill derives pace/CoV from).
def _tool_crew(llm: LLM, prompt: str) -> Crew:
    agent = Agent(
        role="Research assistant",
        goal="Answer the user's question, using tools when a fact or calculation is needed.",
        backstory="You are a careful assistant that looks things up and computes answers.",
        tools=build_tools(),
        llm=llm,
        verbose=False,
        max_iter=4,
    )
    task = Task(
        description=(
            "Use your tools to answer this request. If it mentions numbers or math, use the "
            "calculator; if it asks about facts, topics or 'latest', use web_search. "
            f"Request: {prompt}"
        ),
        expected_output="A concise answer grounded in tool output.",
        agent=agent,
    )
    return Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)


def _chat_crew(llm: LLM, prompt: str) -> Crew:
    agent = Agent(
        role="Conversational assistant",
        goal="Answer the user's question directly from your own knowledge.",
        backstory="You are a helpful assistant that answers briefly and clearly.",
        tools=[],  # no tools -> pure-LLM turn
        llm=llm,
        verbose=False,
        max_iter=1,
    )
    task = Task(
        description=f"Answer directly and concisely, without using any tools. Question: {prompt}",
        expected_output="A short, direct answer.",
        agent=agent,
    )
    return Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)


def run_turn(prompt: str, turn_type: str) -> str:
    """Execute one agent turn and emit the full span tree."""
    with _tracer.start_as_current_span(f"{os.getenv('OTEL_SERVICE_NAME', 'crewai-deepseek-agent')}/request") as req:
        req.set_attribute("agent.turn_type", turn_type)
        req.set_attribute("gen_ai.operation.name", "agent")
        with _tracer.start_as_current_span("agent.turn") as turn:
            turn.set_attribute("agent.turn_type", turn_type)
            llm = _make_llm()
            crew = _tool_crew(llm, prompt) if turn_type == "tool" else _chat_crew(llm, prompt)
            result = str(crew.kickoff())
            with _tracer.start_as_current_span("finalize") as fin:
                fin.set_attribute("agent.output_chars", len(result))
            with _tracer.start_as_current_span("message.sent") as msg:
                msg.set_attribute("agent.turn_type", turn_type)
            return result
