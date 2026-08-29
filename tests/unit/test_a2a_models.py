import pytest
from pydantic import ValidationError

from app.models.a2a import (
    A2AActionSpec,
    A2ABenchmarkCase,
    A2ABenchmarkSuite,
    A2ARemoteStep,
    AgentCard,
    AgentInterface,
    TaskState,
)

CARD = {
    "name": "test-agent",
    "supported_interfaces": [
        {"url": "http://mock", "protocol_binding": "HTTP_JSON", "protocol_version": "1.0"}
    ],
}


def make_case(**overrides) -> A2ABenchmarkCase:
    defaults = dict(
        id="a2a-x",
        category="a2a_correct_interaction",
        user_prompt="do something",
        expected_outcome="success",
        target_agent_card=CARD,
        simulated_remote_behavior=[{"task_state": "TASK_STATE_COMPLETED"}],
        simulated_client_actions=[{"action": "send_message", "content": "hi"}],
    )
    defaults.update(overrides)
    return A2ABenchmarkCase(**defaults)


def test_agent_card_requires_at_least_one_interface():
    with pytest.raises(ValidationError):
        AgentCard(name="x", supported_interfaces=[])


def test_agent_card_defaults_to_text_plain_modes():
    card = AgentCard(**CARD)
    assert card.default_input_modes == ["text/plain"]
    assert card.default_output_modes == ["text/plain"]


def test_task_state_values_are_v1_screaming_snake_case():
    assert TaskState.COMPLETED.value == "TASK_STATE_COMPLETED"
    assert TaskState.INPUT_REQUIRED.value == "TASK_STATE_INPUT_REQUIRED"


def test_a2a_benchmark_case_loads_with_defaults():
    case = make_case()
    assert case.max_interaction_steps == 1
    assert case.expected_task_state is None
    assert case.expected_client_action is None
    assert case.failure_mode == "normal"


def test_scripted_client_actions_cannot_exceed_turn_budget():
    with pytest.raises(ValidationError):
        make_case(
            max_interaction_steps=1,
            simulated_client_actions=[
                {"action": "send_message", "content": "a"},
                {"action": "get_task"},
            ],
        )


def test_a2a_benchmark_suite_rejects_duplicate_ids():
    with pytest.raises(ValidationError):
        A2ABenchmarkSuite(
            name="dup",
            version="0.1.0",
            cases=[make_case(id="same"), make_case(id="same")],
        )


def test_a2a_remote_step_and_action_spec_construct():
    step = A2ARemoteStep(task_state=TaskState.WORKING, remote_message_text="hello")
    assert step.task_state == TaskState.WORKING
    action = A2AActionSpec(action="send_message", content="hi", content_type="text/plain")
    assert action.action == "send_message"


def test_agent_interface_binding_literal_rejects_unknown_value():
    with pytest.raises(ValidationError):
        AgentInterface(url="http://mock", protocol_binding="SOAP", protocol_version="1.0")
