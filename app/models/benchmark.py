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
    # turn's tool output. Only reachable when max_turns >= 2. Mutually
    # exclusive with simulated_reactions (below) — use this one for a single
    # reaction turn (the original Phase 2A/2B shape); it is unchanged.
    simulated_reaction: SimulatedAgentResponse | None = None
    # Turn 1..N fixtures, in order, for a case that needs more than one
    # scripted reaction (e.g. a 3-turn case: turn 0, then two more scripted
    # decisions). Mutually exclusive with simulated_reaction. Added in
    # Phase 2D; every case that predates it uses simulated_reaction or
    # neither, so this field is empty for all of them.
    simulated_reactions: list[SimulatedAgentResponse] = Field(default_factory=list)
    # Which turn indices the mock MCP server should apply this case's
    # simulated_failure_mode to; every other turn gets FailureMode.NORMAL
    # regardless of what tool is called. None (the default) means exactly
    # {0} — turn 0 only — which is the literal, hardcoded behavior every
    # case before Phase 2D relies on, so leaving this unset changes nothing
    # for any of them. Set explicitly (e.g. [0, 1]) only for a case that
    # deliberately exercises more than one malicious/failing observation in
    # the same bounded run.
    injected_turns: list[int] | None = None
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

    @model_validator(mode="after")
    def _reactions_mutually_exclusive_and_bounded(self) -> BenchmarkCase:
        if self.simulated_reaction is not None and self.simulated_reactions:
            raise ValueError(
                f"Case '{self.id}' sets both simulated_reaction and simulated_reactions; "
                "use exactly one."
            )
        if self.simulated_reactions and self.max_turns < len(self.simulated_reactions) + 1:
            raise ValueError(
                f"Case '{self.id}' has {len(self.simulated_reactions)} simulated_reactions "
                f"but max_turns={self.max_turns}; need max_turns >= "
                f"{len(self.simulated_reactions) + 1} (turn 0 plus every reaction)."
            )
        return self

    @model_validator(mode="after")
    def _injected_turns_are_in_range(self) -> BenchmarkCase:
        if self.injected_turns is None:
            return self
        if not self.injected_turns:
            raise ValueError(
                f"Case '{self.id}' sets injected_turns to an empty list; omit it instead."
            )
        if len(set(self.injected_turns)) != len(self.injected_turns):
            raise ValueError(f"Case '{self.id}' has duplicate values in injected_turns.")
        out_of_range = [t for t in self.injected_turns if t < 0 or t >= self.max_turns]
        if out_of_range:
            raise ValueError(
                f"Case '{self.id}' has injected_turns {out_of_range} outside "
                f"[0, max_turns={self.max_turns})."
            )
        if self.simulated_failure_mode == FailureMode.NORMAL:
            raise ValueError(
                f"Case '{self.id}' sets injected_turns but simulated_failure_mode is 'normal'; "
                "injected_turns only has an effect for a non-normal failure mode."
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
