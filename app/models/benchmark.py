"""Benchmark case schema: deterministic, declarative test definitions."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.models.enums import BenchmarkCategory, ExpectedOutcome, FailureMode


class SimulatedAgentResponse(BaseModel):
    """What the deterministic fake adapter will output for a given benchmark case.

    This is fixture data describing the *simulated agent's* (possibly flawed)
    behavior, kept separate from ``expected_tool``/``expected_arguments`` which
    describe the *ground truth* a correct agent should have produced. Negative
    test cases (wrong tool, hallucinated tool, missing args, ...) set this to
    the flawed behavior under test.
    """

    tool_name: str | None = None
    arguments: dict[str, Any] = Field(default_factory=dict)


class BenchmarkCase(BaseModel):
    """A single deterministic MCP reliability/security test case."""

    id: str
    category: BenchmarkCategory
    user_prompt: str
    expected_tool: str | None = None
    expected_arguments: dict[str, Any] = Field(default_factory=dict)
    simulated_failure_mode: FailureMode = FailureMode.NORMAL
    expected_outcome: ExpectedOutcome
    max_latency_ms: int = 2000
    is_mutating: bool = False
    approved_mutation: bool = False
    simulated_agent_response: SimulatedAgentResponse | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _default_simulated_response(self) -> BenchmarkCase:
        """Default the simulated agent response to mirror the "correct" answer.

        Benchmark cases that only care about server-side behavior (timeouts,
        exceptions, malformed responses, prompt injection) don't need to spell
        out a simulated agent response explicitly — it defaults to the perfect,
        expected tool call.
        """
        if self.simulated_agent_response is None:
            self.simulated_agent_response = SimulatedAgentResponse(
                tool_name=self.expected_tool,
                arguments=dict(self.expected_arguments),
            )
        return self


class BenchmarkSuite(BaseModel):
    """A named collection of benchmark cases."""

    name: str
    version: str = "0.1.0"
    cases: list[BenchmarkCase]

    @model_validator(mode="after")
    def _unique_ids(self) -> BenchmarkSuite:
        seen: set[str] = set()
        for case in self.cases:
            if case.id in seen:
                raise ValueError(f"Duplicate benchmark case id: {case.id}")
            seen.add(case.id)
        return self
