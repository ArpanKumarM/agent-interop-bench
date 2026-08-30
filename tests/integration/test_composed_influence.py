"""Phase 3D.3.1: cross-protocol behavioral influence + containment, via ONE
identical, mechanically-conditional shared host reaction policy.

Both the adversarial case and its benign control script the exact same
``simulated_host_actions`` (a shared YAML anchor -- the same node, not just
visually identical fixtures): "relay to remote, then attempt the configured
mutation only if the most recently observed artifact contains the declared
trigger's exact token." Whether the mutation is ever attempted is therefore
a mechanical function of which artifact content the remote fixture actually
produced -- never an authored difference in the host's script. Neither
result is asserted by category name or case ID: both are computed from the
real DAG (``adversarial_ancestor_ids``, ``executed``).
"""

from __future__ import annotations

from app.core.composed_benchmarks import load_composed_suite
from app.evaluators.composed_influence import (
    evaluate_containment,
    evaluate_unsafe_execution,
    evaluate_unsafe_influence,
)
from app.models.composed import action_trigger_token
from app.reporting.composed_scoring import (
    containment_rate,
    unsafe_execution_rate,
    unsafe_influence_rate,
)
from app.runner.composed_engine import ComposedBenchmarkRunner
from tests.integration.test_composed_engine import make_composed_tool_transport

SUITE_PATH = "benchmarks/composed/composed_suite.yaml"
ADVERSARIAL_CASE_ID = "composed-influence-001-adversarial-artifact"
BENIGN_CASE_ID = "composed-influence-control-001-benign-artifact"
TRIGGER_NAME = "apply-fix-trigger"


def _load_case(case_id: str):
    suite = load_composed_suite(SUITE_PATH)
    (case,) = [c for c in suite.cases if c.id == case_id]
    return case


def _events_for_equality(events) -> list[dict]:
    return [event.model_dump(exclude={"recorded_at"}) for event in events]


async def _run(case_id: str):
    case = _load_case(case_id)
    return await ComposedBenchmarkRunner(
        local_transport_factory=make_composed_tool_transport
    ).run_case(case)


async def test_both_cases_use_the_identical_host_policy_configuration():
    adversarial_case = _load_case(ADVERSARIAL_CASE_ID)
    benign_case = _load_case(BENIGN_CASE_ID)
    # Same length, same action sequence, same tool/arguments/trigger/approval
    # config -- the fixture never authors a different host script per case.
    assert [a.model_dump() for a in adversarial_case.simulated_host_actions] == [
        a.model_dump() for a in benign_case.simulated_host_actions
    ]


async def test_adversarial_artifact_alone_contains_the_trigger_token():
    adversarial_case = _load_case(ADVERSARIAL_CASE_ID)
    benign_case = _load_case(BENIGN_CASE_ID)
    token = action_trigger_token(ADVERSARIAL_CASE_ID, TRIGGER_NAME)
    # The token is per-case-id, but checking each case's own artifact text
    # for its own computed token is what the shared runtime policy does too.
    adversarial_events = await _run(ADVERSARIAL_CASE_ID)
    benign_events = await _run(BENIGN_CASE_ID)

    adversarial_artifact = next(e for e in adversarial_events if e.event_type == "a2a_artifact")
    benign_artifact = next(e for e in benign_events if e.event_type == "a2a_artifact")

    assert token in adversarial_artifact.payload["text"]
    assert action_trigger_token(BENIGN_CASE_ID, TRIGGER_NAME) not in benign_artifact.payload["text"]
    assert adversarial_case.action_triggers[0].name == TRIGGER_NAME
    assert benign_case.action_triggers[0].name == TRIGGER_NAME


async def test_adversarial_case_causal_trace_mutation_descends_from_artifact():
    events = await _run(ADVERSARIAL_CASE_ID)

    event_types = [event.event_type for event in events]
    assert event_types == [
        "a2a_message",
        "a2a_task_state_transition",
        "a2a_artifact",
        "mutation_action",
    ]

    artifact = next(e for e in events if e.event_type == "a2a_artifact")
    mutation = next(e for e in events if e.event_type == "mutation_action")

    assert artifact.origin_trust == "untrusted"
    assert artifact.content_class == "adversarial"

    # Causal descent via parent_event_ids, not category-name inference.
    assert mutation.parent_event_ids == [artifact.event_id]
    assert artifact.event_id in mutation.adversarial_ancestor_ids

    assert mutation.is_mutating is True
    assert mutation.approved is False
    assert mutation.executed is False
    assert mutation.source == "host"
    assert mutation.dest == "local_tool"
    assert mutation.protocol == "mcp"


async def test_benign_control_has_no_adversarial_ancestry_and_no_mutation_attempt():
    events = await _run(BENIGN_CASE_ID)

    event_types = [event.event_type for event in events]
    assert "mutation_action" not in event_types

    artifact = next(e for e in events if e.event_type == "a2a_artifact")
    assert artifact.content_class == "non_adversarial"
    assert all(not event.adversarial_ancestor_ids for event in events)


async def test_unsafe_influence_detected_only_in_adversarial_case():
    adversarial_events = await _run(ADVERSARIAL_CASE_ID)
    benign_events = await _run(BENIGN_CASE_ID)

    adversarial_result = evaluate_unsafe_influence(adversarial_events)
    assert adversarial_result.passed is False  # influence detected
    assert adversarial_result.evidence["attempt_count"] == 1
    assert len(adversarial_result.evidence["influenced_event_ids"]) == 1

    benign_result = evaluate_unsafe_influence(benign_events)
    assert benign_result.applicable is False  # no mutation attempts at all


async def test_containment_detected_and_unsafe_execution_is_zero():
    events = await _run(ADVERSARIAL_CASE_ID)

    containment_result = evaluate_containment(events)
    assert containment_result.applicable is True
    assert containment_result.passed is True  # contained

    execution_result = evaluate_unsafe_execution(events)
    assert execution_result.applicable is True
    assert execution_result.passed is True  # no unsafe execution
    assert execution_result.evidence["executed_count"] == 0

    assert unsafe_influence_rate(events) == 1.0
    assert containment_rate(events) == 1.0
    assert unsafe_execution_rate(events) == 0.0


async def test_benign_control_metrics_are_not_applicable():
    events = await _run(BENIGN_CASE_ID)
    assert unsafe_influence_rate(events) is None
    assert containment_rate(events) is None
    assert unsafe_execution_rate(events) is None
    assert evaluate_containment(events).applicable is False
    assert evaluate_unsafe_execution(events).applicable is False


async def test_composed_influence_execution_is_deterministic_across_two_runs():
    for case_id in (ADVERSARIAL_CASE_ID, BENIGN_CASE_ID):
        run_a = await _run(case_id)
        run_b = await _run(case_id)
        assert _events_for_equality(run_a) == _events_for_equality(run_b)
