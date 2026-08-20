"""Models describing a single benchmark case execution.

A case's execution is a bounded sequence of turns: the adapter decides,
the runner validates and (if the decision passes the mutation safety gate)
executes a tool call, the adapter observes the result and decides again, up
to ``BenchmarkCase.max_turns``. ``TurnResult`` captures one such turn in
full; ``RunResult`` is the ordered trace of all turns taken for one case.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import FailureMode


class ToolCallDecision(BaseModel):
    """A decision made by an AgentAdapter: which tool to call, and with what arguments.

    ``tool_name`` is ``None`` when the adapter deliberately declines to call any
    tool — a refusal on turn one, or a voluntary stop on a later turn — which
    is itself a valid, scoreable outcome.
    """

    tool_name: str | None
    arguments: dict[str, Any] = Field(default_factory=dict)
    rationale: str | None = None


class TerminationReason(StrEnum):
    """Why a case's turn loop stopped. Every loop stops for exactly one of these reasons."""

    VOLUNTARY_STOP = "voluntary_stop"
    BLOCKED_UNSAFE = "blocked_unsafe"
    MAX_TURNS_REACHED = "max_turns_reached"


class TurnResult(BaseModel):
    """Everything captured for one turn of a benchmark case's tool-call loop.

    Every field needed to audit that turn independently is recorded here,
    rather than only the outcome: the adapter's raw decision, whether that
    decision named a known tool, whether it was mutating, whether a mutation
    was approved, whether the safety gate blocked it, whether a tool call
    actually executed, and — only if it did — the tool's output/error and
    timing.
    """

    turn_index: int
    requested_tool: str | None
    requested_arguments: dict[str, Any] = Field(default_factory=dict)
    decision_rationale: str | None = None
    stopped: bool = False
    """True when the adapter voluntarily declined to call a tool this turn."""

    tool_known: bool | None = None
    """None when ``stopped``; otherwise whether ``requested_tool`` matched a discovered tool."""

    is_mutating: bool | None = None
    mutation_approved: bool | None = None
    blocked_unsafe: bool = False
    blocked_reason: str | None = None

    executed: bool = False
    """Whether a tool call actually reached the transport this turn."""

    tool_output: Any | None = None
    raw_text_output: str | None = None
    error: str | None = None
    is_error_result: bool = False
    timed_out: bool = False
    tool_not_found: bool = False
    latency_ms: float = 0.0
    failure_mode_applied: FailureMode = FailureMode.NORMAL
    executed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RunResult(BaseModel):
    """The complete, ordered trace of every turn taken while executing one benchmark case.

    Every case, single-turn or multi-turn, is represented the same way: a
    non-empty ``turns`` list plus the reason the loop stopped. Evaluators
    that only care about the first decision (tool selection, argument
    correctness, schema validity, task completion, resilience) read the
    ``turns[0]``-derived convenience properties below unchanged; evaluators
    that need to reason about the whole interaction (prompt-injection
    resistance) read ``turns`` directly.
    """

    case_id: str
    turns: list[TurnResult] = Field(default_factory=list)
    termination_reason: TerminationReason
    failure_mode_applied: FailureMode = FailureMode.NORMAL

    @property
    def first_turn(self) -> TurnResult | None:
        return self.turns[0] if self.turns else None

    @property
    def selected_tool(self) -> str | None:
        return self.first_turn.requested_tool if self.first_turn else None

    @property
    def selected_arguments(self) -> dict[str, Any]:
        return self.first_turn.requested_arguments if self.first_turn else {}

    @property
    def tool_output(self) -> Any | None:
        return self.first_turn.tool_output if self.first_turn else None

    @property
    def raw_text_output(self) -> str | None:
        return self.first_turn.raw_text_output if self.first_turn else None

    @property
    def error(self) -> str | None:
        return self.first_turn.error if self.first_turn else None

    @property
    def is_error_result(self) -> bool:
        return self.first_turn.is_error_result if self.first_turn else False

    @property
    def latency_ms(self) -> float:
        return self.first_turn.latency_ms if self.first_turn else 0.0

    @property
    def timed_out(self) -> bool:
        return self.first_turn.timed_out if self.first_turn else False

    @property
    def blocked_unsafe(self) -> bool:
        return self.first_turn.blocked_unsafe if self.first_turn else False

    @property
    def tool_not_found(self) -> bool:
        return self.first_turn.tool_not_found if self.first_turn else False

    @property
    def reaction_turns(self) -> list[TurnResult]:
        """Every turn after the first — the interaction that happened after the
        adapter observed the first turn's tool output. Empty for single-turn cases."""
        return self.turns[1:]
