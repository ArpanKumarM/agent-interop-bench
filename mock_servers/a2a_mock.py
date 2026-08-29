"""A deterministic, local, in-process A2A v1.0 remote agent (HTTP+JSON/REST
binding). Never contacts a real agent or the network — the FastAPI app
built here is exercised entirely through ``fastapi.testclient.TestClient``,
matching this project's own API test style (no sockets).

Routes implement the real HTTP+JSON binding shapes so a request/response
round-trip through this app validates the same JSON structures a real A2A
server would produce (a benchmark author's script only controls the
*content* of each response, never the wire shape):

    GET  /.well-known/agent-card.json
    POST /message:send
    GET  /tasks/{id}
    POST /tasks/{id}:cancel

Behavior is scripted per case via an ordered ``list[A2ARemoteStep]``: the
Nth client request (of any kind) is answered by ``script[N]`` — the same
"script indexed by call order" discipline ``DeterministicFakeAdapter`` uses
for MCP, applied to the server side of the interaction instead.
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request

from app.models.a2a import (
    TERMINAL_TASK_STATES,
    A2ARemoteStep,
    AgentCard,
    Artifact,
    Message,
    Part,
    TaskState,
    deterministic_id,
)


class _MockTaskState:
    def __init__(self) -> None:
        self.task_id: str | None = None
        self.context_id: str | None = None
        self.state: TaskState = TaskState.SUBMITTED
        self.history: list[Message] = []
        self.artifacts: list[Artifact] = []


def build_a2a_mock_app(agent_card: AgentCard, script: list[A2ARemoteStep], case_id: str) -> FastAPI:
    """Build (but don't serve) a fresh mock A2A agent for one case run.

    A new app/state pair per case run, mirroring how MCP's mock server
    process is spawned fresh per suite execution — no state leaks between
    cases or between runs of the same case.

    ``case_id`` seeds every generated identifier (task/context/message IDs)
    via ``deterministic_id`` so two runs of the same case produce byte-
    identical IDs, not just byte-identical scores -- the A2A analogue of
    MCP having no randomness anywhere in its execution path.
    """
    app = FastAPI()
    state = _MockTaskState()
    call_index = {"value": 0}

    def _next_step() -> A2ARemoteStep:
        idx = call_index["value"]
        call_index["value"] += 1
        if idx >= len(script):
            raise HTTPException(
                status_code=500,
                detail=(
                    f"Mock A2A agent's script exhausted at call {idx} "
                    f"(script has {len(script)} steps)"
                ),
            )
        return script[idx]

    @app.get("/.well-known/agent-card.json")
    def get_agent_card() -> dict:
        return agent_card.model_dump(by_alias=False)

    @app.post("/message:send")
    async def send_message(request: Request) -> dict:
        body = await request.json()
        message = body.get("message", {})
        parts = message.get("parts", [])
        for part in parts:
            content_type = part.get("content_type", "text/plain")
            if content_type not in agent_card.default_input_modes:
                raise HTTPException(
                    status_code=415,
                    detail={
                        "reason": "CONTENT_TYPE_NOT_SUPPORTED",
                        "domain": "a2a-protocol.org",
                        "unsupported_content_type": content_type,
                        "declared_input_modes": agent_card.default_input_modes,
                    },
                )

        if state.task_id is None:
            state.task_id = deterministic_id(case_id, "task")
            state.context_id = deterministic_id(case_id, "context")

        step_number = call_index["value"]
        step = _next_step()
        state.state = step.task_state
        if step.remote_message_text is not None:
            remote_message = Message(
                message_id=deterministic_id(case_id, "remote-message", str(step_number)),
                role="ROLE_AGENT",
                parts=[Part(text=step.remote_message_text)],
                task_id=state.task_id,
                context_id=state.context_id,
            )
            state.history.append(remote_message)
        if step.artifact_text is not None:
            state.artifacts.append(Artifact(parts=[Part(text=step.artifact_text)]))

        return _task_response(state)

    @app.get("/tasks/{task_id}")
    def get_task(task_id: str) -> dict:
        if state.task_id is None or task_id != state.task_id:
            raise HTTPException(status_code=404, detail={"reason": "TASK_NOT_FOUND"})

        step_number = call_index["value"]
        step = _next_step()
        state.state = step.task_state
        if step.remote_message_text is not None:
            state.history.append(
                Message(
                    message_id=deterministic_id(case_id, "remote-message", str(step_number)),
                    role="ROLE_AGENT",
                    parts=[Part(text=step.remote_message_text)],
                    task_id=state.task_id,
                    context_id=state.context_id,
                )
            )
        if step.artifact_text is not None:
            state.artifacts.append(Artifact(parts=[Part(text=step.artifact_text)]))

        return _task_response(state)

    @app.post("/tasks/{task_id}:cancel")
    def cancel_task(task_id: str) -> dict:
        if state.task_id is None or task_id != state.task_id:
            raise HTTPException(status_code=404, detail={"reason": "TASK_NOT_FOUND"})
        if state.state in TERMINAL_TASK_STATES:
            raise HTTPException(status_code=409, detail={"reason": "TASK_NOT_CANCELABLE"})

        step = _next_step()
        state.state = step.task_state
        return _task_response(state)

    return app


def _task_response(state: _MockTaskState) -> dict:
    return {
        "id": state.task_id,
        "context_id": state.context_id,
        "status": {"state": state.state.value},
        "artifacts": [a.model_dump() for a in state.artifacts],
        "history": [m.model_dump() for m in state.history],
    }
