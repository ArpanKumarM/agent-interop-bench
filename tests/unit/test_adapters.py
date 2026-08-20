import pytest

from app.models.execution import ToolCallDecision, TurnResult
from app.runner.adapters import DeterministicFakeAdapter, PlaceholderAdapter


async def test_deterministic_fake_adapter_returns_canned_decision():
    adapter = DeterministicFakeAdapter(
        {"add 1 and 2": [ToolCallDecision(tool_name="calculate_sum", arguments={"a": 1, "b": 2})]}
    )
    decision = await adapter.decide("add 1 and 2", available_tools=[], history=[])
    assert decision.tool_name == "calculate_sum"
    assert decision.arguments == {"a": 1, "b": 2}


async def test_deterministic_fake_adapter_raises_on_unknown_prompt():
    adapter = DeterministicFakeAdapter({})
    with pytest.raises(KeyError):
        await adapter.decide("unregistered prompt", available_tools=[], history=[])


async def test_placeholder_adapter_not_implemented():
    adapter = PlaceholderAdapter(model_name="claude-future")
    with pytest.raises(NotImplementedError):
        await adapter.decide("anything", available_tools=[], history=[])


async def test_deterministic_fake_adapter_stops_when_script_is_exhausted():
    """A one-entry script (the common case) makes the adapter stop on turn 2+."""
    adapter = DeterministicFakeAdapter(
        {"add 1 and 2": [ToolCallDecision(tool_name="calculate_sum", arguments={"a": 1, "b": 2})]}
    )
    first = await adapter.decide("add 1 and 2", available_tools=[], history=[])
    assert first.tool_name == "calculate_sum"

    # Simulate the runner calling decide() again with turn 0 already in history.
    history = [TurnResult(turn_index=0, requested_tool="calculate_sum", executed=True)]
    second = await adapter.decide("add 1 and 2", available_tools=[], history=history)
    assert second.tool_name is None


async def test_deterministic_fake_adapter_returns_scripted_reaction():
    adapter = DeterministicFakeAdapter(
        {
            "search issues": [
                ToolCallDecision(tool_name="search_issues", arguments={}),
                ToolCallDecision(tool_name=None),
            ]
        }
    )
    history = [TurnResult(turn_index=0, requested_tool="search_issues", executed=True)]
    reaction = await adapter.decide("search issues", available_tools=[], history=history)
    assert reaction.tool_name is None
