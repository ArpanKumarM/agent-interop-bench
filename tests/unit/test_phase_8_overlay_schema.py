"""Phase 8 additions to LiveExperimentOverlay (docs/phase_8_change_list.md
S2). The new fields are optional with pre-8 defaults, and left at their
defaults they must not perturb any already-frozen overlay bundle hash.
"""

from __future__ import annotations

from app.models.a2a import AgentCard
from app.models.live_overlay import LiveExperimentOverlay
from app.runner.execution_fingerprint import resolved_overlay_bundle_sha256

_CARD = AgentCard(
    name="x",
    description="y",
    supported_interfaces=[
        {"url": "http://x", "protocol_binding": "HTTP_JSON", "protocol_version": "1.0"}
    ],
    default_input_modes=["text/plain"],
    default_output_modes=["text/plain"],
)


def _mk(**kw) -> LiveExperimentOverlay:
    base = dict(
        id="o1",
        experiment="sensitive_egress",
        condition="neutral",
        user_prompt="do the task",
        target_agent_card=_CARD,
        remote_artifact_text="ok",
    )
    base.update(kw)
    return LiveExperimentOverlay(**base)


def test_new_fields_have_pre8_defaults():
    o = _mk()
    assert o.sink == "a2a_relay"
    assert o.arm is None
    assert o.task_framing_id is None
    assert o.prompt_suffix_kind == "none"


def test_defaults_do_not_change_bundle_hash():
    # An overlay that never mentions the Phase 8 fields hashes identically
    # to one that sets them explicitly to their defaults.
    implicit = _mk()
    explicit = _mk(sink="a2a_relay", arm=None, task_framing_id=None, prompt_suffix_kind="none")
    assert resolved_overlay_bundle_sha256([implicit]) == resolved_overlay_bundle_sha256([explicit])


def test_non_default_sink_changes_bundle_hash():
    a = _mk()
    b = _mk(sink="user_reply", arm="unlabeled", task_framing_id="F1")
    assert resolved_overlay_bundle_sha256([a]) != resolved_overlay_bundle_sha256([b])


def test_sink_literal_is_constrained():
    import pytest

    with pytest.raises(ValueError):
        _mk(sink="carrier-pigeon")
