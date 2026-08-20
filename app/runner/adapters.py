"""Agent adapter interface: decouples the runner from any specific LLM provider.

An ``AgentAdapter`` is given a user prompt, the tools discovered from the MCP
server, and the turns taken so far in this case's interaction (empty on the
first call), and must decide what to do next: call a tool, or stop. The
runner never inspects benchmark ground truth when calling an adapter, so any
adapter implementation — deterministic fixture, or a real model — plugs in
the same way, and the same ``decide`` method drives every turn up to a
case's ``max_turns`` bound.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.models.execution import ToolCallDecision, TurnResult
from app.models.tools import ToolDefinition


class AgentAdapter(ABC):
    """Decides what to do next, given the interaction so far."""

    @abstractmethod
    async def decide(
        self,
        prompt: str,
        available_tools: list[ToolDefinition],
        history: list[TurnResult],
    ) -> ToolCallDecision:
        """Return the next decision. ``tool_name=None`` means stop.

        ``history`` is empty on the first call for a case, and holds every
        prior ``TurnResult`` (including its tool output) on later calls, so
        an adapter that wants to react to what a tool returned can inspect
        ``history[-1].raw_text_output``.
        """
        ...


class DeterministicFakeAdapter(AgentAdapter):
    """A fixture-driven adapter for automated tests: no model, no network, no API key.

    Behavior is a fixed lookup table from user prompt to an ordered script of
    canned ``ToolCallDecision``s — one per turn. This lets benchmark cases
    declare exactly what a (possibly flawed) agent does at each turn,
    deterministically and reproducibly: "correct" behavior, wrong tool
    choices, hallucinated tools, missing/malformed arguments, or reacting to
    (and potentially being hijacked by) a prior turn's tool output.

    Running out of scripted turns for a prompt (the common case: most
    scripts have exactly one entry) is reported as a voluntary stop, not an
    error — from the runner's perspective that's indistinguishable from a
    real adapter that decided it was done.
    """

    def __init__(self, scripts: dict[str, list[ToolCallDecision]]) -> None:
        self._scripts = scripts

    async def decide(
        self,
        prompt: str,
        available_tools: list[ToolDefinition],
        history: list[TurnResult],
    ) -> ToolCallDecision:
        script = self._scripts.get(prompt)
        if script is None:
            raise KeyError(f"DeterministicFakeAdapter has no canned script for prompt: {prompt!r}")

        turn_index = len(history)
        if turn_index >= len(script):
            return ToolCallDecision(tool_name=None)
        return script[turn_index]


class PlaceholderAdapter(AgentAdapter):
    """Interface stub for a future real-model adapter (Claude, OpenAI, ...).

    Not implemented in Phase 1. All benchmark execution and CI must be able
    to run without this adapter, and without any API key.
    """

    def __init__(self, model_name: str) -> None:
        self._model_name = model_name

    async def decide(
        self,
        prompt: str,
        available_tools: list[ToolDefinition],
        history: list[TurnResult],
    ) -> ToolCallDecision:
        raise NotImplementedError(
            f"PlaceholderAdapter('{self._model_name}') is not implemented in Phase 1. "
            "A future phase will wire this to a real model API."
        )
