"""FastAPI front-end for the CrewAI + DeepSeek demo agent app.

One endpoint, POST /request, runs a single agent turn and returns the answer. The load
driver (../loadgen/driver.js) hits this with a controlled mix of
turn_type=tool and turn_type=chat to drive the two behavioral archetypes.

Tracing is initialised before the agent module imports its tracer so spans land on the
installed provider.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from otel_setup import init_tracing, shutdown_tracing

init_tracing()  # must run before `agent`/`tools` grab their tracer

from fastapi import FastAPI  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from agent import run_turn  # noqa: E402


class TurnRequest(BaseModel):
    prompt: str
    turn_type: str = "chat"  # "tool" | "chat"


class TurnResponse(BaseModel):
    answer: str
    turn_type: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    shutdown_tracing()


app = FastAPI(title="crewai-deepseek-agent", lifespan=lifespan)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.post("/request", response_model=TurnResponse)
def handle_request(req: TurnRequest):
    turn_type = req.turn_type if req.turn_type in ("tool", "chat") else "chat"
    answer = run_turn(req.prompt, turn_type)
    return TurnResponse(answer=answer, turn_type=turn_type)
