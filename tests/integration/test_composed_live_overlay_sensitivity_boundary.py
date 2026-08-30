"""Phase 4A.2 (corrected): proves the sensitive-egress live overlay's
treatment/control conditions are genuinely model-observably different, use
one identical host policy, and never leak evaluator/provenance ground
truth into a HostDecisionContext — using a real (mocked-adapter) run
through the actual ComposedBenchmarkRunner, MCP transport, and A2A mock.
"""

from __future__ import annotations

from app.core.live_overlays import load_live_overlays
from app.models.composed import HostActionSpec, canary_token
from app.models.host_context import HostDecisionContext
from app.models.live_overlay import overlay_to_composed_case
from app.runner.composed_engine import ComposedBenchmarkRunner
from app.runner.host_adapters import DEFAULT_HOST_POLICY_TEXT, HostAgentAdapter
from tests.integration.test_composed_engine import make_composed_tool_transport

OVERLAYS_PATH = "benchmarks/composed/live_overlays.yaml"

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
    "provenance_canaries",
    "researcher_notes",
    "parent_event_ids",
}


class _FixedScriptAdapter(HostAgentAdapter):
    """A minimal, non-ScriptedHostAdapter test double: overlay-derived cases
    have empty ``simulated_host_actions``, so a live-overlay run always
    supplies its own explicit adapter -- here, a fixed two-step script."""

    def __init__(self, script) -> None:
        self._script = script

    async def decide(self, context):
        step = context.current_step
        if step >= len(self._script):
            return HostActionSpec(action="stop")
        return self._script[step]


class _RecordingAdapter(HostAgentAdapter):
    def __init__(self, delegate: HostAgentAdapter) -> None:
        self._delegate = delegate
        self.contexts: list[HostDecisionContext] = []

    async def decide(self, context):
        self.contexts.append(context)
        return await self._delegate.decide(context)


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


def _load_overlay(overlay_id: str):
    suite = load_live_overlays(OVERLAYS_PATH)
    (overlay,) = [o for o in suite.overlays if o.id == overlay_id]
    return overlay


async def _run_overlay(overlay_id: str) -> tuple[list, _RecordingAdapter]:
    overlay = _load_overlay(overlay_id)
    case = overlay_to_composed_case(overlay)
    script = [
        HostActionSpec(
            action="call_local_tool",
            tool_name=overlay.local_tool_name,
            tool_arguments=overlay.local_tool_arguments,
        ),
        HostActionSpec(
            action="relay_to_remote",
            relay_template="Local finding: {tool_result_text}",
            content_type="text/plain",
        ),
    ]
    recorder = _RecordingAdapter(_FixedScriptAdapter(script))
    events = await ComposedBenchmarkRunner(
        local_transport_factory=make_composed_tool_transport, adapter=recorder
    ).run_case(case)
    return events, recorder


async def test_treatment_and_control_use_identical_host_policy():
    _, treatment_recorder = await _run_overlay("live-sensitive-egress-treatment")
    _, control_recorder = await _run_overlay("live-sensitive-egress-control")

    assert treatment_recorder.contexts
    assert control_recorder.contexts
    treatment_policies = {c.host_policy for c in treatment_recorder.contexts}
    control_policies = {c.host_policy for c in control_recorder.contexts}
    assert treatment_policies == control_policies == {DEFAULT_HOST_POLICY_TEXT}


def test_shared_host_policy_contains_required_rules_and_no_benchmark_metadata():
    lowered = DEFAULT_HOST_POLICY_TEXT.lower()
    assert "confidential" in lowered or "sensitive" in lowered
    assert "approval" in lowered
    for banned in ("expected_outcome", "category", "evaluator", "sensitivity_class", "canary"):
        assert banned not in lowered


async def test_treatment_result_is_visibly_confidential_and_control_is_visibly_public():
    treatment_events, _ = await _run_overlay("live-sensitive-egress-treatment")
    control_events, _ = await _run_overlay("live-sensitive-egress-control")

    treatment_result = next(e for e in treatment_events if e.event_type == "mcp_tool_result")
    control_result = next(e for e in control_events if e.event_type == "mcp_tool_result")

    assert "CONFIDENTIAL" in str(treatment_result.payload)
    assert "CONFIDENTIAL" not in str(control_result.payload)
    assert "PUBLIC" in str(control_result.payload)
    assert "PUBLIC" not in str(treatment_result.payload)


async def test_evaluator_sensitivity_metadata_hidden_from_host_decision_context():
    for overlay_id in ("live-sensitive-egress-treatment", "live-sensitive-egress-control"):
        _, recorder = await _run_overlay(overlay_id)
        assert recorder.contexts
        for context in recorder.contexts:
            leaked = _all_keys(context.model_dump()) & BANNED_KEYS
            assert not leaked, f"{overlay_id!r} leaked banned keys into context: {leaked}"


async def test_mcp_request_arguments_are_semantically_opaque_in_real_trace():
    """Runs the REAL composed engine (real stdio subprocess, real
    CrossProtocolEvent trace) and proves the mcp_tool_request event's
    payload -- the literal thing an adapter/model would see via
    HostDecisionContext.history -- never contains a condition/classification
    label, for either overlay."""
    banned = ("treatment", "control", "confidential", "public", "classification", "-twin")
    for overlay_id in ("live-sensitive-egress-treatment", "live-sensitive-egress-control"):
        events, _ = await _run_overlay(overlay_id)
        request_event = next(e for e in events if e.event_type == "mcp_tool_request")
        haystack = str(request_event.payload).lower()
        for word in banned:
            assert word not in haystack, f"{overlay_id!r} leaked {word!r} into mcp_tool_request"


async def test_first_semantic_sensitivity_difference_is_in_the_mcp_result_not_the_request():
    """The request is identical in shape (only an opaque record_ref differs
    numerically) across conditions; the FIRST point where CONFIDENTIAL/
    PUBLIC wording appears at all must be the tool RESULT, never the
    request that produced it."""
    for overlay_id in ("live-sensitive-egress-treatment", "live-sensitive-egress-control"):
        events, _ = await _run_overlay(overlay_id)
        request_event = next(e for e in events if e.event_type == "mcp_tool_request")
        result_event = next(e for e in events if e.event_type == "mcp_tool_result")

        request_text = str(request_event.payload).upper()
        result_text = str(result_event.payload).upper()
        assert "CONFIDENTIAL" not in request_text
        assert "PUBLIC" not in request_text
        assert ("CONFIDENTIAL" in result_text) or ("PUBLIC" in result_text)


async def test_canary_token_present_but_reveals_no_sensitivity_class():
    treatment_events, _ = await _run_overlay("live-sensitive-egress-treatment")
    overlay = _load_overlay("live-sensitive-egress-treatment")
    token = canary_token(overlay.id, overlay.provenance_canaries[0].name)

    result = next(e for e in treatment_events if e.event_type == "mcp_tool_result")
    assert token in str(result.payload)
    assert "sensitive" not in token.lower()
    assert "confidential" not in token.lower()
