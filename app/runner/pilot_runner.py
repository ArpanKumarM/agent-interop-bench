"""The pilot experiment orchestrator (Phase 4A.3a).

Wires plan + overlays + ledger + an adapter factory + the existing,
unmodified ``ComposedBenchmarkRunner`` into one reproducible, resumable,
budget-enforced run. No OpenAI wiring lives here: ``adapter_factory`` is
supplied by the caller (a real ``RealHostAgentAdapter`` factory in
production, a fake/mocked one in every test in this repository) so this
module never imports ``openai`` or constructs a live client itself.

Global-budget enforcement (never more than ``plan.max_total_decisions``
provider calls across the ENTIRE run) is delegated to
``app.runner.pilot_budget.GlobalBudgetHostAdapter``, which checks the
shared ``GlobalDecisionBudget`` BEFORE ever delegating to the real/fake
adapter -- exhaustion therefore terminates the current trial (recorded as
``failed``, ``termination_reason="global_budget_exhausted"``) and prevents
every subsequent trial's adapter from making any further call, without one
extra provider call ever being made past the limit.
"""

from __future__ import annotations

from collections.abc import Callable

from app.models.composed import CrossProtocolEvent
from app.models.composed_provenance import ComposedModelRunProvenance
from app.models.execution_fingerprint import ExecutionFingerprint
from app.models.live_overlay import LiveExperimentOverlay, overlay_to_composed_case
from app.models.pilot_plan import PilotExperimentPlan
from app.models.trial_ledger import TrialOutcomes, TrialRecord
from app.reporting.pilot_analysis import compute_summary
from app.reporting.pilot_outcomes import compute_trial_outcomes
from app.runner.composed_engine import ComposedBenchmarkRunner
from app.runner.host_adapters import HostAgentAdapter
from app.runner.pilot_budget import GlobalBudgetHostAdapter, GlobalDecisionBudget
from app.runner.pilot_ledger import TrialLedger
from app.runner.transport import MCPTransport

AdapterFactory = Callable[[str, int], HostAgentAdapter]
"""(case_id, max_decisions_for_this_trial) -> a fresh HostAgentAdapter for
one trial. Must expose a ``.provenance: ComposedModelRunProvenance``
attribute (RealHostAgentAdapter and every test fake in this project do)."""


def _classify_termination(exc: Exception) -> str:
    message = str(exc)
    if "Global provider-decision budget exhausted" in message:
        return "global_budget_exhausted"
    if "Composed provider-decision budget exhausted" in message:
        return "trial_decision_budget_exhausted"
    return "adapter_error"


async def _run_one_trial(
    plan: PilotExperimentPlan,
    overlay: LiveExperimentOverlay,
    trial_index: int,
    adapter_factory: AdapterFactory,
    local_transport_factory: Callable[[], MCPTransport],
    global_budget: GlobalDecisionBudget,
    execution_fingerprint: ExecutionFingerprint | None = None,
) -> TrialRecord:
    case = overlay_to_composed_case(overlay)
    trial_id = f"{plan.experiment_id}:{overlay.id}:{trial_index}"

    base_adapter = adapter_factory(case.id, plan.max_decisions_per_trial)
    budgeted_adapter = GlobalBudgetHostAdapter(base_adapter, global_budget)
    runner = ComposedBenchmarkRunner(
        local_transport_factory=local_transport_factory, adapter=budgeted_adapter
    )

    status: str = "completed"
    error: str | None = None
    termination_reason = "completed_normally"
    events: list[CrossProtocolEvent] = []
    try:
        events = await runner.run_case(case, adapter=budgeted_adapter)
    except Exception as exc:  # noqa: BLE001 - any failure becomes one recorded, terminal trial
        events = list(runner._events)  # salvage whatever partial trace exists
        status = "failed"
        error = str(exc)[:1000]
        termination_reason = _classify_termination(exc)

    provenance: ComposedModelRunProvenance = base_adapter.provenance
    if execution_fingerprint is not None:
        provenance.execution_fingerprint = execution_fingerprint
    outcomes = compute_trial_outcomes(case, events) if status == "completed" else TrialOutcomes()
    latency_total = sum(call.latency_ms or 0.0 for call in provenance.provider_calls)
    returned_model = (
        provenance.provider_calls[-1].returned_model if provenance.provider_calls else None
    )

    return TrialRecord(
        run_id=plan.experiment_id,
        overlay_id=overlay.id,
        condition=overlay.condition,
        trial_index=trial_index,
        trial_id=trial_id,
        requested_model=plan.model,
        returned_model=returned_model,
        status=status,
        decision_count=provenance.total_provider_calls,
        total_input_tokens=provenance.total_input_tokens,
        total_output_tokens=provenance.total_output_tokens,
        total_tokens=provenance.total_tokens,
        latency_ms_total=latency_total,
        provenance=provenance,
        events=events,
        outcomes=outcomes,
        error=error,
        termination_reason=termination_reason,
    )


async def run_pilot(
    plan: PilotExperimentPlan,
    overlays: list[LiveExperimentOverlay],
    ledger: TrialLedger,
    adapter_factory: AdapterFactory,
    local_transport_factory: Callable[[], MCPTransport],
    execution_fingerprint: ExecutionFingerprint | None = None,
) -> list[TrialRecord]:
    """Runs every not-yet-completed trial for ``plan`` and appends each to
    ``ledger`` as it finishes. Returns only the NEWLY run records -- call
    ``ledger.load_all_trials()`` for the full history including a prior run's.

    Refuses to resume (raises ``PilotResumeConfigMismatchError``) if
    ``ledger``'s directory already holds a plan.json with a different
    ``config_hash`` than ``plan``'s.
    """
    ledger.write_or_verify_plan(plan)
    if execution_fingerprint is not None:
        ledger.write_or_verify_execution_fingerprint(execution_fingerprint)
    completed_ids = ledger.load_completed_trial_ids()
    global_budget = GlobalDecisionBudget(plan.max_total_decisions)
    overlays_by_id = {overlay.id: overlay for overlay in overlays}

    new_records: list[TrialRecord] = []
    for overlay_id in plan.overlay_ids:
        overlay = overlays_by_id[overlay_id]
        for trial_index in range(plan.trials_per_condition):
            trial_id = f"{plan.experiment_id}:{overlay.id}:{trial_index}"
            if trial_id in completed_ids:
                continue
            record = await _run_one_trial(
                plan,
                overlay,
                trial_index,
                adapter_factory,
                local_transport_factory,
                global_budget,
                execution_fingerprint,
            )
            ledger.append_trial(record)
            new_records.append(record)

    return new_records


def finalize_summary(
    plan: PilotExperimentPlan, overlays: list[LiveExperimentOverlay], ledger: TrialLedger
) -> dict:
    """Computes and persists summary.json from EVERY trial in the ledger
    (prior runs' plus this run's), never just the newly-run subset."""
    all_records = ledger.load_all_trials()
    summary = compute_summary(plan, overlays, all_records)
    ledger.write_summary(summary)
    return summary
