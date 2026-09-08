"""Phase 9 (F3 resolution study) -- dedicated execution entrypoint.

POST-FREEZE EXECUTION-IMPLEMENTATION ADDENDUM. Scientific freeze:
``32a76bfa19c3240bd87011fe9a7e41b3ced1a511`` -- UNCHANGED. This module adds
only execution machinery; it changes no scientific parameter.

Narrow responsibility:

    frozen Phase 9 artifacts
      -> preflight verification (no client)
      -> exact frozen-schedule loading (docs/phase_9_design/phase_9_execution_schedule.json)
      -> scenario/context construction via the frozen overlays
      -> the EXISTING generic decision-point machinery
         (run_decision_point_trial + the real OpenAI/Anthropic adapters,
          reused, never reimplemented)
      -> append-only Phase 9 ledger + at-most-once attempt journal
      -> frozen section-12 completion/halt rule.

Subcommands:
    preflight   Validates readiness. Constructs NO provider client.
    dry-run     Runs the exact same loop with a caller-injected fake
                provider at the network boundary. ``--run-id`` must start
                with ``dryrun-``; output never lands in a real Phase 9 dir.
    run         The ONLY subcommand that can make a live provider call.
                Refuses unless preflight passes, ENABLE_REAL_MODEL_COMPOSED_RUNS
                is true, PHASE_9_EXECUTE=1, and the provider key is present.
                Writes to reports/experiments/phase-9-f3-<short>/.

One model per invocation: each run consumes exactly that model's frozen
384-row schedule slice in its exact frozen order.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from app.cli.composed_live_pilot import (
    build_real_decision_point_adapter_factory,
    local_transport_factory,
    require_live_preconditions,
)
from app.cli.freeze_phase_9_artifacts import OVERLAYS_PATH, PLAN_PATH
from app.core.config import settings
from app.core.live_overlays import load_live_overlays
from app.models.composed import HostActionSpec
from app.models.composed_provenance import ComposedModelRunProvenance, ComposedProviderCallRecord
from app.models.execution_fingerprint import ExecutionFingerprint
from app.models.live_overlay import LiveExperimentOverlay
from app.models.pilot_plan import PilotExperimentPlan
from app.runner.blocked_schedule import ScheduledTrial, schedule_sha256
from app.runner.decision_point_pilot import (
    DecisionPointAdapterFactory,
    run_decision_point_trial,
)
from app.runner.execution_fingerprint import compute_execution_fingerprint_v2
from app.runner.host_adapters import PHASE_6B_HOST_POLICY_TEXT
from app.runner.model_panel import provider_config_sha256, provider_for_model
from app.runner.phase_9_execution_journal import Phase9ExecutionJournal, Phase9JournalError
from app.runner.phase_9_halt_monitor import Phase9HaltMonitor
from app.runner.phase_9_schedule_loader import (
    PHASE_9_EXPERIMENT_ID,
    PHASE_9_EXPERIMENT_VERSION,
    PHASE_9_MODEL_PANEL,
    Phase9ScheduleError,
    engine_trial_id,
    frozen_trial_id_map,
    load_phase_9_schedule,
)
from app.runner.pilot_budget import GlobalDecisionBudget
from app.runner.pilot_ledger import (
    PilotResumeConfigMismatchError,
    PilotResumeFingerprintMismatchError,
    PilotResumeScheduleMismatchError,
    TrialLedger,
)

_ROOT = Path(__file__).resolve().parents[2]
RUN_DIR_ROOT = _ROOT / "reports" / "experiments"

PHASE_9_SCIENTIFIC_FREEZE_COMMIT = "32a76bfa19c3240bd87011fe9a7e41b3ced1a511"
PHASE_9_CANONICAL_ACTIONS: tuple[str, ...] = ("relay_to_remote", "stop")

# Frozen per-model real output directory (step 17). Append-only; one dir per
# model minimises cross-model corruption risk.
PHASE_9_RUN_DIRNAME: dict[str, str] = {
    "gpt-5.6-sol": "phase-9-f3-sol",
    "gpt-5.6-terra": "phase-9-f3-terra",
    "gpt-5.6-luna": "phase-9-f3-luna",
    "claude-sonnet-5": "phase-9-f3-claude",
}
_FREEZE_VERIFIER = _ROOT / "scripts" / "verify_phase_9_freeze.py"
_ADDENDUM_MANIFEST = _ROOT / "docs" / "phase_9_execution_addendum_manifest.json"


class Phase9ExecuteError(RuntimeError):
    """A refused precondition. No provider client is constructed / no call is
    made when this is raised."""


# --------------------------------------------------------------------------- #
# frozen-artifact loading
# --------------------------------------------------------------------------- #
def load_phase_9_plan(model: str) -> PilotExperimentPlan:
    data = json.loads(PLAN_PATH.read_text())
    data["model"] = model
    plan = PilotExperimentPlan.model_validate(data)
    problems: list[str] = []
    if plan.experiment_id != PHASE_9_EXPERIMENT_ID:
        problems.append(f"experiment_id {plan.experiment_id!r}")
    if plan.experiment_version != PHASE_9_EXPERIMENT_VERSION:
        problems.append(f"experiment_version {plan.experiment_version!r}")
    if plan.execution_mode != "decision_point":
        problems.append(f"execution_mode {plan.execution_mode!r}")
    if plan.trials_per_condition != 3:
        problems.append(f"trials_per_condition {plan.trials_per_condition}")
    if plan.max_decisions_per_trial != 1:
        problems.append(f"max_decisions_per_trial {plan.max_decisions_per_trial}")
    if plan.max_total_decisions != 384:
        problems.append(f"max_total_decisions {plan.max_total_decisions}")
    if plan.timeout_seconds != 20.0:
        problems.append(f"timeout_seconds {plan.timeout_seconds}")
    if plan.reasoning_effort != "low":
        problems.append(f"reasoning_effort {plan.reasoning_effort!r}")
    if len(plan.overlay_ids) != 128:
        problems.append(f"overlay_ids count {len(plan.overlay_ids)}")
    if problems:
        raise Phase9ExecuteError(f"frozen Phase 9 plan drift: {', '.join(problems)}")
    return plan


def resolve_phase_9_overlays(plan: PilotExperimentPlan) -> list[LiveExperimentOverlay]:
    suite = load_live_overlays(str(OVERLAYS_PATH))
    by_id = {o.id: o for o in suite.overlays}
    unknown = [oid for oid in plan.overlay_ids if oid not in by_id]
    if unknown:
        raise Phase9ExecuteError(
            f"plan overlay id(s) missing from live_overlays_phase9.yaml: {unknown}"
        )
    return [by_id[oid] for oid in plan.overlay_ids]


def phase_9_execution_fingerprint(
    plan: PilotExperimentPlan,
    overlays: list[LiveExperimentOverlay],
    schedule: list[ScheduledTrial],
) -> ExecutionFingerprint:
    return compute_execution_fingerprint_v2(
        plan,
        overlays,
        canonical_actions=PHASE_9_CANONICAL_ACTIONS,
        host_policy_text=PHASE_6B_HOST_POLICY_TEXT,
        schedule_sha256=schedule_sha256(schedule),
        provider_config_sha256=provider_config_sha256(
            plan.model,
            canonical_actions=PHASE_9_CANONICAL_ACTIONS,
            timeout_seconds=plan.timeout_seconds,
        ),
    )


# --------------------------------------------------------------------------- #
# preflight / readiness checks (NO client, NO network)
# --------------------------------------------------------------------------- #
def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], capture_output=True, text=True, cwd=_ROOT, check=True
    ).stdout.strip()


def _returned_model_ok(requested: str, returned: str | None) -> bool:
    """A dated snapshot of the requested id is fine (e.g.
    ``gpt-5.6-sol-2026-09-08``); a different family is a substitution."""
    if returned is None:
        return True
    return returned == requested or returned.startswith(requested + "-")


def preflight_checks(model: str, run_dir: Path, *, for_run: bool) -> list[str]:
    """Every readiness gate. Returns a list of failure strings ([] == ready).
    Makes zero network calls and constructs no provider client."""
    fails: list[str] = []

    if model not in PHASE_9_MODEL_PANEL:
        fails.append(
            f"model {model!r} is not in the frozen four-model panel {list(PHASE_9_MODEL_PANEL)}"
        )
        return fails

    # -- scientific freeze lineage + verifier ---------------------------- #
    try:
        merge_base = _git("merge-base", "HEAD", PHASE_9_SCIENTIFIC_FREEZE_COMMIT)
        if merge_base != PHASE_9_SCIENTIFIC_FREEZE_COMMIT:
            fails.append(
                f"HEAD does not contain the scientific freeze commit "
                f"{PHASE_9_SCIENTIFIC_FREEZE_COMMIT[:12]} in its history"
            )
    except (subprocess.CalledProcessError, OSError) as exc:
        fails.append(f"cannot check scientific-freeze lineage: {exc}")

    rc = subprocess.run(
        [sys.executable, str(_FREEZE_VERIFIER)], capture_output=True, text=True, cwd=_ROOT
    )
    if rc.returncode != 0:
        fails.append("scripts/verify_phase_9_freeze.py did not pass")

    # -- execution-addendum manifest ---------------------------------- #
    if not _ADDENDUM_MANIFEST.exists():
        fails.append("docs/phase_9_execution_addendum_manifest.json is missing")
    else:
        try:
            from scripts.phase_9_execution_addendum import verify_addendum_manifest

            fails.extend(f"addendum manifest: {m}" for m in verify_addendum_manifest())
        except Exception as exc:  # noqa: BLE001 - any failure is a refusal
            fails.append(f"addendum manifest verification raised: {exc}")

    # -- frozen plan / overlays / schedule ------------------------------ #
    try:
        plan = load_phase_9_plan(model)
        overlays = resolve_phase_9_overlays(plan)
        schedule = load_phase_9_schedule(model)
        if len(schedule) != 384:
            fails.append(f"frozen schedule slice for {model!r} is not 384 rows")
        _ = phase_9_execution_fingerprint(plan, overlays, schedule)
    except (Phase9ExecuteError, Phase9ScheduleError) as exc:
        fails.append(str(exc))
        plan = None  # type: ignore[assignment]

    # -- output state: pristine for a first run, or a valid resumable state
    ledger = TrialLedger(run_dir)
    journal = Phase9ExecutionJournal(run_dir)
    completed = ledger.load_completed_trial_ids()
    try:
        journal.assert_resumable()
    except Phase9JournalError as exc:
        fails.append(str(exc))
    indeterminate = journal.indeterminate()
    if indeterminate:
        fails.append(f"{len(indeterminate)} indeterminate attempted trial(s) present in {run_dir}")
    if for_run and completed:
        # resume is allowed, but only against a matching plan/fingerprint/schedule
        # (the ledger enforces this on write_or_verify_*). Flag that this is a
        # resume, not a fresh run, so the operator is aware.
        fails.append(
            f"NOTE/resume: {run_dir} already has {len(completed)} completed trial(s); "
            "this would be a RESUME. Re-run preflight with acknowledgement, or use a "
            "fresh run dir for a first execution."
        )
    if not for_run and completed:
        fails.append(f"{run_dir} already has {len(completed)} completed trial(s)")

    # -- credentials present (never printed) + provider identity -------- #
    provider = provider_for_model(model)
    key_env = "ANTHROPIC_API_KEY" if provider == "anthropic" else "OPENAI_API_KEY"
    if not (os.environ.get(key_env) or "").strip():
        fails.append(f"{key_env} is not set (value never printed)")
    if not settings.enable_real_model_composed_runs and for_run:
        fails.append("ENABLE_REAL_MODEL_COMPOSED_RUNS is not true")
    if for_run and os.environ.get("PHASE_9_EXECUTE") != "1":
        fails.append("PHASE_9_EXECUTE is not '1' (belt-and-suspenders gate for a live Phase 9 run)")

    # -- no provider substitution / fallback / retry configuration ---- #
    for var in ("OPENAI_MODEL_OVERRIDE", "ANTHROPIC_MODEL_OVERRIDE", "PHASE_9_FALLBACK_MODEL"):
        if (os.environ.get(var) or "").strip():
            fails.append(f"{var} is set -- model substitution/fallback config is not permitted")
    for var in ("OPENAI_MAX_RETRIES", "ANTHROPIC_MAX_RETRIES"):
        val = (os.environ.get(var) or "").strip()
        if val and val != "0":
            fails.append(f"{var}={val!r} -- Phase 9 requires zero provider retries")

    return fails


def preflight_report(model: str, run_dir: Path, *, for_run: bool) -> dict:
    fails = preflight_checks(model, run_dir, for_run=for_run)
    report: dict = {
        "phase": 9,
        "scientific_freeze_commit": PHASE_9_SCIENTIFIC_FREEZE_COMMIT,
        "model": model,
        "provider": provider_for_model(model),
        "run_directory": str(run_dir.relative_to(_ROOT))
        if run_dir.is_relative_to(_ROOT)
        else str(run_dir),
        "canonical_actions": list(PHASE_9_CANONICAL_ACTIONS),
        "provider_calls_made": 0,
    }
    try:
        plan = load_phase_9_plan(model)
        overlays = resolve_phase_9_overlays(plan)
        schedule = load_phase_9_schedule(model)
        fp = phase_9_execution_fingerprint(plan, overlays, schedule)
        report.update(
            frozen_schedule_slice_trials=len(schedule),
            planned_provider_calls=len(schedule) * plan.max_decisions_per_trial,
            plan_config_hash=plan.config_hash,
            execution_fingerprint_sha256=fp.execution_fingerprint_sha256,
            schedule_sha256=fp.schedule_sha256,
            host_policy_sha256=fp.host_policy_sha256,
            canonical_action_schema_sha256=fp.canonical_action_schema_sha256,
            provider_config_sha256=fp.provider_config_sha256,
        )
    except (Phase9ExecuteError, Phase9ScheduleError) as exc:
        report["frozen_artifact_error"] = str(exc)
        fails = [*fails, f"frozen artifact load failed: {exc}"]
    report["ready"] = not [f for f in fails if not f.startswith("NOTE/")]
    report["blocking"] = [f for f in fails if not f.startswith("NOTE/")]
    report["notes"] = [f for f in fails if f.startswith("NOTE/")]
    return report


# --------------------------------------------------------------------------- #
# the execution loop (frozen order + journaling + halt rule)
# --------------------------------------------------------------------------- #
def _arm_of(entry: ScheduledTrial) -> str:
    return "N" if entry.condition == "neutral" else "P"


async def execute_phase_9(
    model: str,
    run_dir: Path,
    *,
    adapter_factory: DecisionPointAdapterFactory,
    transport_factory: Callable[[], object] = local_transport_factory,
    execution_fingerprint: ExecutionFingerprint | None = None,
    max_trials: int | None = None,
) -> dict:
    """Run (or resume) that model's frozen 384-trial slice, in frozen order,
    with at-most-once journaling and the section-12 halt rule. ``adapter_factory``
    is injected: the real per-provider factory for ``run``, a deterministic
    fake for ``dry-run`` / tests. Makes exactly one provider call per
    not-yet-terminal frozen trial.

    ``max_trials`` (optional): stop cleanly after executing that many
    not-yet-terminal trials this invocation -- a deliberate bounded /
    staged execution, no dangling attempt, no HALT. Resume (with a larger
    or unset ``max_trials``) continues in the same frozen order. The
    persisted schedule and execution fingerprint are always the full
    384-trial frozen ones regardless of ``max_trials``."""
    plan = load_phase_9_plan(model)
    overlays = resolve_phase_9_overlays(plan)
    overlays_by_id = {o.id: o for o in overlays}
    schedule = load_phase_9_schedule(model)
    fp = execution_fingerprint or phase_9_execution_fingerprint(plan, overlays, schedule)

    ledger = TrialLedger(run_dir)
    ledger.write_or_verify_plan(plan)
    ledger.write_or_verify_execution_fingerprint(fp)
    ledger.write_or_verify_schedule(schedule)

    journal = Phase9ExecutionJournal(run_dir)
    journal.assert_resumable()  # refuse on any dangling ATTEMPT_STARTED

    frozen_map = frozen_trial_id_map(model)
    (run_dir / "phase_9_frozen_trial_map.json").write_text(
        json.dumps(frozen_map, indent=2, sort_keys=True) + "\n"
    )

    completed_ids = ledger.load_completed_trial_ids()
    journal_terminal = journal.terminal_engine_ids()
    # ledger and journal must agree on what is already terminal
    if completed_ids - journal_terminal:
        raise Phase9JournalError(
            "ledger has completed trial(s) with no terminal journal line -- "
            f"corruption; refusing to resume: {sorted(completed_ids - journal_terminal)}"
        )

    budget = GlobalDecisionBudget(plan.max_total_decisions)
    halt = Phase9HaltMonitor(model)
    # fold prior terminal records into the halt tally on resume
    engine_to_arm = {engine_trial_id(e.overlay_id, e.trial_index): _arm_of(e) for e in schedule}
    for rec in ledger.load_all_trials():
        if rec.trial_id not in engine_to_arm:
            raise Phase9JournalError(
                f"ledger contains a trial id not in {model!r}'s frozen schedule: {rec.trial_id!r}"
            )
        halt.observe_terminal(engine_to_arm[rec.trial_id], status=rec.status)

    executed_now = 0
    halted: dict | None = None
    substitution: dict | None = None
    started_at = datetime.now(UTC).isoformat()

    for entry in schedule:
        eid = engine_trial_id(entry.overlay_id, entry.trial_index)
        fid = frozen_map[eid]
        if eid in completed_ids:
            continue
        arm = _arm_of(entry)
        overlay = overlays_by_id[entry.overlay_id]

        journal.record_attempt_started(eid, fid, model=model, overlay_id=entry.overlay_id)
        record = await run_decision_point_trial(
            plan, overlay, entry.trial_index, adapter_factory, transport_factory, budget, fp
        )
        ledger.append_trial(record)
        journal.record_terminal(eid, fid, status=record.status, detail=record.termination_reason)
        executed_now += 1
        halt.observe_terminal(arm, status=record.status)

        if record.returned_model and not _returned_model_ok(model, record.returned_model):
            substitution = {
                "engine_trial_id": eid,
                "requested_model": model,
                "returned_model": record.returned_model,
            }
            break

        decision = halt.check()
        if decision.tripped:
            halted = {"reason": decision.reason, "cell": list(decision.cell or ())}
            break

        if max_trials is not None and executed_now >= max_trials:
            break

    summary = _finalize(
        plan, model, ledger, journal, halt, started_at, executed_now, halted, substitution
    )
    ledger.write_summary(summary)
    if halted is not None or substitution is not None:
        (run_dir / "HALTED.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return summary


def _finalize(
    plan: PilotExperimentPlan,
    model: str,
    ledger: TrialLedger,
    journal: Phase9ExecutionJournal,
    halt: Phase9HaltMonitor,
    started_at: str,
    executed_now: int,
    halted: dict | None,
    substitution: dict | None,
) -> dict:
    records = ledger.load_all_trials()
    by_status: dict[str, int] = {}
    egress_true = 0
    for r in records:
        by_status[r.status] = by_status.get(r.status, 0) + 1
        if r.outcomes.any_sensitive_field_egress is True:
            egress_true += 1
    complete = halted is None and substitution is None and len(records) == 384
    return {
        "phase": 9,
        "scientific_freeze_commit": PHASE_9_SCIENTIFIC_FREEZE_COMMIT,
        "experiment_id": plan.experiment_id,
        "model": model,
        "started_at": started_at,
        "finished_at": datetime.now(UTC).isoformat(),
        "frozen_schedule_slice_trials": 384,
        "trials_recorded": len(records),
        "trials_executed_this_invocation": executed_now,
        "trial_status_counts": by_status,
        "journal_state_counts": journal.state_counts(),
        "any_sensitive_field_egress_true_count": egress_true,
        "halt_monitor": halt.summary(),
        "halted": halted,
        "model_substitution_detected": substitution,
        "run_complete": complete,
        "partial": not complete,
        "note": (
            "PARTIAL run -- immutable, not to be analysed below the section-12 threshold; "
            "re-freeze before any re-run"
            if not complete
            else "complete 384-trial model slice"
        ),
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _run_dir_for_run(model: str) -> Path:
    return RUN_DIR_ROOT / PHASE_9_RUN_DIRNAME[model]


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="phase_9_execute")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("preflight", "dry-run", "run"):
        p = sub.add_parser(name)
        p.add_argument("--model", required=True, choices=sorted(PHASE_9_MODEL_PANEL))
        p.add_argument(
            "--run-id",
            default=None,
            help="dry-run: required, must start with 'dryrun-'. run/preflight: ignored "
            "(the frozen per-model directory is used).",
        )
    return parser


class _FakePhase9Adapter:
    """A deterministic, no-network fake decision source. Records exactly one
    ``ComposedProviderCallRecord`` per decision (so ``decision_count == 1``
    per trial, provider-boundary calls are countable) and captures the
    ``HostDecisionContext`` seen at the boundary. Never imports a provider
    SDK. Used by ``dry-run`` and by the offline integration / failure tests.

    ``fail_mode`` (tests only): ``None`` -> return ``action``; ``"timeout"``
    / ``"malformed"`` / ``"provider_error"`` / ``"refusal"`` / ``"truncation"``
    -> raise, so ``run_decision_point_trial`` records a terminal
    ``status="failed"`` trial exactly as a real provider failure would.
    """

    def __init__(
        self,
        *,
        case_id: str,
        action: str = "stop",
        relay_content: str | None = None,
        returned_model: str | None = None,
        system_fingerprint: str | None = None,
        fail_mode: str | None = None,
        fail_message: str | None = None,
        seen_contexts: list | None = None,
        call_counter: list[int] | None = None,
    ) -> None:
        self._case_id = case_id
        self._action = action
        self._relay_content = relay_content
        self._fail_mode = fail_mode
        self._fail_message = fail_message
        self._seen_contexts = seen_contexts
        self._call_counter = call_counter
        self.provenance = ComposedModelRunProvenance(
            adapter_type="phase9_fake",
            provider="none",
            requested_model=returned_model or "fake",
            host_policy_sha256="0" * 64,
            tool_schema_sha256="0" * 64,
            configured_timeout_seconds=0.0,
            configured_max_retries=0,
            configured_max_output_tokens=0,
        )
        self._returned_model = returned_model
        self._system_fingerprint = system_fingerprint

    async def decide(self, context):  # noqa: ANN001 - HostDecisionContext
        if self._seen_contexts is not None:
            self._seen_contexts.append(context)
        if self._call_counter is not None:
            self._call_counter[0] += 1
        self.provenance.provider_calls.append(
            ComposedProviderCallRecord(
                case_id=self._case_id,
                decision_index=len(self.provenance.provider_calls),
                requested_model=self.provenance.requested_model,
                returned_model=self._returned_model,
                provider_system_fingerprint=self._system_fingerprint,
                status="ok" if self._fail_mode is None else "provider_protocol_error",
                observable_action=None,
            )
        )
        if self._fail_mode is not None:
            # mimic the real adapters: any provider failure is passed through
            # _sanitize_provider_error before it can be persisted.
            from app.runner.openai_adapter import _sanitize_provider_error

            raw = self._fail_message or f"fake provider {self._fail_mode} (no network)"
            raise RuntimeError(_sanitize_provider_error(Exception(raw)))
        if self._action == "relay_to_remote":
            return HostActionSpec(
                action="relay_to_remote",
                relay_template=self._relay_content or "ack",
                content_type="text/plain",
            )
        return HostActionSpec(action="stop")


def build_fake_phase_9_adapter_factory(
    *,
    action: str = "stop",
    relay_content: str | None = None,
    returned_model: str | None = None,
    system_fingerprint: str | None = None,
    fail_mode: str | None = None,
    fail_message: str | None = None,
    seen_contexts: list | None = None,
    call_counter: list[int] | None = None,
) -> DecisionPointAdapterFactory:
    def factory(case_id: str, max_decisions: int, allowed_actions: tuple[str, ...]):
        return _FakePhase9Adapter(
            case_id=case_id,
            action=action,
            relay_content=relay_content,
            returned_model=returned_model,
            system_fingerprint=system_fingerprint,
            fail_mode=fail_mode,
            fail_message=fail_message,
            seen_contexts=seen_contexts,
            call_counter=call_counter,
        )

    return factory  # type: ignore[return-value]


def _fake_stop_factory() -> DecisionPointAdapterFactory:
    """The ``dry-run`` fake: always 'stop', records one provider call."""
    return build_fake_phase_9_adapter_factory(action="stop", returned_model="dry-run-fake")


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)
    model: str = args.model
    try:
        if args.command == "preflight":
            report = preflight_report(model, _run_dir_for_run(model), for_run=True)
            print(json.dumps(report, indent=2, sort_keys=True))
            return 0 if not report["blocking"] else 1

        if args.command == "dry-run":
            run_id = args.run_id or ""
            if not run_id.startswith("dryrun-"):
                raise Phase9ExecuteError("dry-run requires --run-id starting with 'dryrun-'")
            run_dir = RUN_DIR_ROOT / run_id
            summary = asyncio.run(
                execute_phase_9(model, run_dir, adapter_factory=_fake_stop_factory())
            )
            print(json.dumps(summary, indent=2, sort_keys=True))
            return 0

        # run
        run_dir = _run_dir_for_run(model)
        fails = preflight_checks(model, run_dir, for_run=True)
        blocking = [f for f in fails if not f.startswith("NOTE/")]
        if blocking:
            print("refused: preflight failed:", file=sys.stderr)
            for f in blocking:
                print(f"  - {f}", file=sys.stderr)
            return 1
        require_live_preconditions(model)
        plan = load_phase_9_plan(model)
        summary = asyncio.run(
            execute_phase_9(
                model,
                run_dir,
                adapter_factory=build_real_decision_point_adapter_factory(plan),
            )
        )
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    except (
        Phase9ExecuteError,
        Phase9ScheduleError,
        Phase9JournalError,
        PilotResumeConfigMismatchError,
        PilotResumeFingerprintMismatchError,
        PilotResumeScheduleMismatchError,
    ) as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
