"""Phase 3D.2.1: the true matched-control composition-only-failure
experiment, plus the separate protocol-local-gap diagnostic.

Proves, with real execution (never asserted):
- an MCP-only control that produces the same sensitive canary but never
  transfers it to A2A at all -- PASS, and never emits any A2A event
- an A2A-only control performing the identical delegation with a
  structurally matched PUBLIC twin canary -- PASS, with no sensitive
  provenance anywhere in its trace
- the composed workflow alone introduces the forbidden flow: it produces
  the sensitive canary via MCP and relays it across host -> remote / a2a,
  an edge the case never authorizes for sensitive content -- FAIL

...and, separately, that a single-protocol control which does carry the
actual sensitive canary over A2A passes A2A's own native evaluators anyway
(``protocol_local_gap``) -- a distinct, non-composition finding that must
never be conflated with ``composition_only_failure``.
"""

from __future__ import annotations

from app.core.composed_benchmarks import load_composed_suite
from app.core.composed_controls import load_matched_control
from app.evaluators.composed_composition import evaluate_composition_failure
from app.evaluators.composed_egress import evaluate_sensitive_egress
from app.evaluators.composed_protocol_gap import evaluate_protocol_local_gap
from app.evaluators.composed_provenance import evaluate_propagation
from app.models.a2a import A2ABenchmarkSuite
from app.models.benchmark import BenchmarkSuite
from app.models.composed import canary_token, composed_deterministic_id
from app.reporting.composed_scoring import failure_rate_over_applicable
from app.runner.a2a_suite_execution import execute_a2a_suite
from app.runner.composed_controls import run_matched_controls
from app.runner.composed_engine import ComposedBenchmarkRunner
from app.runner.suite_execution import execute_suite
from tests.integration.test_composed_engine import make_composed_tool_transport

SUITE_PATH = "benchmarks/composed/composed_suite.yaml"
CONTROLS_PATH = "benchmarks/composed/isolated_controls.yaml"
CASE_ID = "composed-isolated-pass-composition-fails-001-sensitive-egress"
SENSITIVE_CANARY_NAME = "local-secret-2"
PUBLIC_TWIN_CANARY_NAME = "local-secret-2-public-twin"
CANARY_NAMES = [SENSITIVE_CANARY_NAME, PUBLIC_TWIN_CANARY_NAME]


def _load_case():
    suite = load_composed_suite(SUITE_PATH)
    (case,) = [c for c in suite.cases if c.id == CASE_ID]
    return case


def _load_control():
    return load_matched_control(CONTROLS_PATH, CASE_ID, canary_names=CANARY_NAMES)


def _events_for_equality(events) -> list[dict]:
    return [event.model_dump(exclude={"recorded_at"}) for event in events]


async def test_composed_egress_case_loads_with_declared_sensitive_canary_and_edges():
    case = _load_case()
    assert case.category == "composed_isolated_pass_fails"
    assert [c.sensitivity for c in case.provenance_canaries] == ["sensitive"]
    allowed = case.allowed_sensitive_edges[0]
    assert (allowed.source, allowed.dest, allowed.protocol) == ("local_tool", "host", "mcp")


async def test_composed_run_has_sensitive_canary_origin_at_mcp_result():
    case = _load_case()
    events = await ComposedBenchmarkRunner(
        local_transport_factory=make_composed_tool_transport
    ).run_case(case)

    expected_canary_id = composed_deterministic_id(case.id, "canary", SENSITIVE_CANARY_NAME)
    token = canary_token(case.id, SENSITIVE_CANARY_NAME)

    mcp_request = next(e for e in events if e.event_type == "mcp_tool_request")
    mcp_result = next(e for e in events if e.event_type == "mcp_tool_result")

    assert token not in str(mcp_request.payload)
    assert mcp_request.canary_ids == []
    assert mcp_result.canary_ids == [expected_canary_id]
    first_direct_index = next(i for i, e in enumerate(events) if expected_canary_id in e.canary_ids)
    assert events[first_direct_index].event_type == "mcp_tool_result"


async def test_only_composed_run_crosses_host_to_remote_with_sensitive_canary():
    case = _load_case()
    control = _load_control()
    expected_canary_id = composed_deterministic_id(case.id, "canary", SENSITIVE_CANARY_NAME)

    # The composed run DOES cross host -> remote / a2a with the sensitive canary.
    events = await ComposedBenchmarkRunner(
        local_transport_factory=make_composed_tool_transport
    ).run_case(case)
    a2a_message = next(e for e in events if e.event_type == "a2a_message")
    assert a2a_message.canary_ids == [expected_canary_id]
    assert (a2a_message.source, a2a_message.dest, a2a_message.protocol) == (
        "host",
        "remote",
        "a2a",
    )
    assert a2a_message.source != "local_tool"

    # The TRUE a2a_control (public twin) never carries the sensitive canary at all.
    a2a_suite = A2ABenchmarkSuite(name="check", version="0.1.0", cases=[control.a2a_control])
    a2a_report = await execute_a2a_suite("check-a2a-control", a2a_suite)
    interactions = a2a_report.per_test[0].a2a_interactions
    sensitive_token = canary_token(case.id, SENSITIVE_CANARY_NAME)
    assert not any(sensitive_token in (record.request_content or "") for record in interactions)
    public_twin_token = canary_token(case.id, PUBLIC_TWIN_CANARY_NAME)
    assert any(public_twin_token in (record.request_content or "") for record in interactions)


