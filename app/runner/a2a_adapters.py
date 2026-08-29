"""A2A agent adapter interface: decouples the A2A runner from any specific
client-agent implementation. Deliberately separate from
``app.runner.adapters.AgentAdapter`` (MCP's tool-call-shaped interface) —
see the Phase 3A/3B.0 architecture audit for why widening one interface into
a union of both protocols was rejected.

``DeterministicA2AAdapter`` is the only adapter Phase 3B ships: a fixture
that replays a case's ``simulated_client_actions`` script, exactly the role
``DeterministicFakeAdapter`` plays for MCP. A live A2A client adapter
(measuring a real agent's real delegation behavior) is explicitly future
work, not Phase 3B.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.models.a2a import A2AActionSpec, A2ABenchmarkCase, A2AInteractionRecord


class A2AAgentAdapter(ABC):
    """Decides the next client-side A2A action, given the interaction so far."""

    @abstractmethod
    async def decide_a2a(
        self,
        case: A2ABenchmarkCase,
        history: list[A2AInteractionRecord],
    ) -> A2AActionSpec:
        """Return the next action. ``action="stop"`` means voluntarily done.

        ``history`` is empty on the first call for a case, and holds every
        prior ``A2AInteractionRecord`` on later calls.
        """
        ...


class DeterministicA2AAdapter(A2AAgentAdapter):
    """A fixture-driven adapter for automated tests: no model, no network.

    Behavior is a fixed lookup table from case ID to an ordered script of
    canned ``A2AActionSpec``s — one per step. Running out of scripted steps
    is reported as a voluntary stop, matching ``DeterministicFakeAdapter``'s
    behavior for MCP.
    """

    def __init__(self, scripts: dict[str, list[A2AActionSpec]]) -> None:
        self._scripts = scripts

    async def decide_a2a(
        self,
        case: A2ABenchmarkCase,
        history: list[A2AInteractionRecord],
    ) -> A2AActionSpec:
        script = self._scripts.get(case.id)
        if script is None:
            raise KeyError(f"DeterministicA2AAdapter has no canned script for case: {case.id!r}")

        step_index = len(history)
        if step_index >= len(script):
            return A2AActionSpec(action="stop")
        return script[step_index]


def build_a2a_fixture_adapter(suite) -> DeterministicA2AAdapter:  # noqa: ANN001
    """Build a DeterministicA2AAdapter from a suite's fixture scripts."""
    scripts = {case.id: list(case.simulated_client_actions) for case in suite.cases}
    return DeterministicA2AAdapter(scripts)
