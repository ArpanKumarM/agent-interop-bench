"""Phase 8 model-blindness: ``sink`` / ``arm`` / ``task_framing_id`` /
``prompt_suffix_kind`` must never reach the model. ``overlay_to_composed_case``
must not read any of them, so the two sinks differ ONLY in the offered
action set (docs/phase_8_change_list.md S3.3/S7).
"""

from __future__ import annotations

from app.models.a2a import AgentCard, AgentInterface
from app.models.live_overlay import LiveExperimentOverlay, overlay_to_composed_case
from mock_servers.phase_8_fixtures import (
    PHASE_8_ARMS,
    phase_8_canary_token,
    phase_8_fields,
    phase_8_record_body,
    phase_8_record_ref,
    phase_8_user_prompt,
)

_CARD = AgentCard(
    name="test-agent",
    supported_interfaces=[
        AgentInterface(url="http://test", protocol_binding="HTTP_JSON", protocol_version="1.0")
    ],
)


def _mk_overlay(scenario: str, arm: str, sink: str, framing: str = "F1") -> LiveExperimentOverlay:
    fields = phase_8_fields(scenario)
    canary = phase_8_canary_token(scenario)
    return LiveExperimentOverlay(
        id=f"p8-{scenario}-{arm}-{sink}",
        experiment="sensitive_egress",
        condition="neutral",
        user_prompt=phase_8_user_prompt(framing, sink, arm),
        target_agent_card=_CARD,
        local_tool_name="get_account_record",
        local_tool_arguments={"record_ref": phase_8_record_ref(scenario, arm)},
        remote_artifact_text="Understood, thank you.",
        host_policy_text="policy text",
        visible_tool_names=["get_account_record"],
        record_field_values={
            "full_name": fields.full_name,
            "email": fields.email,
            "phone": fields.phone,
            "account_id": fields.account_id,
            "internal_note": fields.internal_note,
            "credential_token": fields.credential_token,
            "canary_token": canary,
            "header_label": "",
            "full_record_text": phase_8_record_body(arm, fields, canary),
        },
        sink=sink,
        arm=arm,
        task_framing_id=framing,
    )


def test_overlay_to_composed_case_never_reads_sink_arm_or_framing():
    scenario, arm = "saas-support", "unlabeled"
    a2a = _mk_overlay(scenario, arm, "a2a_relay")
    reply = _mk_overlay(scenario, arm, "user_reply")

    case_a2a = overlay_to_composed_case(a2a)
    case_reply = overlay_to_composed_case(reply)

    # ComposedBenchmarkCase carries no sink/arm/framing field at all --
    # the model-visible surface differs only via the action set the caller
    # (bootstrap_plan_for) restricts the decision point to, never via the
    # case itself.
    dump_a2a = case_a2a.model_dump()
    dump_reply = case_reply.model_dump()
    assert "sink" not in dump_a2a and "sink" not in dump_reply
    # every field except user_prompt (sink-appropriate addressee wording,
    # by design -- see docs/phase_8_design.md S4) is byte-identical
    for key in dump_a2a:
        if key in {"user_prompt", "id"}:
            continue
        assert dump_a2a[key] == dump_reply[key], f"unexpected divergence in {key!r}"
    assert dump_a2a["user_prompt"] != dump_reply["user_prompt"]


def test_no_arm_or_sink_word_appears_in_the_composed_case_prompt():
    for arm in PHASE_8_ARMS:
        for sink in ("a2a_relay", "user_reply"):
            overlay = _mk_overlay("saas-support", arm, sink)
            case = overlay_to_composed_case(overlay)
            low = case.user_prompt.lower()
            for word in ("a2a_relay", "user_reply", "sink", "arm=", "condition="):
                assert word not in low


def test_agent_card_shown_identically_regardless_of_sink():
    scenario, arm = "saas-support", "public"
    a2a = _mk_overlay(scenario, arm, "a2a_relay")
    reply = _mk_overlay(scenario, arm, "user_reply")
    assert (
        overlay_to_composed_case(a2a).target_agent_card
        == overlay_to_composed_case(reply).target_agent_card
    )
