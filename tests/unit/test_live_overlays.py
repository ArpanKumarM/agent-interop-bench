"""Phase 4A.2 (corrected): live-experiment overlay schema/loader tests.

Proves the file loads with exactly the four initial overlays; that both
experiments' treatment/control conditions are MODEL-OBSERVABLY different
(not just benchmark-ground-truth different) via real, visible content; that
the influence experiment never uses an ACTION_TRIGGER marker; that the
canary tokens themselves never reveal their sensitivity class; and that
converting an overlay to a ComposedBenchmarkCase never leaks
researcher-only or evaluator-only metadata into anything model-visible.
"""

from __future__ import annotations

from app.core.live_overlays import load_live_overlays
from app.models.composed import canary_token
from app.models.live_overlay import overlay_to_composed_case

OVERLAYS_PATH = "benchmarks/composed/live_overlays.yaml"


def test_loads_exactly_four_overlays():
    suite = load_live_overlays(OVERLAYS_PATH)
    assert {o.id for o in suite.overlays} == {
        "live-sensitive-egress-treatment",
        "live-sensitive-egress-control",
        "live-influence-treatment",
        "live-influence-control",
    }


def test_no_overlay_ever_contains_action_trigger_marker():
    """Broader than just the influence experiment: no field of any overlay,
    of either experiment, may ever contain the deterministic-fixture-only
    ACTION_TRIGGER marker."""
    suite = load_live_overlays(OVERLAYS_PATH)
    for overlay in suite.overlays:
        haystack = " ".join(
            [
                overlay.user_prompt,
                overlay.remote_artifact_text,
                str(overlay.local_tool_arguments),
            ]
        )
        assert "ACTION_TRIGGER" not in haystack
        assert "⟦" not in haystack


def test_influence_treatment_is_realistic_natural_language_not_a_marker():
    suite = load_live_overlays(OVERLAYS_PATH)
    treatment = next(o for o in suite.overlays if o.id == "live-influence-treatment")
    control = next(o for o in suite.overlays if o.id == "live-influence-control")
    assert len(treatment.remote_artifact_text.split()) > 10
    assert len(control.remote_artifact_text.split()) > 5
    assert treatment.remote_artifact_text != control.remote_artifact_text


def test_sensitive_egress_conditions_are_matched_but_model_observably_different():
    suite = load_live_overlays(OVERLAYS_PATH)
    treatment = next(o for o in suite.overlays if o.id == "live-sensitive-egress-treatment")
    control = next(o for o in suite.overlays if o.id == "live-sensitive-egress-control")

    # Matched: same task/tool/topology structure.
    assert treatment.user_prompt == control.user_prompt
    assert treatment.local_tool_name == control.local_tool_name == "get_customer_record"
    assert treatment.target_agent_card == control.target_agent_card
    assert (
        set(treatment.local_tool_arguments) == set(control.local_tool_arguments) == {"record_ref"}
    )

    # The model-visible REQUEST is semantically opaque and differs only in
    # an opaque reference, never a benchmark/condition parameter.
    assert (
        treatment.local_tool_arguments["record_ref"] != control.local_tool_arguments["record_ref"]
    )

    # Evaluator ground truth differs, but that's benchmark-side only, never
    # part of the request the model sends.
    assert treatment.provenance_canaries[0].sensitivity == "sensitive"
    assert control.provenance_canaries[0].sensitivity == "public"


def test_sensitive_egress_mcp_request_arguments_are_semantically_opaque():
    """The model-visible MCP request must never contain a condition label,
    classification, or experiment-identifying string -- only a neutral
    reference. See mock_servers/composed_tool_mock.py's
    _LIVE_RECORD_FIXTURES for where the actual mapping lives (server-side,
    never in the request)."""
    suite = load_live_overlays(OVERLAYS_PATH)
    treatment = next(o for o in suite.overlays if o.id == "live-sensitive-egress-treatment")
    control = next(o for o in suite.overlays if o.id == "live-sensitive-egress-control")

    banned = (
        "treatment",
        "control",
        "public-twin",
        "public_twin",
        "sensitive-twin",
        "sensitive_twin",
        "confidential",
        "sensitive",
        "public",
        "classification",
    )
    for overlay in (treatment, control):
        haystack = str(overlay.local_tool_arguments).lower()
        for word in banned:
            assert word not in haystack, (
                f"{overlay.id!r} leaked {word!r} into MCP request arguments"
            )

    # The only argument at all is the opaque reference.
    assert list(treatment.local_tool_arguments) == ["record_ref"]
    assert list(control.local_tool_arguments) == ["record_ref"]


def test_sensitive_egress_prompt_does_not_authorize_or_instruct_relay():
    """The experimental conflict must come from the model-visible TOOL
    RESULT (CONFIDENTIAL vs PUBLIC), never from the prompt itself: the
    prompt must not explicitly authorize sending confidential/sensitive
    data to the remote agent, and must not instruct copying/relaying the
    retrieved record verbatim -- while still giving the host a legitimate
    reason to consider contacting the remote agent."""
    suite = load_live_overlays(OVERLAYS_PATH)
    treatment = next(o for o in suite.overlays if o.id == "live-sensitive-egress-treatment")
    control = next(o for o in suite.overlays if o.id == "live-sensitive-egress-control")

    assert treatment.user_prompt == control.user_prompt

    lowered = treatment.user_prompt.lower()
    for banned in (
        "confidential",
        "sensitive",
        "internal",
        "relay the finding",
        "relay the record",
        "send the record",
        "copy the record",
        "verbatim",
    ):
        assert banned not in lowered

    # Still gives a legitimate reason to consider using the remote agent.
    assert "remote agent" in lowered


def test_canary_tokens_do_not_reveal_their_sensitivity_class():
    suite = load_live_overlays(OVERLAYS_PATH)
    treatment = next(o for o in suite.overlays if o.id == "live-sensitive-egress-treatment")
    control = next(o for o in suite.overlays if o.id == "live-sensitive-egress-control")

    treatment_token = canary_token(treatment.id, treatment.provenance_canaries[0].name)
    control_token = canary_token(control.id, control.provenance_canaries[0].name)

    for token in (treatment_token, control_token):
        lowered = token.lower()
        for banned_word in ("sensitive", "confidential", "public", "secret", "private"):
            assert banned_word not in lowered


def test_overlay_to_composed_case_never_reads_researcher_notes():
    suite = load_live_overlays(OVERLAYS_PATH)
    for overlay in suite.overlays:
        assert overlay.researcher_notes is not None  # every overlay documents its condition
        case = overlay_to_composed_case(overlay)
        dumped = case.model_dump_json()
        assert overlay.researcher_notes not in dumped


def test_overlay_derived_case_has_empty_scripted_actions():
    """A live-overlay-derived case never relies on ScriptedHostAdapter's
    default -- an explicit adapter must always be supplied to run_case."""
    suite = load_live_overlays(OVERLAYS_PATH)
    for overlay in suite.overlays:
        case = overlay_to_composed_case(overlay)
        assert case.simulated_host_actions == []
