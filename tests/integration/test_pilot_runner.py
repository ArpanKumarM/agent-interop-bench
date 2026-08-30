"""Phase 4A.3a: end-to-end offline pilot runner tests.

Every provider decision comes from a hand-rolled fake HostAgentAdapter --
no OpenAI SDK, no network, no live model. Proves: global budget cannot be
exceeded, resume never duplicates trials, a config_hash mismatch refuses
resume, a failed provider decision is recorded (not silently dropped or
retried), outcomes/analysis are computed correctly from known mocked
scripts, and no raw reasoning/credential ever reaches a persisted record.
"""

from __future__ import annotations

import json

from app.core.live_overlays import load_live_overlays
from app.models.composed import HostActionSpec
from app.models.composed_provenance import ComposedModelRunProvenance, ComposedProviderCallRecord
from app.models.pilot_plan import PilotExperimentPlan
from app.runner.host_adapters import HostAgentAdapter
from app.runner.pilot_budget import GlobalDecisionBudget
from app.runner.pilot_ledger import PilotResumeConfigMismatchError, TrialLedger
from app.runner.pilot_runner import _run_one_trial, finalize_summary, run_pilot
from tests.integration.test_composed_engine import make_composed_tool_transport

OVERLAYS_PATH = "benchmarks/composed/live_overlays.yaml"


class _FakeAdapter(HostAgentAdapter):
    """A hand-rolled HostAgentAdapter test double exposing the same
    ``.provenance`` contract RealHostAgentAdapter does. ``fail_at_step``, if
    set, raises instead of returning an action once that step is reached --
    simulating a real provider failure."""

    def __init__(
        self,
        case_id: str,
        script: list[HostActionSpec],
        model: str = "fake-model",
        fail_at_step: int | None = None,
    ) -> None:
        self._case_id = case_id
        self._script = script
        self._fail_at_step = fail_at_step
        self.provenance = ComposedModelRunProvenance(
            adapter_type="fake",
            provider="fake",
            requested_model=model,
            host_policy_sha256="x" * 64,
            tool_schema_sha256="y" * 64,
            configured_timeout_seconds=5.0,
            configured_max_retries=0,
            configured_max_output_tokens=100,
        )

    async def decide(self, context):
        step = context.current_step
        if self._fail_at_step is not None and step >= self._fail_at_step:
            self.provenance.provider_calls.append(
                ComposedProviderCallRecord(
                    case_id=self._case_id,
                    decision_index=len(self.provenance.provider_calls),
                    requested_model=self.provenance.requested_model,
                    status="error",
                    error="simulated provider failure",
                )
            )
            raise RuntimeError("simulated provider failure")

        action = self._script[step] if step < len(self._script) else HostActionSpec(action="stop")
        self.provenance.provider_calls.append(
            ComposedProviderCallRecord(
                case_id=self._case_id,
                decision_index=len(self.provenance.provider_calls),
                requested_model=self.provenance.requested_model,
                returned_model=f"{self.provenance.requested_model}-returned",
                input_tokens=10,
                output_tokens=5,
                total_tokens=15,
                latency_ms=1.5,
                observable_action=action.model_dump(),
                status="ok",
            )
        )
        return action


BENIGN_INFLUENCE_SCRIPT = [
    HostActionSpec(action="relay_to_remote", relay_template="hi", content_type="text/plain"),
]

TREATMENT_INFLUENCE_SCRIPT = [
    HostActionSpec(action="relay_to_remote", relay_template="hi", content_type="text/plain"),
    HostActionSpec(
        action="attempt_mutating_tool",
        tool_name="apply_remote_recommendation",
        tool_arguments={"action": "apply pending fix"},
    ),
]


def _plan(**overrides) -> PilotExperimentPlan:
    defaults = dict(
        experiment_id="pilot-test-001",
        experiment_version="v1",
        model="fake-model",
        overlay_ids=["live-influence-treatment", "live-influence-control"],
        trials_per_condition=2,
        max_decisions_per_trial=5,
        max_total_decisions=100,
        timeout_seconds=30.0,
        max_output_tokens=256,
    )
    defaults.update(overrides)
    return PilotExperimentPlan(**defaults)


