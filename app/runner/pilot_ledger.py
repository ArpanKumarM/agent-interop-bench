"""Persists a pilot run's plan/trials/summary as machine-readable artifacts
(Phase 4A.3a) under ``reports/experiments/<run_id>/`` -- a path already
covered by this repository's blanket ``reports/`` gitignore entry, so
generated run artifacts are never accidentally committed.

Resumability: ``write_or_verify_plan`` refuses to resume against a changed
configuration (a plan.json already on disk whose ``config_hash`` differs
from the current plan's); ``load_completed_trial_ids`` returns every
``trial_id`` already present in trials.jsonl (regardless of
"completed"/"failed" status -- both are terminal, already-attempted, and
already budget-charged observations) so a resumed run's dispatch loop never
reruns, and never re-spends budget on, a trial that already ran.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.models.pilot_plan import PilotExperimentPlan
from app.models.trial_ledger import TrialRecord


class PilotResumeConfigMismatchError(RuntimeError):
    """Raised when resuming against an existing run directory whose
    persisted plan.json has a different config_hash than the plan being
    resumed with -- refusing to silently mix two different experiment
    configurations under one run_id."""


class TrialLedger:
    def __init__(self, run_dir: str | Path) -> None:
        self.run_dir = Path(run_dir)
        self.plan_path = self.run_dir / "plan.json"
        self.trials_path = self.run_dir / "trials.jsonl"
        self.summary_path = self.run_dir / "summary.json"

    def write_or_verify_plan(self, plan: PilotExperimentPlan) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        if self.plan_path.exists():
            existing = PilotExperimentPlan.model_validate(json.loads(self.plan_path.read_text()))
            if existing.config_hash != plan.config_hash:
                raise PilotResumeConfigMismatchError(
                    f"Existing plan.json config_hash {existing.config_hash!r} does not match "
                    f"the current plan's config_hash {plan.config_hash!r}; refusing to resume "
                    "with a different experiment configuration under the same run directory."
                )
        else:
            self.plan_path.write_text(plan.model_dump_json(indent=2))

    def load_completed_trial_ids(self) -> set[str]:
        if not self.trials_path.exists():
            return set()
        ids: set[str] = set()
        for line in self.trials_path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            ids.add(json.loads(line)["trial_id"])
        return ids

    def append_trial(self, record: TrialRecord) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        with self.trials_path.open("a", encoding="utf-8") as handle:
            handle.write(record.model_dump_json() + "\n")

    def load_all_trials(self) -> list[TrialRecord]:
        if not self.trials_path.exists():
            return []
        records = []
        for line in self.trials_path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            records.append(TrialRecord.model_validate_json(line))
        return records

    def write_summary(self, summary: dict) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True))
