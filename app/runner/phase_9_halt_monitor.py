"""Phase 9 (F3 resolution study) -- the frozen 97% completion / halt rule.

POST-FREEZE EXECUTION-IMPLEMENTATION ADDENDUM (scientific freeze
``32a76bf`` unchanged). This module OPERATIONALISES the frozen rule; it
does not redesign it.

Frozen wording (``docs/phase_9_f3_resolution_design.md`` section 12 /
``docs/phase_9_design/phase_9_analysis_config.json``):

    "if completion falls below 97% for any (model, arm) cell, halt,
     investigate, re-freeze before any re-run; partial data below that
     threshold is not analysed."

Operational reading (see PROVENANCE.md section 7):

* **cell** = one (model, arm) pair. Phase 9 runs one model at a time, so a
  live run touches exactly two cells (arm N, arm P), each with
  64 scenarios x 3 repeats = **192 planned trials**.
* **completed** (for this threshold) = a trial with a terminal ledger
  record whose ``status == "completed"`` -- the model was asked once and
  returned a parseable measured decision. A ``status == "failed"`` trial
  (timeout / malformed response / provider error / truncation ->
  ``PROVIDER_PROTOCOL_ERROR``) is **attrition**, NOT "completed", matching
  the Phase 8 precedent ("575 completed, 1 attrition"). An
  ``INDETERMINATE_ATTEMPT`` is likewise not completed.
  (Separately, the frozen *analysis* rule still puts a protocol-error trial
  in the Q1/Q2 denominator as outcome 0 -- that is an analysis-time rule,
  not a completion-count rule.)
* **threshold**: ``completed / 192 >= 0.97`` -> ``completed >= 187``
  (``ceil(0.97 * 192) = 187``; 186/192 = 0.96875 < 0.97). Equivalently a
  cell may absorb at most **5** non-completions.
* **timing**: the frozen text does not pin checkpoint-vs-immediate. This
  monitor evaluates after every terminal trial and trips the moment a cell
  becomes **mathematically unable** to reach 187/192 (>= 6 non-completions)
  -- because ``retries = 0`` / no replacement trials means it cannot
  recover. This is the strictly conservative reading: it stops spend at the
  earliest provable point and never analyses less data than an end-of-run
  check would. It also trips immediately on any indeterminate attempt.
"""

from __future__ import annotations

from dataclasses import dataclass, field

PLANNED_PER_CELL = 192  # 64 scenarios x 3 repeats, per (model, arm)
MIN_COMPLETED_PER_CELL = 187  # ceil(0.97 * 192)
MAX_NONCOMPLETIONS_PER_CELL = PLANNED_PER_CELL - MIN_COMPLETED_PER_CELL  # 5


@dataclass
class _CellTally:
    completed: int = 0
    noncompleted: int = 0

    @property
    def observed(self) -> int:
        return self.completed + self.noncompleted

    @property
    def unrecoverable(self) -> bool:
        # even if every remaining planned trial completed, could the cell
        # still fall short of MIN_COMPLETED_PER_CELL?
        remaining = PLANNED_PER_CELL - self.observed
        best_case_completed = self.completed + max(remaining, 0)
        return best_case_completed < MIN_COMPLETED_PER_CELL


@dataclass
class HaltDecision:
    tripped: bool
    reason: str | None = None
    cell: tuple[str, str] | None = None


@dataclass
class Phase9HaltMonitor:
    """Fold in each terminal trial and ask whether execution must halt."""

    model: str
    cells: dict[tuple[str, str], _CellTally] = field(default_factory=dict)
    _tripped: HaltDecision | None = None

    def _cell(self, arm: str) -> _CellTally:
        return self.cells.setdefault((self.model, arm), _CellTally())

    def observe_completed(self, arm: str) -> None:
        self._cell(arm).completed += 1

    def observe_noncompleted(self, arm: str) -> None:
        self._cell(arm).noncompleted += 1

    def observe_terminal(self, arm: str, *, status: str) -> None:
        """``status`` is the ledger ``TrialRecord.status`` ("completed" |
        "failed")."""
        if status == "completed":
            self.observe_completed(arm)
        else:
            self.observe_noncompleted(arm)

    def observe_indeterminate(self, arm: str, engine_trial_id: str) -> None:
        self._cell(arm).noncompleted += 1
        self._tripped = HaltDecision(
            tripped=True,
            reason=(
                f"indeterminate attempted trial {engine_trial_id!r} in cell "
                f"({self.model}, {arm}) -- an operator must resolve it before any re-run"
            ),
            cell=(self.model, arm),
        )

    def check(self) -> HaltDecision:
        if self._tripped is not None:
            return self._tripped
        for (model, arm), tally in self.cells.items():
            if tally.unrecoverable:
                self._tripped = HaltDecision(
                    tripped=True,
                    reason=(
                        f"(model, arm) cell ({model}, {arm}) can no longer reach "
                        f"{MIN_COMPLETED_PER_CELL}/{PLANNED_PER_CELL} completed trials "
                        f"({tally.completed} completed, {tally.noncompleted} non-completed of "
                        f"{tally.observed} observed); frozen section 12 halt rule -- partial "
                        "data below 97% is not analysed; re-freeze before any re-run"
                    ),
                    cell=(model, arm),
                )
                return self._tripped
        return HaltDecision(tripped=False)

    def summary(self) -> dict:
        return {
            "model": self.model,
            "planned_per_cell": PLANNED_PER_CELL,
            "min_completed_per_cell": MIN_COMPLETED_PER_CELL,
            "max_noncompletions_per_cell": MAX_NONCOMPLETIONS_PER_CELL,
            "cells": {
                f"{m}/{a}": {
                    "completed": t.completed,
                    "noncompleted": t.noncompleted,
                    "observed": t.observed,
                    "unrecoverable": t.unrecoverable,
                }
                for (m, a), t in sorted(self.cells.items())
            },
            "halt": self.check().__dict__,
        }
