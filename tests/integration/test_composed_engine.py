"""Phase 3D.1 integration tests: the composed runner executes a real local
MCP protocol interaction (a real stdio subprocess, the unmodified
``mock_servers.github_mock``) interleaved with a real in-process A2A
``TestClient`` interaction (the unmodified ``mock_servers.a2a_mock``),
emitting one unified ``CrossProtocolEvent`` trace. No sockets, no live
network, no OpenAI calls.
"""

from __future__ import annotations

import sys

from app.core.composed_benchmarks import load_composed_suite
from app.evaluators.composed_provenance import evaluate_propagation
from app.models.composed import canary_token, composed_deterministic_id
from app.runner.composed_engine import ComposedBenchmarkRunner
from app.runner.transport import StdioMCPTransport
from tests.integration.conftest import make_mock_transport

SUITE_PATH = "benchmarks/composed/composed_suite.yaml"


def make_composed_tool_transport() -> StdioMCPTransport:
    """Build (but don't connect) a transport for the dedicated composed-suite
    tool server (mock_servers/composed_tool_mock.py) -- never the 29-case
    suite's github_mock, and never modifying it."""
    return StdioMCPTransport(command=sys.executable, args=["-m", "mock_servers.composed_tool_mock"])


def _transport_factory_for(case_id: str):
    if case_id == "composed-propagation-001-canary-crosses-mcp-to-a2a":
        return make_composed_tool_transport
    return make_mock_transport


def _load_case(case_id: str):
    suite = load_composed_suite(SUITE_PATH)
    (case,) = [c for c in suite.cases if c.id == case_id]
    return case


def _events_for_equality(events) -> list[dict]:
    """Strip the non-scientific, optional wall-clock field before comparing
    two runs -- only ``seq`` and the rest of the event's content are used
    for deterministic equality, per the Phase 3D design lock."""
    return [event.model_dump(exclude={"recorded_at"}) for event in events]


async def test_composed_suite_loads_exactly_three_cases():
    suite = load_composed_suite(SUITE_PATH)
    assert {c.id for c in suite.cases} == {
        "composed-benign-001-happy-path",
        "composed-propagation-001-canary-crosses-mcp-to-a2a",
        "composed-isolated-pass-composition-fails-001-sensitive-egress",
    }


async def test_composed_benign_case_produces_unified_trace_and_succeeds():
    case = _load_case("composed-benign-001-happy-path")
    runner = ComposedBenchmarkRunner(local_transport_factory=_transport_factory_for(case.id))
    events = await runner.run_case(case)

    protocols = [event.protocol for event in events]
    assert protocols == ["mcp", "mcp", "a2a", "a2a", "a2a"]
    event_types = [event.event_type for event in events]
    assert event_types == [
        "mcp_tool_request",
        "mcp_tool_result",
        "a2a_message",
        "a2a_task_state_transition",
        "a2a_artifact",
    ]
    # seq is strictly increasing and every non-root event's parent already
    # exists earlier in the same list -- the DAG invariants held throughout.
    assert [event.seq for event in events] == list(range(len(events)))
    for event in events[1:]:
        assert all(
            pid in {e.event_id for e in events[: event.seq]} for pid in event.parent_event_ids
        )

    result = evaluate_propagation(case, events)
    assert result.applicable is False  # no canaries declared for the benign case


async def test_composed_propagation_case_canary_crosses_mcp_to_a2a():
    case = _load_case("composed-propagation-001-canary-crosses-mcp-to-a2a")
    runner = ComposedBenchmarkRunner(local_transport_factory=_transport_factory_for(case.id))
    events = await runner.run_case(case)

    expected_canary_id = composed_deterministic_id(case.id, "canary", "local-secret-1")
    token = canary_token(case.id, "local-secret-1")

    mcp_request_event = next(e for e in events if e.event_type == "mcp_tool_request")
    mcp_result_event = next(e for e in events if e.event_type == "mcp_tool_result")
    a2a_message_event = next(e for e in events if e.event_type == "a2a_message")
    a2a_artifact_event = next(e for e in events if e.event_type == "a2a_artifact")

    # 1. The request never contains the canary token itself (only the plain
    #    label "local-secret-1", which is not the token).
    assert token not in str(mcp_request_event.payload)
    assert mcp_request_event.canary_ids == []

    # 2. mcp_tool_result is the FIRST event with a direct observation.
    assert token in str(mcp_result_event.payload)
    assert mcp_result_event.canary_ids == [expected_canary_id]
    first_direct_index = next(i for i, e in enumerate(events) if expected_canary_id in e.canary_ids)
    assert events[first_direct_index].event_type == "mcp_tool_result"

    # 3. The A2A message directly contains it (host relayed the tool result
    #    verbatim), not merely by ancestry.
    assert token in str(a2a_message_event.payload)
    assert a2a_message_event.canary_ids == [expected_canary_id]

    # 4. The A2A artifact directly contains it too (the scripted remote-agent
    #    fixture echoes the same canary back), not merely by ancestry.
    assert token in str(a2a_artifact_event.payload)
    assert a2a_artifact_event.canary_ids == [expected_canary_id]

    # 5. All three direct observations share the identical deterministic canary_id.
    assert (
        mcp_result_event.canary_ids
        == a2a_message_event.canary_ids
        == a2a_artifact_event.canary_ids
        == [expected_canary_id]
    )

    result = evaluate_propagation(case, events)
    assert result.applicable is True
    assert result.passed is True
    assert result.evidence["crossed_canaries"] == ["local-secret-1"]


async def test_composed_execution_is_deterministic_across_two_runs():
    for case_id in [
        "composed-benign-001-happy-path",
        "composed-propagation-001-canary-crosses-mcp-to-a2a",
    ]:
        case = _load_case(case_id)
        factory = _transport_factory_for(case_id)
        run_a = await ComposedBenchmarkRunner(local_transport_factory=factory).run_case(case)
        run_b = await ComposedBenchmarkRunner(local_transport_factory=factory).run_case(case)
        assert _events_for_equality(run_a) == _events_for_equality(run_b), (
            f"case {case_id!r} produced non-identical traces across two runs "
            "(excluding the optional, non-scientific recorded_at field)"
        )
