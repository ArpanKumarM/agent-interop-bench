import pytest

from app.models.execution import ToolCallDecision
from app.runner.adapters import DeterministicFakeAdapter, PlaceholderAdapter


async def test_deterministic_fake_adapter_returns_canned_decision():
    adapter = DeterministicFakeAdapter(
        {"add 1 and 2": ToolCallDecision(tool_name="calculate_sum", arguments={"a": 1, "b": 2})}
    )
    decision = await adapter.select_tool("add 1 and 2", available_tools=[])
    assert decision.tool_name == "calculate_sum"
    assert decision.arguments == {"a": 1, "b": 2}


async def test_deterministic_fake_adapter_raises_on_unknown_prompt():
    adapter = DeterministicFakeAdapter({})
    with pytest.raises(KeyError):
        await adapter.select_tool("unregistered prompt", available_tools=[])


async def test_placeholder_adapter_not_implemented():
    adapter = PlaceholderAdapter(model_name="claude-future")
    with pytest.raises(NotImplementedError):
        await adapter.select_tool("anything", available_tools=[])
