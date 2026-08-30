"""Deterministic A2A benchmark runner: a bounded decide -> call -> observe
loop, structurally analogous to ``app.runner.engine.BenchmarkRunner`` but
operating on A2A's task/message lifecycle instead of MCP tool calls.

Not a ``Transport``/``BenchmarkRunner`` subtype and shares no code with
them — see the Phase 3A/3B.0 architecture audit for why a shared generic
MCP/A2A interaction abstraction was deliberately not built.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.models.a2a import (
    A2ABenchmarkCase,
    A2AInteractionRecord,
    Message,
    Part,
    Task,
    TaskState,
    deterministic_id,
)
from app.runner.a2a_adapters import A2AAgentAdapter

_TERMINAL_CLASSIFICATION_BY_STATE = {
    TaskState.COMPLETED: "completed",
    TaskState.FAILED: "failed",
    TaskState.CANCELED: "canceled",
    TaskState.REJECTED: "rejected",
}


class A2ABenchmarkRunner:
    """Executes A2A benchmark cases against a connected mock agent client."""

    def __init__(self, client: TestClient, adapter: A2AAgentAdapter) -> None:
        self._client = client
        self._adapter = adapter

    async def run_case(self, case: A2ABenchmarkCase) -> list[A2AInteractionRecord]:
        interactions: list[A2AInteractionRecord] = []
        task_id: str | None = None

        for step_index in range(case.max_interaction_steps):
            action = await self._adapter.decide_a2a(case, interactions)

            if action.action == "stop":
                interactions.append(
                    A2AInteractionRecord(
                        step_index=step_index,
                        client_action="stop",
                        task_id=task_id,
                        termination_classification="stopped",
                    )
                )
                break

            record, task_id, terminal = self._dispatch(case.id, step_index, action, task_id)
            interactions.append(record)
            if terminal:
                break
        else:
            if interactions and interactions[-1].termination_classification == "in_progress":
                interactions[-1] = interactions[-1].model_copy(
                    update={"termination_classification": "step_limit_reached"}
                )

        return interactions

    def _dispatch(self, case_id, step_index, action, task_id):  # noqa: ANN001
        if action.action == "send_message":
            return self._send_message(case_id, step_index, action, task_id)
        if action.action == "get_task":
            return self._get_task(step_index, task_id)
        if action.action == "cancel_task":
            return self._cancel_task(step_index, task_id)
        raise ValueError(f"Unknown A2A action: {action.action!r}")

    def _send_message(self, case_id, step_index, action, task_id):  # noqa: ANN001
        message_id = deterministic_id(case_id, "client-message", str(step_index))
        outgoing = Message(
            message_id=message_id,
            role="ROLE_USER",
            parts=[Part(content_type=action.content_type, text=action.content or "")],
            task_id=task_id,
        )
        # by_alias=True: the wire body is v1.0's camelCase shape
        # (messageId, taskId, contentType, ...) -- see app/models/a2a.py.
        body = {"message": outgoing.model_dump(by_alias=True)}
        response = self._client.post("/message:send", json=body)
        return self._record_from_response(
            step_index, "send_message", "SendMessage", response, message_id, action.content
        )

    def _get_task(self, step_index, task_id):  # noqa: ANN001
        response = self._client.get(f"/tasks/{task_id}")
        return self._record_from_response(step_index, "get_task", "GetTask", response, None, None)

    def _cancel_task(self, step_index, task_id):  # noqa: ANN001
        response = self._client.post(f"/tasks/{task_id}:cancel")
        return self._record_from_response(
            step_index, "cancel_task", "CancelTask", response, None, None
        )

    def _record_from_response(  # noqa: ANN001
        self, step_index, client_action, protocol_operation, response, message_id, request_content
    ):
        if response.status_code >= 400:
            detail = response.json().get("detail", {})
            record = A2AInteractionRecord(
                step_index=step_index,
                client_action=client_action,
                protocol_operation=protocol_operation,
                request_message_id=message_id,
                request_content=request_content,
                task_id=None,
                protocol_error={
                    "reason": detail.get("reason", "UNKNOWN"),
                    "http_status": response.status_code,
                    **{k: v for k, v in detail.items() if k != "reason"},
                },
                termination_classification="rejected",
            )
            return record, None, True

        # Task.model_validate accepts the wire's camelCase body directly
        # (populate_by_name=True means it would also accept snake_case, but
        # the mock always emits camelCase -- see app/models/a2a.py).
        task = Task.model_validate(response.json())
        observed_state = task.status.state
        remote_message = task.history[-1] if task.history else None

        terminal = observed_state in _TERMINAL_CLASSIFICATION_BY_STATE
        classification = _TERMINAL_CLASSIFICATION_BY_STATE.get(observed_state, "in_progress")

        record = A2AInteractionRecord(
            step_index=step_index,
            client_action=client_action,
            protocol_operation=protocol_operation,
            request_message_id=message_id,
            request_content=request_content,
            task_id=task.id,
            context_id=task.context_id,
            observed_task_state=observed_state,
            remote_message=remote_message,
            artifacts=task.artifacts,
            termination_classification=classification,
        )
        return record, task.id, terminal