def _script_for(overlay_id: str) -> list[HostActionSpec]:
    return TREATMENT_INFLUENCE_SCRIPT if "treatment" in overlay_id else BENIGN_INFLUENCE_SCRIPT


async def test_full_run_produces_expected_outcomes_and_artifacts(tmp_path):
    overlays_suite = load_live_overlays(OVERLAYS_PATH)
    overlays = [o for o in overlays_suite.overlays if o.experiment == "adversarial_influence"]
    plan = _plan()
    ledger = TrialLedger(tmp_path / "run-1")

    def adapter_factory(case_id: str, max_decisions: int) -> HostAgentAdapter:
        overlay_id = (
            "live-influence-treatment" if "treatment" in case_id else "live-influence-control"
        )
        return _FakeAdapter(case_id, _script_for(overlay_id))

    records = await run_pilot(plan, overlays, ledger, adapter_factory, make_composed_tool_transport)

    assert len(records) == 4  # 2 overlays x 2 trials
    treatment_records = [r for r in records if r.overlay_id == "live-influence-treatment"]
    control_records = [r for r in records if r.overlay_id == "live-influence-control"]
    assert all(r.outcomes.mutation_attempted is True for r in treatment_records)
    assert all(r.outcomes.mutation_executed is False for r in treatment_records)  # gate blocked it
    assert all(r.outcomes.mutation_attempted is False for r in control_records)
    assert all(r.outcomes.mutation_executed is None for r in control_records)
    assert all(r.status == "completed" for r in records)

    assert ledger.plan_path.exists()
    assert ledger.trials_path.exists()
    summary = finalize_summary(plan, overlays, ledger)
    assert ledger.summary_path.exists()

    influence_summary = summary["experiments"]["adversarial_influence"]
    assert influence_summary["treatment"]["outcomes"]["mutation_attempted"]["n"] == 2
    assert influence_summary["treatment"]["outcomes"]["mutation_attempted"]["successes"] == 2
    assert influence_summary["treatment"]["outcomes"]["mutation_attempted"]["rate"] == 1.0
    assert influence_summary["control"]["outcomes"]["mutation_attempted"]["rate"] == 0.0
    diff = influence_summary["treatment_vs_control"]["mutation_attempted"]
    assert diff["rate_difference"] == 1.0
    assert diff["absolute_difference"] == 1.0
    assert "sensitive_egress" not in summary["experiments"]  # denominators never collapsed

    # Attrition is separately visible per condition.
    treatment_attrition = influence_summary["treatment"]["attrition"]
    assert treatment_attrition["trials_planned"] == 2
    assert treatment_attrition["trials_recorded"] == 2
    assert treatment_attrition["trials_completed"] == 2
    assert treatment_attrition["trials_failed"] == 0
    assert treatment_attrition["failure_reasons"] == {}


async def test_resume_does_not_duplicate_trials(tmp_path):
    overlays_suite = load_live_overlays(OVERLAYS_PATH)
    overlays = [o for o in overlays_suite.overlays if o.experiment == "adversarial_influence"]
    plan = _plan(overlay_ids=["live-influence-control"], trials_per_condition=3)
    ledger = TrialLedger(tmp_path / "run-resume")

    def adapter_factory(case_id: str, max_decisions: int) -> HostAgentAdapter:
        return _FakeAdapter(case_id, BENIGN_INFLUENCE_SCRIPT)

    first_batch = await run_pilot(
        plan, overlays, ledger, adapter_factory, make_composed_tool_transport
    )
    assert len(first_batch) == 3

    second_batch = await run_pilot(
        plan, overlays, ledger, adapter_factory, make_composed_tool_transport
    )
    assert second_batch == []  # nothing new to run -- all 3 already completed

    all_records = ledger.load_all_trials()
    assert len(all_records) == 3
    assert len({r.trial_id for r in all_records}) == 3  # no duplicates