async def test_mcp_only_control_never_emits_an_a2a_event():
    control = _load_control()
    mcp_suite = BenchmarkSuite(name="check", version="0.1.0", cases=[control.mcp_control])
    async with make_composed_tool_transport() as transport:
        mcp_report = await execute_suite("check-mcp-control", mcp_suite, transport)
    case_report = mcp_report.per_test[0]
    assert case_report.protocol == "mcp"
    assert case_report.a2a_interactions is None
    assert case_report.passed is True


async def test_a2a_only_control_has_no_sensitive_provenance():
    case = _load_case()
    control = _load_control()
    a2a_suite = A2ABenchmarkSuite(name="check", version="0.1.0", cases=[control.a2a_control])
    a2a_report = await execute_a2a_suite("check-a2a-control-2", a2a_suite)
    case_report = a2a_report.per_test[0]
    assert case_report.passed is True

    sensitive_token = canary_token(case.id, SENSITIVE_CANARY_NAME)
    for record in case_report.a2a_interactions:
        assert sensitive_token not in (record.request_content or "")
        if record.remote_message is not None:
            for part in record.remote_message.parts:
                assert sensitive_token not in (part.text or "")
        for artifact in record.artifacts:
            for part in artifact.parts:
                assert sensitive_token not in (part.text or "")


async def test_both_true_isolated_controls_pass_and_composed_run_fails():
    case = _load_case()
    control = _load_control()

    events = await ComposedBenchmarkRunner(
        local_transport_factory=make_composed_tool_transport
    ).run_case(case)
    propagation_result = evaluate_propagation(case, events)
    egress_result = evaluate_sensitive_egress(case, events)
    applicable = [r for r in (propagation_result, egress_result) if r.applicable]
    composed_case_passed = all(r.passed for r in applicable)
    assert composed_case_passed is False

    results = await run_matched_controls(
        control, mcp_transport_factory=make_composed_tool_transport
    )
    assert results.isolated_mcp_control_passed is True
    assert results.isolated_a2a_control_passed is True

    composition_result = evaluate_composition_failure(
        composed_case_passed,
        results.isolated_mcp_control_passed,
        results.isolated_a2a_control_passed,
    )
    assert composition_result.evaluator_name == "composition_only_failure"
    assert composition_result.applicable is True
    assert composition_result.passed is False  # composition-only failure detected

    assert failure_rate_over_applicable([egress_result]) == 1.0
    assert failure_rate_over_applicable([composition_result]) == 1.0


async def test_protocol_local_gap_is_detected_and_kept_separate_from_composition_failure():
    case = _load_case()
    control = _load_control()

    results = await run_matched_controls(
        control, mcp_transport_factory=make_composed_tool_transport
    )
    assert results.a2a_native_gap_control_passed is True  # native evaluators are blind to this

    gap_result = evaluate_protocol_local_gap(
        control.a2a_native_gap_control,
        results.a2a_native_gap_control_passed,
        case.id,
        SENSITIVE_CANARY_NAME,
    )
    assert gap_result.evaluator_name == "protocol_local_gap"
    assert gap_result.applicable is True
    assert gap_result.evidence["protocol_local_gap_detected"] is True
    assert gap_result.passed is False  # "passed" means "no gap"; a gap was found

    # The two findings must never be conflated: distinct evaluator names.
    events = await ComposedBenchmarkRunner(
        local_transport_factory=make_composed_tool_transport
    ).run_case(case)
    propagation_result = evaluate_propagation(case, events)
    egress_result = evaluate_sensitive_egress(case, events)
    composed_case_passed = all(
        r.passed for r in (propagation_result, egress_result) if r.applicable
    )
    composition_result = evaluate_composition_failure(
        composed_case_passed,
        results.isolated_mcp_control_passed,
        results.isolated_a2a_control_passed,
    )
    assert {gap_result.evaluator_name, composition_result.evaluator_name} == {
        "protocol_local_gap",
        "composition_only_failure",
    }


async def test_composed_egress_execution_is_deterministic_across_two_runs():
    case = _load_case()
    run_a = await ComposedBenchmarkRunner(
        local_transport_factory=make_composed_tool_transport
    ).run_case(case)
    run_b = await ComposedBenchmarkRunner(
        local_transport_factory=make_composed_tool_transport
    ).run_case(case)
    assert _events_for_equality(run_a) == _events_for_equality(run_b)
