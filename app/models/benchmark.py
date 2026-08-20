"""Benchmark case schema: deterministic, declarative test definitions."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.models.enums import BenchmarkCategory, ExpectedOutcome, FailureMode


class ArgumentMatchRule(BaseModel):
    """An explicit, benchmark-author-opted-in matcher for one expected argument.

    Absent from a case's ``argument_match_rules``, every argument is compared
    with Python ``==`` (exact match) against its ``expected_arguments`` value
    — this is the only default and covers identifiers, enums, numbers, and
    mutation payload text, none of which should ever match loosely.

    ``contains_substrings`` exists for exactly one situation found in the
    core suite: a free-text tool argument (e.g. a search query) whose task
    contract, per the case's own ``user_prompt``, states an intent rather
    than quoting an exact required string. Its name is literal, not
    aspirational: it is a case-insensitive check that every one of ``terms``
    occurs as a raw substring of the actual argument value — no tokenization,
    no word boundaries, no stemming, no semantic equivalence. A benchmark
    author choosing this matcher is responsible for picking substrings
    specific enough not to accidentally occur inside an unrelated word (e.g.
    ``"fail"`` also matches inside ``"failover"``; ``"failure"`` does not).
    It does not replace ``exact``; it must be explicitly opted into per
    argument, per case.
    """

    matcher: Literal["exact", "contains_substrings"] = "exact"
    terms: list[str] | None = None

    @model_validator(mode="after")
    def _terms_required_for_contains(self) -> ArgumentMatchRule:
        if self.matcher == "contains_substrings" and not self.terms:
            raise ValueError("matcher 'contains_substrings' requires a non-empty 'terms' list")
        return self


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
    # Opt-in, per-argument non-exact matchers (see ArgumentMatchRule). Any
    # argument name absent from this mapping is compared with exact equality.
    argument_match_rules: dict[str, ArgumentMatchRule] = Field(default_factory=dict)
    simulated_failure_mode: FailureMode = FailureMode.NORMAL
    expected_outcome: ExpectedOutcome
    max_latency_ms: int = 2000
    # Bounded turn budget for this case's interaction loop. 1 (the default)
    # means single-turn: the runner asks the adapter for exactly one decision
    # and never asks it to react to that decision's tool output. Raise this
    # to let a case exercise multi-turn behavior (e.g. reacting to a
    # prompt-injection payload observed in tool output). The runner always
    # stops at this bound regardless of what the adapter would otherwise do —
    # termination is deterministic, never open-ended.
    max_turns: int = Field(default=1, ge=1, le=10)
    is_mutating: bool = False
    approved_mutation: bool = False
    simulated_agent_response: SimulatedAgentResponse | None = None
    # Second-turn fixture: what the fake adapter does after observing the first
    # turn's tool output. Only reachable when max_turns >= 2.
    simulated_reaction: SimulatedAgentResponse | None = None
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

    @model_validator(mode="after")
    def _match_rules_reference_real_arguments(self) -> BenchmarkCase:
        unknown = set(self.argument_match_rules) - set(self.expected_arguments)
        if unknown:
            raise ValueError(
                f"Case '{self.id}' has argument_match_rules for argument(s) {sorted(unknown)} "
                "not present in expected_arguments."
            )
        return self

    @model_validator(mode="after")
    def _reaction_requires_turn_budget(self) -> BenchmarkCase:
        if self.simulated_reaction is not None and self.max_turns < 2:
            raise ValueError(
                f"Case '{self.id}' sets simulated_reaction but max_turns={self.max_turns}; "
                "the runner would never reach a second turn to use it. Set max_turns >= 2."
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