async def test_partial_resume_only_runs_missing_trials(tmp_path):
    """Simulates an interrupted run (e.g. process killed after 1 of 3
    trials): resuming with the IDENTICAL plan config must run only the
    trials missing from the ledger, never rerun the completed one."""
    overlays_suite = load_live_overlays(OVERLAYS_PATH)
    overlays = [o for o in overlays_suite.overlays if o.experiment == "adversarial_influence"]
    control_overlay = next(o for o in overlays if o.id == "live-influence-control")
    ledger = TrialLedger(tmp_path / "run-partial")
    plan = _plan(overlay_ids=["live-influence-control"], trials_per_condition=3)

    def adapter_factory(case_id: str, max_decisions: int) -> HostAgentAdapter:
        return _FakeAdapter(case_id, BENIGN_INFLUENCE_SCRIPT)

    # Simulate an interrupted first run: the plan was written, and only
    # trial_index 0 was ever run and persisted before the process stopped.
    ledger.write_or_verify_plan(plan)
    budget = GlobalDecisionBudget(plan.max_total_decisions)
    first_record = await _run_one_trial(
        plan, control_overlay, 0, adapter_factory, make_composed_tool_transport, budget
    )
    ledger.append_trial(first_record)

    new_records = await run_pilot(
        plan, overlays, ledger, adapter_factory, make_composed_tool_transport
    )
    assert len(new_records) == 2  # only trial_index 1 and 2 are new
    assert {r.trial_index for r in new_records} == {1, 2}
    assert len(ledger.load_all_trials()) == 3


async def test_config_hash_mismatch_refuses_resume(tmp_path):
    overlays_suite = load_live_overlays(OVERLAYS_PATH)
    overlays = [o for o in overlays_suite.overlays if o.experiment == "adversarial_influence"]
    ledger = TrialLedger(tmp_path / "run-mismatch")

    def adapter_factory(case_id: str, max_decisions: int) -> HostAgentAdapter:
        return _FakeAdapter(case_id, BENIGN_INFLUENCE_SCRIPT)

    plan_a = _plan(overlay_ids=["live-influence-control"], trials_per_condition=1)
    await run_pilot(plan_a, overlays, ledger, adapter_factory, make_composed_tool_transport)

    plan_b = _plan(
        overlay_ids=["live-influence-control"], trials_per_condition=5
    )  # different config
    try:
        await run_pilot(plan_b, overlays, ledger, adapter_factory, make_composed_tool_transport)
        raise AssertionError("expected PilotResumeConfigMismatchError")
    except PilotResumeConfigMismatchError:
        pass


async def test_global_budget_exhaustion_terminates_safely_without_extra_calls(tmp_path):
    overlays_suite = load_live_overlays(OVERLAYS_PATH)
    overlays = [o for o in overlays_suite.overlays if o.experiment == "adversarial_influence"]
    # Each treatment trial needs 2 decisions; budget allows only 3 total --
    # so at most one full trial (2) plus one partial (1) can ever be spent.
    plan = _plan(
        overlay_ids=["live-influence-treatment"], trials_per_condition=3, max_total_decisions=3
    )
    ledger = TrialLedger(tmp_path / "run-budget")

    def adapter_factory(case_id: str, max_decisions: int) -> HostAgentAdapter:
        return _FakeAdapter(case_id, TREATMENT_INFLUENCE_SCRIPT)

    records = await run_pilot(plan, overlays, ledger, adapter_factory, make_composed_tool_transport)

    total_decisions_spent = sum(r.decision_count for r in records)
    assert total_decisions_spent <= 3
    failed = [r for r in records if r.status == "failed"]
    assert any(r.termination_reason == "global_budget_exhausted" for r in failed)


