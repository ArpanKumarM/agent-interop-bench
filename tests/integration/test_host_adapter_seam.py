"""Phase 4A.1: the HostAgentAdapter seam is a no-op for existing behavior,
and no benchmark ground truth / provenance label ever reaches a
HostDecisionContext produced by a real run -- checked by recording every
context ComposedBenchmarkRunner actually built and serialized.

Literal canary/trigger text already present inside an observed payload is
NOT stripped -- it is real content the host actually saw. Only fixture
ground truth (category, expected_outcome, ...) and provenance labels
(content_class, origin_trust, sensitivity, canary_ids, ancestor lists,
allowed_sensitive_edges) must never appear.
"""

from __future__ import annotations

from app.core.composed_benchmarks import load_composed_suite
from app.models.composed import canary_token
from app.models.host_context import HostDecisionContext
from app.runner.composed_engine import ComposedBenchmarkRunner
from app.runner.host_adapters import HostAgentAdapter, ScriptedHostAdapter
from tests.integration.test_composed_engine import make_composed_tool_transport

SUITE_PATH = "benchmarks/composed/composed_suite.yaml"
PROPAGATION_CASE_ID = "composed-propagation-001-canary-crosses-mcp-to-a2a"

BANNED_KEYS = {
    "expected_outcome",
    "category",
    "content_class",
    "origin_trust",
    "sensitivity",
    "canary_ids",
    "propagated_canary_ids",
    "adversarial_ancestor_ids",
    "sensitive_ancestor_ids",
    "allowed_sensitive_edges",
    "evaluator_name",
    "passed",
    "applicable",
    "simulated_host_actions",
    "simulated_remote_behavior",
    "simulated_client_actions",
    "expected_task_state",
    "expected_artifact",
    "provenance_canaries",
    "action_triggers",
    "parent_event_ids",
}


class _RecordingAdapter(HostAgentAdapter):
    """Wraps a real adapter, recording every HostDecisionContext it receives."""

    def __init__(self, delegate: HostAgentAdapter) -> None:
        self._delegate = delegate
        self.contexts: list[HostDecisionContext] = []

    async def decide(self, context):
        self.contexts.append(context)
        return await self._delegate.decide(context)


def _load_case(case_id: str):
    suite = load_composed_suite(SUITE_PATH)
    (case,) = [c for c in suite.cases if c.id == case_id]
    return case


def _all_keys(obj) -> set[str]:
    keys: set[str] = set()
    if isinstance(obj, dict):
        for key, value in obj.items():
            keys.add(key)
            keys |= _all_keys(value)
    elif isinstance(obj, list):
        for item in obj:
            keys |= _all_keys(item)
    return keys


async def test_default_scripted_adapter_produces_byte_identical_trace_to_explicit_one():
    """Passing ScriptedHostAdapter.for_case(case) explicitly must produce the
    exact same trace as relying on the runner's default -- the seam is a
    pure refactor, not a behavior change."""
    for case_id in [
        "composed-benign-001-happy-path",
        "composed-propagation-001-canary-crosses-mcp-to-a2a",
        "composed-isolated-pass-composition-fails-001-sensitive-egress",
        "composed-influence-001-adversarial-artifact",
        "composed-influence-control-001-benign-artifact",
    ]:
        case = _load_case(case_id)

        default_run = await ComposedBenchmarkRunner(
            local_transport_factory=make_composed_tool_transport
        ).run_case(case)
        explicit_run = await ComposedBenchmarkRunner(
            local_transport_factory=make_composed_tool_transport
        ).run_case(case, adapter=ScriptedHostAdapter.for_case(case))

        default_dump = [e.model_dump(exclude={"recorded_at"}) for e in default_run]
        explicit_dump = [e.model_dump(exclude={"recorded_at"}) for e in explicit_run]
        assert default_dump == explicit_dump


async def test_no_benchmark_ground_truth_reaches_host_decision_context():
    for case_id in [
        "composed-benign-001-happy-path",
        "composed-propagation-001-canary-crosses-mcp-to-a2a",
        "composed-isolated-pass-composition-fails-001-sensitive-egress",
        "composed-influence-001-adversarial-artifact",
        "composed-influence-control-001-benign-artifact",
    ]:
        case = _load_case(case_id)
        recorder = _RecordingAdapter(ScriptedHostAdapter.for_case(case))
        await ComposedBenchmarkRunner(
            local_transport_factory=make_composed_tool_transport, adapter=recorder
        ).run_case(case)

        assert recorder.contexts, f"no HostDecisionContext was ever built for {case_id!r}"
        for context in recorder.contexts:
            observed_keys = _all_keys(context.model_dump())
            leaked = observed_keys & BANNED_KEYS
            assert not leaked, f"case {case_id!r} leaked banned keys into context: {leaked}"


async def test_literal_canary_text_is_not_stripped_from_observable_history():
    case = _load_case(PROPAGATION_CASE_ID)
    recorder = _RecordingAdapter(ScriptedHostAdapter.for_case(case))
    await ComposedBenchmarkRunner(
        local_transport_factory=make_composed_tool_transport, adapter=recorder
    ).run_case(case)

    token = canary_token(case.id, "local-secret-1")
    final_context = recorder.contexts[-1]
    payload_texts = [str(event.payload) for event in final_context.history]
    assert any(token in text for text in payload_texts), (
        "literal canary text observed in a real payload must remain visible in "
        "the sanitized history, not be stripped"
    )
