"""Phase 9 (F3 resolution study) -- append-only execution journal.

POST-FREEZE EXECUTION-IMPLEMENTATION ADDENDUM (scientific freeze
``32a76bf`` unchanged).

Purpose: guarantee **strict at-most-once automatic execution** of every
frozen Phase 9 trial id across crashes. The generic ``TrialLedger`` only
records a trial *after* it terminates; if the process dies between the
provider call and the ledger append, a naive resume would re-issue that
provider call. This journal closes that window.

For each engine trial id the journal records, in ``attempts.jsonl``
(append-only, fsync'd before the network call):

    ATTEMPT_STARTED         durable, written BEFORE the one provider call
    COMPLETED               terminal: the trial produced a status="completed" record
    PROVIDER_PROTOCOL_ERROR terminal: the trial produced a status="failed" record
                            (timeout / malformed response / provider error / truncation)

Derived states (never written, computed by ``scan``):

    UNEXECUTED              no journal line at all
    INDETERMINATE_ATTEMPT   ATTEMPT_STARTED with no terminal line -> a crash
                            during/after the provider call. NEVER retried
                            automatically; the run refuses to resume until an
                            operator resolves it.

No provider call. No network.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

ATTEMPT_STARTED = "ATTEMPT_STARTED"
COMPLETED = "COMPLETED"
PROVIDER_PROTOCOL_ERROR = "PROVIDER_PROTOCOL_ERROR"
UNEXECUTED = "UNEXECUTED"
INDETERMINATE_ATTEMPT = "INDETERMINATE_ATTEMPT"

_TERMINAL = frozenset({COMPLETED, PROVIDER_PROTOCOL_ERROR})


class Phase9JournalError(RuntimeError):
    """A journal integrity violation (duplicate terminal, unknown trial id,
    scenario/arm mismatch, or a dangling indeterminate attempt on resume)."""


@dataclass(frozen=True)
class TrialJournalState:
    engine_trial_id: str
    frozen_trial_id: str
    state: str
    attempt_started_at: str | None
    terminal_at: str | None
    detail: str | None


class Phase9ExecutionJournal:
    def __init__(self, run_dir: str | Path) -> None:
        self.run_dir = Path(run_dir)
        self.path = self.run_dir / "attempts.jsonl"

    # -- writes -------------------------------------------------------------
    def _append(self, obj: dict) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        line = json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n"
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())

    def record_attempt_started(
        self, engine_trial_id: str, frozen_trial_id: str, *, model: str, overlay_id: str
    ) -> None:
        """Durably record ATTEMPT_STARTED. MUST be called (and returned from)
        before the single provider call for this trial."""
        self._append(
            {
                "event": ATTEMPT_STARTED,
                "engine_trial_id": engine_trial_id,
                "frozen_trial_id": frozen_trial_id,
                "model": model,
                "overlay_id": overlay_id,
                "utc": datetime.now(UTC).isoformat(),
            }
        )

    def record_terminal(
        self, engine_trial_id: str, frozen_trial_id: str, *, status: str, detail: str | None = None
    ) -> str:
        """Record the terminal state derived from the ledger ``TrialRecord``
        status. ``status`` is the ``TrialRecord.status`` value
        ("completed" | "failed"). Returns the journal state written."""
        state = COMPLETED if status == "completed" else PROVIDER_PROTOCOL_ERROR
        self._append(
            {
                "event": state,
                "engine_trial_id": engine_trial_id,
                "frozen_trial_id": frozen_trial_id,
                "trial_record_status": status,
                "detail": (detail or "")[:500] or None,
                "utc": datetime.now(UTC).isoformat(),
            }
        )
        return state

    # -- reads ------------------------------------------------------------
    def _raw_events(self) -> list[dict]:
        if not self.path.exists():
            return []
        out: list[dict] = []
        for line in self.path.read_text().splitlines():
            line = line.strip()
            if line:
                out.append(json.loads(line))
        return out

    def scan(self) -> dict[str, TrialJournalState]:
        """{engine_trial_id -> TrialJournalState}. Raises on a duplicate
        terminal line (a second scientific observation for one frozen id)."""
        started: dict[str, dict] = {}
        terminal: dict[str, dict] = {}
        for ev in self._raw_events():
            eid = ev["engine_trial_id"]
            kind = ev["event"]
            if kind == ATTEMPT_STARTED:
                started.setdefault(eid, ev)
            elif kind in _TERMINAL:
                if eid in terminal:
                    raise Phase9JournalError(
                        f"duplicate terminal journal line for {eid!r}: "
                        f"{terminal[eid]['event']} then {kind}"
                    )
                terminal[eid] = ev
        out: dict[str, TrialJournalState] = {}
        for eid in set(started) | set(terminal):
            s = started.get(eid)
            t = terminal.get(eid)
            if t is not None:
                state = t["event"]
            elif s is not None:
                state = INDETERMINATE_ATTEMPT
            else:  # pragma: no cover - unreachable (union guarantees one side)
                state = UNEXECUTED
            out[eid] = TrialJournalState(
                engine_trial_id=eid,
                frozen_trial_id=(t or s or {}).get("frozen_trial_id", ""),
                state=state,
                attempt_started_at=(s or {}).get("utc"),
                terminal_at=(t or {}).get("utc"),
                detail=(t or {}).get("detail"),
            )
        return out

    def terminal_engine_ids(self) -> set[str]:
        return {eid for eid, st in self.scan().items() if st.state in _TERMINAL}

    def indeterminate(self) -> list[TrialJournalState]:
        return [st for st in self.scan().values() if st.state == INDETERMINATE_ATTEMPT]

    def assert_resumable(self) -> None:
        """Refuse an automatic resume while any ATTEMPT_STARTED has no terminal
        line -- that trial's provider call may have happened; re-issuing it
        would create a second independent observation under one frozen id."""
        dangling = self.indeterminate()
        if dangling:
            ids = ", ".join(sorted(st.engine_trial_id for st in dangling))
            raise Phase9JournalError(
                "refusing to resume: indeterminate attempted trial(s) with no terminal record "
                f"-- an operator must resolve these before any further execution: {ids}. "
                "Do NOT re-run them automatically; do NOT fabricate an outcome; do NOT create "
                "a replacement trial."
            )

    def state_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for st in self.scan().values():
            counts[st.state] = counts.get(st.state, 0) + 1
        return counts
