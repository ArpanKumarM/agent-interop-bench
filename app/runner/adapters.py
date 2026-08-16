"""Agent adapter interface: decouples the runner from any specific LLM provider.

An ``AgentAdapter`` is given a user prompt and the tools discovered from the
MCP server, and must decide which tool (if any) to call and with what
arguments. The runner never inspects benchmark ground truth when calling an
adapter, so any adapter implementation — deterministic fixture, or a real
model — plugs in the same way.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.models.execution import ToolCallDecision
from app.models.tools import ToolDefinition


class AgentAdapter(ABC):
    """Decides which tool to call for a given prompt."""

    @abstractmethod
    async def select_tool(
        self, prompt: str, available_tools: list[ToolDefinition]
    ) -> ToolCallDecision: ...


class DeterministicFakeAdapter(AgentAdapter):
    """A fixture-driven adapter for automated tests: no model, no network, no API key.

    Behavior is a fixed lookup table from user prompt to a canned
    ``ToolCallDecision``, built from the benchmark suite's
    ``simulated_agent_response`` fields. This lets benchmark cases declare
    exactly what a (possibly flawed) agent does, deterministically and
    reproducibly, including "correct" behavior, wrong tool choices,
    hallucinated tools, or missing/malformed arguments.
    """

    def __init__(self, responses: dict[str, ToolCallDecision]) -> None:
        self._responses = responses

    async def select_tool(
        self, prompt: str, available_tools: list[ToolDefinition]
    ) -> ToolCallDecision:
        decision = self._responses.get(prompt)
        if decision is None:
            raise KeyError(
                f"DeterministicFakeAdapter has no canned response for prompt: {prompt!r}"
            )
        return decision


class PlaceholderAdapter(AgentAdapter):
    """Interface stub for a future real-model adapter (Claude, OpenAI, ...).

    Not implemented in Phase 1. All benchmark execution and CI must be able
    to run without this adapter, and without any API key.
    """

    def __init__(self, model_name: str) -> None:
        self._model_name = model_name

    async def select_tool(
        self, prompt: str, available_tools: list[ToolDefinition]
    ) -> ToolCallDecision:
        raise NotImplementedError(
            f"PlaceholderAdapter('{self._model_name}') is not implemented in Phase 1. "
            "A future phase will wire this to a real model API."
        )
