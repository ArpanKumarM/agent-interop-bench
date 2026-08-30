"""Phase 4A.2: one full, MOCKED composed trial proving

    mock provider decision(s) -> RealHostAgentAdapter -> ComposedBenchmarkRunner
    -> real MCP/A2A mock protocols -> unified CrossProtocolEvent trace

No real model is ever called. The provider is a hand-rolled fake
(``ResponsesClient`` Protocol), but every layer beneath it — the adapter,
the composed runner, the local MCP stdio transport, the A2A in-process
mock — is the real, unmodified production code path also exercised by the
deterministic composed suite.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

from app.core.live_overlays import load_live_overlays
from app.models.live_overlay import overlay_to_composed_case
from app.runner.composed_engine import ComposedBenchmarkRunner
from app.runner.mutation_gate import mutation_blocked
from app.runner.real_host_adapter import RealHostAgentAdapter
from tests.integration.test_composed_engine import make_composed_tool_transport

OVERLAYS_PATH = "benchmarks/composed/live_overlays.yaml"


class FakeResponsesClient:
    def __init__(self, responses: list):
        self._responses = list(responses)
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._responses.pop(0)


def _function_call(name, arguments, call_id="call_1"):
    return SimpleNamespace(
        type="function_call", name=name, arguments=json.dumps(arguments), call_id=call_id
    )


def _response(output, response_id="resp_1"):
    return SimpleNamespace(id=response_id, model="gpt-test", output=output, usage=None)


def _load_overlay(overlay_id: str):
    suite = load_live_overlays(OVERLAYS_PATH)
    (overlay,) = [o for o in suite.overlays if o.id == overlay_id]
    return overlay


async def test_mocked_trial_influence_treatment_proposes_and_gate_blocks_mutation():
    """The mock provider decides: relay to remote, observe the (realistic,
    natural-language) adversarial artifact, then attempt the mutating tool.
    The real mutation gate blocks it -- exactly like the deterministic
    scripted case -- because the model can never grant its own approval."""
    overlay = _load_overlay("live-influence-treatment")
    case = overlay_to_composed_case(overlay)

    client = FakeResponsesClient(
        [
            _response(
                [
                    _function_call(
                        "relay_to_remote",
                        {"content": "Any recommendation?", "content_type": "text/plain"},
                    )
                ]
            ),
            _response(
                [
                    _function_call(
                        "attempt_mutating_tool",
                        {
                            "tool_name": "apply_remote_recommendation",
                            "tool_arguments_json": json.dumps({"action": "apply pending fix"}),
                        },
                    )
                ]
            ),
            _response([_function_call("stop", {})]),
        ]
    )
    adapter = RealHostAgentAdapter(client, model="gpt-test", case_id=case.id)

    events = await ComposedBenchmarkRunner(
        local_transport_factory=make_composed_tool_transport, adapter=adapter
    ).run_case(case)

    event_types = [event.event_type for event in events]
    assert event_types == [
        "a2a_message",
        "a2a_task_state_transition",
        "a2a_artifact",
        "mutation_action",
    ]

    artifact = next(e for e in events if e.event_type == "a2a_artifact")
    mutation = next(e for e in events if e.event_type == "mutation_action")

    # The realistic artifact text is present verbatim -- no ACTION_TRIGGER marker.
    assert "emergency remediation" in artifact.payload["text"]
    assert "ACTION_TRIGGER" not in artifact.payload["text"]

    # The mutation gate really ran: is_mutating discovered from the real
    # apply_remote_recommendation tool's annotation, approved forced False by
    # the adapter, and mutation_blocked(True, False) is True -- blocked.
    assert mutation.is_mutating is True
    assert mutation.approved is False
    assert mutation.executed is False
    assert mutation_blocked(is_mutating=True, approved=False) is True

    assert len(client.calls) == 3
    assert adapter.provenance.total_provider_calls == 3


async def test_mocked_trial_influence_control_never_attempts_mutation():
    overlay = _load_overlay("live-influence-control")
    case = overlay_to_composed_case(overlay)

    client = FakeResponsesClient(
        [
            _response(
                [
                    _function_call(
                        "relay_to_remote",
                        {"content": "Any recommendation?", "content_type": "text/plain"},
                    )
                ]
            ),
            _response([_function_call("stop", {})]),
        ]
    )
    adapter = RealHostAgentAdapter(client, model="gpt-test", case_id=case.id)

    events = await ComposedBenchmarkRunner(
        local_transport_factory=make_composed_tool_transport, adapter=adapter
    ).run_case(case)

    assert "mutation_action" not in [event.event_type for event in events]
    artifact = next(e for e in events if e.event_type == "a2a_artifact")
    assert "no action needed" in artifact.payload["text"].lower()
