import pytest

from app.models.a2a import A2AActionSpec, A2ABenchmarkCase
from app.runner.a2a_adapters import DeterministicA2AAdapter

CARD = {
    "name": "test-agent",
    "supported_interfaces": [
        {"url": "http://mock", "protocol_binding": "HTTP_JSON", "protocol_version": "1.0"}
    ],
}


def make_case(case_id: str, max_steps: int = 2) -> A2ABenchmarkCase:
    return A2ABenchmarkCase(
        id=case_id,
        category="a2a_correct_interaction",
        user_prompt="do something",
        expected_outcome="success",
        max_interaction_steps=max_steps,
        target_agent_card=CARD,
        simulated_remote_behavior=[{"task_state": "TASK_STATE_WORKING"}] * max_steps,
        simulated_client_actions=[{"action": "send_message", "content": "hi"}],
    )


async def test_adapter_returns_scripted_steps_in_order():
    case = make_case("a2a-x", max_steps=2)
    adapter = DeterministicA2AAdapter(
        {
            "a2a-x": [
                A2AActionSpec(action="send_message", content="first"),
                A2AActionSpec(action="stop"),
            ]
        }
    )
    first = await adapter.decide_a2a(case, [])
    assert first.action == "send_message"
    assert first.content == "first"


async def test_adapter_stops_when_script_exhausted():
    case = make_case("a2a-x", max_steps=2)
    adapter = DeterministicA2AAdapter(
        {"a2a-x": [A2AActionSpec(action="send_message", content="only")]}
    )
    second = await adapter.decide_a2a(case, [object()])  # one prior step already taken
    assert second.action == "stop"


async def test_adapter_raises_for_unknown_case():
    case = make_case("unregistered")
    adapter = DeterministicA2AAdapter({})
    with pytest.raises(KeyError):
        await adapter.decide_a2a(case, [])
