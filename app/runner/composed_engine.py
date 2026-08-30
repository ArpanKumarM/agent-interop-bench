"""Cross-protocol composed benchmark runner (Phase 3D.1).

Deliberately does NOT call ``BenchmarkRunner.run_case`` or
``A2ABenchmarkRunner.run_case``: those two runners stay completely
untouched and independently valid. ``ComposedBenchmarkRunner`` instead
drives the lowest existing protocol primitives directly --
``MCPTransport.call_tool`` for the local MCP leg, and a direct
``TestClient`` call against the same mock A2A agent app
(``mock_servers.a2a_mock.build_a2a_mock_app``) for the A2A leg, using the
same ``Message``/``Part``/``Task`` wire models ``a2a_engine.py`` already
uses -- so that a host's actions can interleave across both protocols
within a single ordered event trace, which calling either existing
``run_case`` as an opaque black box would prevent.

No chain-of-thought or adapter rationale is ever read: every
``CrossProtocolEvent`` this runner emits is built only from the request/
response data that actually crossed a protocol boundary.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from fastapi.testclient import TestClient

from app.models.a2a import Message, Part, Task
from app.models.composed import (
    Actor,
    ComposedBenchmarkCase,
    CrossProtocolEvent,
    canary_token,
    composed_deterministic_id,
    default_origin_trust,
)
from app.runner.transport import MCPTransport
from mock_servers.a2a_mock import build_a2a_mock_app

LOCAL_MCP_CALL_TIMEOUT_SECONDS = 10.0


def _substitute(text: str, case: ComposedBenchmarkCase, tool_result_text: str | None) -> str:
    """Plain string substitution only -- no templating logic, no conditionals.

    ``{canary:NAME}`` becomes that named canary's literal token;
    ``{tool_result_text}`` becomes the most recent local MCP tool result's
    text output verbatim, exactly what a host relaying a tool's output into
    an outgoing message would do.
    """
    result = text
    if tool_result_text is not None:
        result = result.replace("{tool_result_text}", tool_result_text)
    for canary in case.provenance_canaries:
        result = result.replace(f"{{canary:{canary.name}}}", canary_token(case.id, canary.name))
    return result


def _substitute_arguments(arguments: dict[str, Any], case: ComposedBenchmarkCase) -> dict[str, Any]:
    substituted: dict[str, Any] = {}
    for key, value in arguments.items():
        if isinstance(value, str):
            substituted[key] = _substitute(value, case, tool_result_text=None)
        else:
            substituted[key] = value
    return substituted


class ComposedBenchmarkRunner:
    """Executes one composed benchmark case, emitting a single ordered,
    DAG-validated ``list[CrossProtocolEvent]`` spanning both protocols."""

    def __init__(self, local_transport_factory: Callable[[], MCPTransport]) -> None:
        self._local_transport_factory = local_transport_factory
        self._events: list[CrossProtocolEvent] = []
        self._by_id: dict[str, CrossProtocolEvent] = {}

    def _append(
        self,
        case: ComposedBenchmarkCase,
        *,
        event_type: str,
        source: Actor,
        dest: Actor,
        protocol: str,
        payload: dict[str, Any],
        parent_event_ids: list[str],
        is_mutating: bool = False,
        approved: bool | None = None,
        executed: bool | None = None,
    ) -> CrossProtocolEvent:
        seq = len(self._events)

        for parent_id in parent_event_ids:
            parent = self._by_id.get(parent_id)
            if parent is None:
                raise ValueError(
                    f"Composed event DAG violation: parent_event_id {parent_id!r} does not "
                    "exist in this case's trace yet."
                )
            if not parent.seq < seq:
                raise ValueError(
                    f"Composed event DAG violation: parent {parent_id!r} has seq "
                    f"{parent.seq} >= new event's seq {seq}."
                )

        event_id = composed_deterministic_id(case.id, "event", str(seq))

        origin_trust = case.origin_trust_overrides.get(event_type, default_origin_trust(source))
        content_class = case.content_class_overrides.get(event_type, "non_adversarial")

        haystack = json.dumps(payload, default=str, sort_keys=True, ensure_ascii=False)
        canary_ids: list[str] = []
        sensitivity: str = "public"
        for canary in case.provenance_canaries:
            token = canary_token(case.id, canary.name)
            if token in haystack:
                canary_ids.append(composed_deterministic_id(case.id, "canary", canary.name))
                if canary.sensitivity == "sensitive":
                    sensitivity = "sensitive"

        parents = [self._by_id[pid] for pid in parent_event_ids]
        adversarial_ancestor_ids = sorted(
            {
                ancestor_id
                for parent in parents
                for ancestor_id in (
                    parent.adversarial_ancestor_ids
                    + (
                        [parent.event_id]
                        if parent.origin_trust == "untrusted"
                        and parent.content_class == "adversarial"
                        else []
                    )
                )
            }
        )
        sensitive_ancestor_ids = sorted(
            {
                ancestor_id
                for parent in parents
                for ancestor_id in (
                    parent.sensitive_ancestor_ids
                    + ([parent.event_id] if parent.sensitivity == "sensitive" else [])
                )
            }
        )
        propagated_canary_ids = sorted(
            set(canary_ids) | {cid for parent in parents for cid in parent.propagated_canary_ids}
        )

        event = CrossProtocolEvent(
            event_id=event_id,
            parent_event_ids=parent_event_ids,
            case_id=case.id,
            seq=seq,
            event_type=event_type,
            source=source,
            dest=dest,
            protocol=protocol,
            payload=payload,
            origin_trust=origin_trust,
            content_class=content_class,
            sensitivity=sensitivity,
            canary_ids=canary_ids,
            adversarial_ancestor_ids=adversarial_ancestor_ids,
            sensitive_ancestor_ids=sensitive_ancestor_ids,
            propagated_canary_ids=propagated_canary_ids,
            is_mutating=is_mutating,
            approved=approved,
            executed=executed,
        )
        self._events.append(event)
        self._by_id[event_id] = event
        return event

    async def run_case(self, case: ComposedBenchmarkCase) -> list[CrossProtocolEvent]:
        self._events = []
        self._by_id = {}

        # Canary placeholders in the case's own scripted remote-agent fixture
        # (e.g. artifact_text) are substituted here, before the mock app is
        # built -- so a fixture author can declare "the remote agent's
        # artifact echoes this canary back" using the same {canary:NAME}
        # syntax as host actions, without hand-computing the deterministic
        # token's UUID and pasting it into YAML.
        substituted_remote_behavior = [
            step.model_copy(
                update={
                    "remote_message_text": (
                        _substitute(step.remote_message_text, case, tool_result_text=None)
                        if step.remote_message_text is not None
                        else None
                    ),
                    "artifact_text": (
                        _substitute(step.artifact_text, case, tool_result_text=None)
                        if step.artifact_text is not None
                        else None
                    ),
                }
            )
            for step in case.simulated_remote_behavior
        ]
        mock_app = build_a2a_mock_app(case.target_agent_card, substituted_remote_behavior, case.id)

        last_event: CrossProtocolEvent | None = None
        last_tool_result_text: str | None = None

        with TestClient(mock_app) as client:
            for action in case.simulated_host_actions[: case.max_interaction_steps]:
                if action.action == "stop":
                    break

                if action.action == "call_local_tool":
                    arguments = _substitute_arguments(action.tool_arguments, case)
                    request_event = self._append(
                        case,
                        event_type="mcp_tool_request",
                        source="host",
                        dest="local_tool",
                        protocol="mcp",
                        payload={"tool_name": action.tool_name, "arguments": arguments},
                        parent_event_ids=[last_event.event_id] if last_event else [],
                    )
                    async with self._local_transport_factory() as transport:
                        outcome = await transport.call_tool(
                            action.tool_name or "",
                            arguments,
                            timeout_seconds=LOCAL_MCP_CALL_TIMEOUT_SECONDS,
                        )
                    last_tool_result_text = outcome.text_output
                    result_event = self._append(
                        case,
                        event_type="mcp_tool_result",
                        source="local_tool",
                        dest="host",
                        protocol="mcp",
                        payload={
                            "text_output": outcome.text_output,
                            "structured_output": outcome.structured_output,
                            "is_error": outcome.is_error,
                        },
                        parent_event_ids=[request_event.event_id],
                    )
                    last_event = result_event

                elif action.action == "relay_to_remote":
                    text = _substitute(
                        action.relay_template or "", case, tool_result_text=last_tool_result_text
                    )
                    message_id = composed_deterministic_id(
                        case.id, "client-message", str(len(self._events))
                    )
                    outgoing = Message(
                        message_id=message_id,
                        role="ROLE_USER",
                        parts=[Part(content_type=action.content_type, text=text)],
                    )
                    message_event = self._append(
                        case,
                        event_type="a2a_message",
                        source="host",
                        dest="remote",
                        protocol="a2a",
                        payload={"role": "ROLE_USER", "text": text},
                        parent_event_ids=[last_event.event_id] if last_event else [],
                    )
                    response = client.post(
                        "/message:send", json={"message": outgoing.model_dump(by_alias=True)}
                    )
                    task = Task.model_validate(response.json())
                    transition_event = self._append(
                        case,
                        event_type="a2a_task_state_transition",
                        source="remote",
                        dest="host",
                        protocol="a2a",
                        payload={"to_state": task.status.state.value},
                        parent_event_ids=[message_event.event_id],
                    )
                    last_event = transition_event
                    if task.artifacts:
                        artifact_text = "\n".join(
                            part.text for part in task.artifacts[-1].parts if part.text
                        )
                        last_event = self._append(
                            case,
                            event_type="a2a_artifact",
                            source="remote",
                            dest="host",
                            protocol="a2a",
                            payload={"text": artifact_text},
                            parent_event_ids=[transition_event.event_id],
                        )

        return list(self._events)