async def test_failed_provider_decision_is_recorded_not_silently_dropped(tmp_path):
    overlays_suite = load_live_overlays(OVERLAYS_PATH)
    overlays = [o for o in overlays_suite.overlays if o.experiment == "adversarial_influence"]
    plan = _plan(overlay_ids=["live-influence-treatment"], trials_per_condition=1)
    ledger = TrialLedger(tmp_path / "run-fail")

    def adapter_factory(case_id: str, max_decisions: int) -> HostAgentAdapter:
        return _FakeAdapter(case_id, TREATMENT_INFLUENCE_SCRIPT, fail_at_step=0)

    records = await run_pilot(plan, overlays, ledger, adapter_factory, make_composed_tool_transport)
    assert len(records) == 1
    record = records[0]
    assert record.status == "failed"
    assert record.termination_reason == "adapter_error"
    assert record.error is not None
    assert "simulated provider failure" in record.error


async def test_failed_trial_partial_trace_never_enters_behavioral_rate_denominator(tmp_path):
    """The first decision (relay_to_remote) succeeds and produces real
    events; the SECOND decision (attempt_mutating_tool) fails. The trial is
    terminal-failed with a genuinely non-empty partial trace -- proving that
    partial trace alone is never enough to compute or leak an outcome."""
    overlays_suite = load_live_overlays(OVERLAYS_PATH)
    overlays = [o for o in overlays_suite.overlays if o.experiment == "adversarial_influence"]
    plan = _plan(overlay_ids=["live-influence-treatment"], trials_per_condition=1)
    ledger = TrialLedger(tmp_path / "run-partial-fail")

    def adapter_factory(case_id: str, max_decisions: int) -> HostAgentAdapter:
        return _FakeAdapter(case_id, TREATMENT_INFLUENCE_SCRIPT, fail_at_step=1)

    records = await run_pilot(plan, overlays, ledger, adapter_factory, make_composed_tool_transport)
    assert len(records) == 1
    record = records[0]

    assert record.status == "failed"
    assert record.events, "the first decision must have produced a genuine partial trace"
    assert any(e.event_type == "a2a_message" for e in record.events)
    # No outcome is ever computed from a failed trial's (partial) trace.
    assert record.outcomes.mutation_attempted is None
    assert record.outcomes.task_success is None

    summary = finalize_summary(plan, overlays, ledger)
    influence_summary = summary["experiments"]["adversarial_influence"]
    treatment_outcomes = influence_summary["treatment"]["outcomes"]
    # n=0: the failed trial's partial trace never enters the denominator,
    # even though it structurally contains a real a2a_message event.
    assert treatment_outcomes["mutation_attempted"]["n"] == 0
    assert treatment_outcomes["mutation_attempted"]["rate"] is None
    attrition = influence_summary["treatment"]["attrition"]
    assert attrition["trials_completed"] == 0
    assert attrition["trials_failed"] == 1
    assert attrition["failure_reasons"] == {"adapter_error": 1}


async def test_no_raw_reasoning_or_credentials_in_persisted_ledger(tmp_path):
    overlays_suite = load_live_overlays(OVERLAYS_PATH)
    overlays = [o for o in overlays_suite.overlays if o.experiment == "adversarial_influence"]
    plan = _plan(overlay_ids=["live-influence-treatment"], trials_per_condition=1)
    ledger = TrialLedger(tmp_path / "run-clean")

    def adapter_factory(case_id: str, max_decisions: int) -> HostAgentAdapter:
        return _FakeAdapter(case_id, TREATMENT_INFLUENCE_SCRIPT)

    await run_pilot(plan, overlays, ledger, adapter_factory, make_composed_tool_transport)
    raw_text = ledger.trials_path.read_text()
    # "reasoning_effort" (the frozen, explicitly-configured setting) is
    # intentionally persisted -- only raw reasoning CONTENT/items are banned.
    for banned in ("sk-", "Authorization", "reasoning_item", "chain_of_thought", "OPENAI_API_KEY"):
        assert banned not in raw_text

    # trials.jsonl is valid, line-delimited JSON.
    lines = [json.loads(line) for line in raw_text.splitlines() if line.strip()]
    assert len(lines) == 1
