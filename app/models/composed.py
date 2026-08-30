"""Cross-protocol composed benchmark models (Phase 3D.1).

Deliberately separate from ``app.models.benchmark`` (MCP) and
``app.models.a2a`` (A2A): neither existing case model is modified or
extended here, per the Phase 3D design lock. A composed case references
those two protocols' own types (``AgentCard``, ``A2ARemoteStep``) but adds
no fields to them.

``CrossProtocolEvent`` is the single normalized record for every observable
step of a composed interaction (an MCP tool request/result, an A2A message,
task-state transition, or artifact, an approval event, or a mutation
action). Provenance is tracked via independent, fixture-declared axes
(``origin_trust``, ``content_class``, ``sensitivity``) plus deterministic
provenance canaries — never a single "tainted" boolean, and never inferred
from any adapter's rationale text (no chain-of-thought is read or stored).

Only the two cases Phase 3D.1 implements
(``composed-benign-001-happy-path``,
``composed-propagation-001-canary-crosses-mcp-to-a2a``) are exercised by any
runner today; the six-category ``Literal`` below reflects the full Phase 3D
design lock so later phases (mutation/approval/remote-failure/isolated-pass)
don't require a schema migration, but only the first two categories are
reachable in this phase.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.models.a2a import A2ARemoteStep, AgentCard

# Same fixed-namespace discipline as app.models.a2a.deterministic_id: the
# same (case_id, ...) input always produces the same ID, across processes
# and runs -- required for the two-run byte-identical equality proof.
_ID_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "a2avalidator.composed")


def composed_deterministic_id(*parts: str) -> str:
    return str(uuid.uuid5(_ID_NAMESPACE, ":".join(parts)))


def canary_token(case_id: str, canary_name: str) -> str:
    """The literal, syntactically-inert substring embedded in fixture
    content to prove propagation by exact string identity -- never by
    semantic guessing. See ``ProvenanceCanary``."""
    return f"⟦CANARY:{composed_deterministic_id(case_id, 'canary', canary_name)}⟧"


Actor = Literal["user", "host", "remote", "local_tool", "remote_tool"]

_DEFAULT_ORIGIN_TRUST: dict[Actor, Literal["trusted", "untrusted"]] = {
    "user": "trusted",
    "host": "trusted",
    "remote": "untrusted",
    "local_tool": "untrusted",
    "remote_tool": "untrusted",
}


class ProvenanceCanary(BaseModel):
    """A fixture-authored, deterministic marker embedded in specific
    content so propagation across a protocol boundary is provable by exact
    substring identity, never by semantic interpretation of the content."""

    name: str
    sensitivity: Literal["public", "sensitive"] = "public"


class SensitiveEdge(BaseModel):
    """One explicitly authorized observable communication edge for
    sensitive content. Describes the edge itself (who talked to whom, over
    which protocol) -- independent of any event's ``origin_trust``."""

    source: Actor
    dest: Actor
    protocol: Literal["mcp", "a2a", "internal"]


class HostActionSpec(BaseModel):
    """One scripted host decision. ``{canary:NAME}`` in ``tool_arguments``
    values or in ``relay_template`` is substituted with that named canary's
    literal token (see ``canary_token``) before use; ``{tool_result_text}``
    in ``relay_template`` is substituted with the most recent
    ``mcp_tool_result`` event's text payload -- both are plain string
    substitution, not templating with any conditional/semantic logic."""

    action: Literal["call_local_tool", "relay_to_remote", "stop"]
    tool_name: str | None = None
    tool_arguments: dict[str, Any] = Field(default_factory=dict)
    relay_template: str | None = None
    content_type: str = "text/plain"


class ComposedBenchmarkCase(BaseModel):
    """A single deterministic cross-protocol composed benchmark case."""

    id: str
    category: Literal[
        "composed_benign",
        "composed_propagation",
        "composed_mutation",
        "composed_approval_absent",
        "composed_remote_failure",
        "composed_isolated_pass_fails",
    ]
    user_prompt: str
    expected_outcome: Literal["success", "graceful_failure", "blocked_unsafe"]
    target_agent_card: AgentCard
    provenance_canaries: list[ProvenanceCanary] = Field(default_factory=list)
    allowed_sensitive_edges: list[SensitiveEdge] = Field(default_factory=list)
    origin_trust_overrides: dict[str, Literal["trusted", "untrusted"]] = Field(default_factory=dict)
    content_class_overrides: dict[str, Literal["adversarial", "non_adversarial"]] = Field(
        default_factory=dict
    )
    simulated_host_actions: list[HostActionSpec]
    simulated_remote_behavior: list[A2ARemoteStep]
    max_interaction_steps: int = Field(default=6, ge=1, le=20)


class ComposedBenchmarkSuite(BaseModel):
    name: str
    version: str
    cases: list[ComposedBenchmarkCase]

    @model_validator(mode="after")
    def _unique_ids(self) -> ComposedBenchmarkSuite:
        seen: set[str] = set()
        for case in self.cases:
            if case.id in seen:
                raise ValueError(f"Duplicate composed benchmark case id: {case.id}")
            seen.add(case.id)
        return self


class CrossProtocolEvent(BaseModel):
    """One normalized, observable step of a composed interaction.

    ``seq`` (a monotonic per-case integer assigned by
    ``ComposedBenchmarkRunner``) is the sole field used for ordering and
    deterministic equality/replay; ``recorded_at`` is optional wall-clock
    metadata, excluded from every such comparison -- the same treatment
    ``TurnResult.executed_at`` already receives in this project's existing
    scientific-equivalence proofs.
    """

    event_id: str
    parent_event_ids: list[str] = Field(default_factory=list)
    case_id: str
    seq: int

    event_type: Literal[
        "mcp_tool_request",
        "mcp_tool_result",
        "a2a_message",
        "a2a_task_state_transition",
        "a2a_artifact",
        "approval_event",
        "mutation_action",
    ]
    source: Actor
    dest: Actor
    protocol: Literal["mcp", "a2a", "internal"]
    payload: dict[str, Any] = Field(default_factory=dict)

    origin_trust: Literal["trusted", "untrusted"]
    content_class: Literal["adversarial", "non_adversarial"] = "non_adversarial"
    sensitivity: Literal["public", "sensitive"] = "public"
    canary_ids: list[str] = Field(default_factory=list)

    adversarial_ancestor_ids: list[str] = Field(default_factory=list)
    sensitive_ancestor_ids: list[str] = Field(default_factory=list)
    propagated_canary_ids: list[str] = Field(default_factory=list)

    is_mutating: bool = False
    approved: bool | None = None
    executed: bool | None = None
    recorded_at: str | None = None


def default_origin_trust(actor: Actor) -> Literal["trusted", "untrusted"]:
    """The fixture-overridable default for an event whose ``source`` is
    ``actor`` -- never treated as permanently derived from the actor alone;
    a case's ``origin_trust_overrides`` always wins when present."""
    return _DEFAULT_ORIGIN_TRUST[actor]
