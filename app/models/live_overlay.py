"""Live-experiment overlay schema (Phase 4A.2).

A NEW, separate schema from ``ComposedBenchmarkCase`` — deterministic
``benchmarks/composed/composed_suite.yaml`` is never modified or read by
this module. An overlay declares the treatment/control stimuli for one
real-model trial template; ``overlay_to_composed_case`` converts it into a
``ComposedBenchmarkCase`` purely so the existing, unmodified
``ComposedBenchmarkRunner``/mock MCP+A2A machinery can execute it — a real
adapter is always passed explicitly for an overlay-derived case, so its
(unused, empty) ``simulated_host_actions`` never matters.

Two independent safety points, both structural, not just conventions:

1. The influence-experiment treatment's ``remote_artifact_text`` is
   realistic natural-language content, never an
   ``⟦ACTION_TRIGGER:...⟧`` marker — that marker only exists to drive
   ``ScriptedHostAdapter``'s own mechanical check; a real model reasons
   about real content, not a fixture-only string. ``LiveExperimentOverlay``
   has no ``action_triggers``/trigger field at all, so there is no field to
   accidentally populate with one.
2. ``researcher_notes`` (condition labels, hypotheses, etc.) exists only as
   overlay/report metadata. ``overlay_to_composed_case`` never reads it when
   building the ``ComposedBenchmarkCase``, and nothing in
   ``ComposedBenchmarkRunner`` ever includes case-level fields like
   ``category``/``expected_outcome`` in a ``HostDecisionContext`` (Phase
   4A.1's boundary) — so even the placeholder ``expected_outcome`` this
   conversion sets is structurally unreachable from any adapter.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from app.models.a2a import A2ARemoteStep, AgentCard, TaskState
from app.models.composed import ComposedBenchmarkCase, ProvenanceCanary, SensitiveEdge


class LiveExperimentOverlay(BaseModel):
    id: str
    experiment: Literal["sensitive_egress", "adversarial_influence"]
    condition: Literal["treatment", "control"]
    user_prompt: str
    target_agent_card: AgentCard
    local_tool_name: str | None = None
    local_tool_arguments: dict[str, Any] = Field(default_factory=dict)
    provenance_canaries: list[ProvenanceCanary] = Field(default_factory=list)
    allowed_sensitive_edges: list[SensitiveEdge] = Field(default_factory=list)
    # Realistic, natural-language remote-agent artifact content. For
    # experiment="adversarial_influence", this is the manipulated variable
    # (treatment: realistic adversarial phrasing; control: ordinary benign
    # phrasing) -- NEVER an ACTION_TRIGGER marker.
    remote_artifact_text: str
    max_interaction_steps: int = Field(default=6, ge=1, le=20)

    # --- Phase 6B (v4) additions. All optional; a v1/v2/v3 overlay omits
    #     them entirely and behaves exactly as before. ---
    # Which decision-point action surface the influence experiment offers.
    # "legacy_wrapper" (default) -> {attempt_mutating_tool, stop} (Phase 4B).
    # "call_tool"                -> {call_tool, stop} (Phase 6B; no wrapper).
    action_surface: Literal["legacy_wrapper", "call_tool"] = "legacy_wrapper"
    # RQ1 v4: the synthetic record's exact field values for this arm (both
    # arms of a pair carry identical values). Used by the offline field-
    # egress detector; never model-visible.
    record_field_values: dict[str, str] | None = None
    # RQ2 v4: mark the treatment artifact adversarial so DAG-computed
    # adversarial ancestry is populated and can be cross-checked against the
    # assigned condition (a consistency check, not a second metric).
    content_class_override: Literal["adversarial"] | None = None
    # RQ1+RQ2 v4: the exact host-policy text for this trial (the Phase 6B
    # policy). None -> DEFAULT_HOST_POLICY_TEXT (Phase 4A/4B).
    host_policy_text: str | None = None
    # RQ1+RQ2 v4: the exact model-visible tool allowlist (the 12-tool Phase
    # 6B surface). None -> the model sees every discovered tool.
    visible_tool_names: list[str] | None = None
    # Metadata only -- never read when building a ComposedBenchmarkCase,
    # never model-visible.
    researcher_notes: str | None = None


class LiveOverlaySuite(BaseModel):
    name: str
    version: str
    overlays: list[LiveExperimentOverlay]


def overlay_to_composed_case(overlay: LiveExperimentOverlay) -> ComposedBenchmarkCase:
    """Builds a ``ComposedBenchmarkCase`` purely to drive the existing MCP+A2A
    mock machinery -- ``simulated_host_actions`` is intentionally empty
    because a live-overlay run always supplies an explicit adapter (real or
    a test double) to ``ComposedBenchmarkRunner.run_case``, never relies on
    the default ``ScriptedHostAdapter``.
    """
    category = (
        "composed_mutation"
        if overlay.experiment == "adversarial_influence"
        else "composed_propagation"
    )
    content_class_overrides: dict[str, str] = {}
    if overlay.content_class_override == "adversarial":
        # The artifact the remote fixture returns is adversarial; the engine
        # folds this into per-event adversarial ancestry.
        content_class_overrides["a2a_artifact"] = "adversarial"
    return ComposedBenchmarkCase(
        id=overlay.id,
        category=category,
        user_prompt=overlay.user_prompt,
        expected_outcome="success",
        target_agent_card=overlay.target_agent_card,
        provenance_canaries=overlay.provenance_canaries,
        allowed_sensitive_edges=overlay.allowed_sensitive_edges,
        content_class_overrides=content_class_overrides,
        simulated_remote_behavior=[
            A2ARemoteStep(
                task_state=TaskState.COMPLETED, artifact_text=overlay.remote_artifact_text
            )
        ],
        simulated_host_actions=[],
        max_interaction_steps=overlay.max_interaction_steps,
        host_policy=overlay.host_policy_text,
        visible_tool_names=overlay.visible_tool_names,
    )
