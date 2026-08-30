"""A2A v1.0 (HTTP+JSON/REST binding) protocol and benchmark-case models.

Deliberately separate from ``app.models.benchmark``: MCP's ``BenchmarkCase``
is tool-call-shaped (``expected_tool``/``expected_arguments``/``is_mutating``)
and stays completely unchanged. A2A has almost no field-vocabulary overlap
with it (see the Phase 3A/3B.0 architecture audit), so bolting A2A fields
onto ``BenchmarkCase`` would force every MCP case to carry meaningless nulls
and vice versa.

Field names follow the official A2A v1.0 specification (a2a-protocol.org)
where a protocol object is being modeled (``AgentCard``, ``AgentInterface``,
``Message``, ``Part``, ``Task``, ``TaskStatus``, ``TaskState``, ``Artifact``).
Benchmark-authored fixture/case fields (``A2ARemoteStep``,
``A2ABenchmarkCase``, ...) are this project's own vocabulary, not the
protocol's.
"""

from __future__ import annotations

import uuid
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

# Fixed namespace so `deterministic_id` produces the exact same UUID string
# for the exact same (case_id, ...) input across every run -- the A2A
# analogue of MCP's "no randomness anywhere" determinism guarantee. Real
# A2A identifiers are opaque strings the protocol never requires to be
# random; deriving them from the case is a legitimate, deterministic choice
# a benchmark fixture is free to make.
_ID_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "a2avalidator.a2a")


def deterministic_id(*parts: str) -> str:
    """A stable UUID5 string derived from ``parts`` -- the same parts always
    produce the same ID, across processes and across runs."""
    return str(uuid.uuid5(_ID_NAMESPACE, ":".join(parts)))


class TaskState(StrEnum):
    """A2A v1.0 task lifecycle states (SCREAMING_SNAKE_CASE, TASK_STATE_ prefix)."""

    SUBMITTED = "TASK_STATE_SUBMITTED"
    WORKING = "TASK_STATE_WORKING"
    INPUT_REQUIRED = "TASK_STATE_INPUT_REQUIRED"
    AUTH_REQUIRED = "TASK_STATE_AUTH_REQUIRED"
    COMPLETED = "TASK_STATE_COMPLETED"
    FAILED = "TASK_STATE_FAILED"
    CANCELED = "TASK_STATE_CANCELED"
    REJECTED = "TASK_STATE_REJECTED"


TERMINAL_TASK_STATES = frozenset(
    {TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELED, TaskState.REJECTED}
)


class _WireModel(BaseModel):
    """Base for models that are literally exchanged as A2A v1.0 HTTP+JSON
    request/response bodies (``AgentCard``, ``Message``, ``Part``,
    ``Artifact``, ``Task``, ``TaskStatus``).

    The v1.0 specification's normative field tables (Section 5.5, "JSON
    Field Naming Convention") use camelCase on the wire (``messageId``,
    ``contextId``, ``defaultInputModes``, ``supportedInterfaces``,
    ``protocolBinding``, ...) — Phase 3B shipped these fields serialized
    under their raw Python (snake_case) names instead, a real spec
    non-conformance found and fixed in Phase 3C.1. ``alias_generator``
    derives the camelCase wire name from each snake_case Python attribute
    automatically; ``populate_by_name=True`` means construction and
    ``model_validate`` still accept the snake_case name too, so internal
    Python code is completely unaffected and stays snake_case throughout
    (see class docstrings below) — only code that explicitly serializes
    with ``by_alias=True`` (the mock agent and the A2A client engine) emits
    camelCase on the wire, and only external-JSON ingestion call sites that
    also call ``reject_snake_case_wire_keys`` first (see that function's
    docstring) actually *enforce* camelCase-only on the way in.

    Benchmark-authored fixture/config models below (``ArgumentMatchRule``,
    ``A2ARemoteStep``, ``A2AActionSpec``, ``A2ABenchmarkCase``,
    ``A2ABenchmarkSuite``) and the persisted-report model
    (``A2AInteractionRecord``) are deliberately **not** ``_WireModel``\\ s:
    they are this project's own YAML/report vocabulary, never literally
    transmitted as A2A protocol JSON, and keep the project's existing
    snake_case JSON convention (matching ``CaseReport``/``TurnResult``).
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class Part(_WireModel):
    """A v1.0 ``Part`` — text-only for Phase 3B (file/data parts are a real
    protocol concept but no initial case needs them). Wire: ``contentType``."""

    content_type: str = "text/plain"
    text: str


class Message(_WireModel):
    """A v1.0 ``Message``. ``extensions``/``referenceTaskIds`` omitted: unused
    by any Phase 3B case. Wire: ``messageId``, ``taskId``, ``contextId``."""

    message_id: str
    role: Literal["ROLE_USER", "ROLE_AGENT"]
    parts: list[Part]
    task_id: str | None = None
    context_id: str | None = None


class Artifact(_WireModel):
    """A v1.0 ``Artifact`` — a finalized deliverable, composed of ``Part``s."""

    parts: list[Part] = Field(default_factory=list)


class TaskStatus(_WireModel):
    """A v1.0 ``TaskStatus`` — ``Task.status``. ``message``/``timestamp``
    omitted: unused by any Phase 3B case."""

    state: TaskState


class Task(_WireModel):
    """A v1.0 ``Task``. Wire: ``contextId``; ``id``/``status``/``artifacts``/
    ``history`` are already single-word-or-already-camelCase and unaffected
    by the alias generator. ``metadata`` omitted: unused by any Phase 3B case."""

    id: str
    context_id: str | None = None
    status: TaskStatus
    artifacts: list[Artifact] = Field(default_factory=list)
    history: list[Message] = Field(default_factory=list)


class AgentInterface(_WireModel):
    """One entry of a v1.0 ``AgentCard.supportedInterfaces[]``. Wire:
    ``protocolBinding``, ``protocolVersion``."""

    url: str
    protocol_binding: Literal["HTTP_JSON", "JSON_RPC", "GRPC"]
    protocol_version: str


class AgentCard(_WireModel):
    """A v1.0 ``AgentCard`` fixture. Only the fields Phase 3B's cases actually
    need: identity, transport/version declaration, and input/output-mode
    capability declaration. ``skills``/``provider``/``securitySchemes``/
    ``security``/``extensions``/``signature`` are real v1.0 fields but unused
    by any Phase 3B case, so omitted rather than modeled speculatively.
    Wire: ``supportedInterfaces``, ``defaultInputModes``, ``defaultOutputModes``."""

    name: str
    description: str = ""
    supported_interfaces: list[AgentInterface]
    default_input_modes: list[str] = Field(default_factory=lambda: ["text/plain"])
    default_output_modes: list[str] = Field(default_factory=lambda: ["text/plain"])

    @model_validator(mode="after")
    def _at_least_one_interface(self) -> AgentCard:
        if not self.supported_interfaces:
            raise ValueError("AgentCard.supported_interfaces must declare at least one interface")
        return self


_PROTOCOL_SNAKE_CASE_FIELD_NAMES: frozenset[str] = frozenset(
    name
    for cls in (Part, Message, Artifact, TaskStatus, Task, AgentInterface, AgentCard)
    for name in cls.model_fields
    if "_" in name
)


def reject_snake_case_wire_keys(data: Any) -> None:
    """Raise ``ValueError`` if ``data`` (a JSON value already decoded into
    Python dict/list/scalar form) uses a known A2A protocol field's raw
    snake_case Python name as a dict key, anywhere, at any nesting depth.

    This is the strict half of the wire-casing contract: ``_WireModel``'s
    ``populate_by_name=True`` must stay on so *internal* Python code can keep
    constructing these models with readable snake_case keyword arguments
    (``Message(message_id=...)``) — but that same setting would otherwise
    also let a payload arriving over HTTP use snake_case keys
    (``{"message_id": ...}``), which the v1.0 spec's JSON Field Naming
    Convention (Section 5.5, camelCase-only) does not permit. Pydantic v2
    has no per-call-site way to make ``populate_by_name`` apply to
    construction but not to ``model_validate`` (both are governed by the
    same model-level setting) — so external-JSON ingestion call sites
    (currently: the mock agent's ``/message:send`` handler) call this
    *before* ``model_validate``, rejecting the payload outright if it uses
    any protocol field's raw Python name instead of its camelCase alias.

    Deliberately narrower than "any key containing an underscore": this only
    flags names in ``_PROTOCOL_SNAKE_CASE_FIELD_NAMES``, the actual snake_case
    attribute names declared on ``_WireModel`` subclasses (``message_id``,
    ``task_id``, ``context_id``, ``content_type``, ``protocol_binding``,
    ``protocol_version``, ``supported_interfaces``, ``default_input_modes``,
    ``default_output_modes``). A caller's own nested payload/data content
    (e.g. ``{"customer_id": "123"}`` inside message text or future
    unstructured fields) is not A2A protocol vocabulary and must not be
    rejected just because it happens to contain an underscore. The set is
    derived from the model classes themselves (not hand-enumerated) so it
    stays correct as protocol fields are added or removed.
    """
    if isinstance(data, dict):
        for key, value in data.items():
            if key in _PROTOCOL_SNAKE_CASE_FIELD_NAMES:
                raise ValueError(
                    f"Field '{key}' is not valid A2A v1.0 wire JSON: the spec's JSON Field "
                    "Naming Convention (Section 5.5) requires camelCase (e.g. 'messageId', "
                    "not 'message_id')."
                )
            reject_snake_case_wire_keys(value)
    elif isinstance(data, list):
        for item in data:
            reject_snake_case_wire_keys(item)


class ArtifactMatchRule(BaseModel):
    """Opt-in, benchmark-authored artifact matcher. Mirrors
    ``app.models.benchmark.ArgumentMatchRule``'s discipline exactly: ``exact``
    is the only default, no semantic/fuzzy comparison exists."""

    matcher: Literal["exact"] = "exact"
    expected_text: str


# --- Benchmark-authored fixture scripts (not protocol objects) ---


class A2ARemoteStep(BaseModel):
    """One scripted response from the remote fixture agent, consumed in order
    by successive client actions (mirrors ``DeterministicFakeAdapter``'s
    script-per-step model). Index N of ``simulated_remote_behavior`` answers
    client action N, regardless of which action type it is."""

    task_state: TaskState
    remote_message_text: str | None = None
    artifact_text: str | None = None
    protocol_error_reason: str | None = None
    http_status: int | None = None


class A2AActionSpec(BaseModel):
    """One client action, either scripted (what the fixture client actually
    does) or declared as ground truth (what a safe client should do). The
    same shape serves both roles; which role a given instance plays is
    determined by which field of ``A2ABenchmarkCase`` it appears in — never
    both at once for the same case field (see module docstring on
    ``A2ABenchmarkCase.expected_client_action``)."""

    action: Literal["send_message", "get_task", "cancel_task", "stop"]
    content: str | None = None
    content_type: str = "text/plain"


class A2ABenchmarkCase(BaseModel):
    """A single deterministic A2A interoperability benchmark case.

    ``simulated_client_actions`` is the *scripted* (possibly deliberately
    flawed) behavior under test — the A2A analogue of MCP's
    ``simulated_agent_response``/``simulated_reactions``. It is never read as
    ground truth.

    ``expected_client_action`` is the explicit, benchmark-authored *safe*
    action a correctly-behaving client should take at the case's decision
    point (e.g. after observing a malicious remote message) — the A2A
    analogue of MCP's ``expected_tool``/``expected_arguments``. It is
    ``None`` for cases with no such decision point to score (e.g. a
    single-path happy case has nothing to compare against).
    """

    id: str
    category: Literal[
        "a2a_correct_interaction",
        "a2a_capability_negotiation",
        "a2a_task_lifecycle",
        "a2a_remote_failure",
        "a2a_cross_agent_injection",
        "a2a_false_success",
        "a2a_cancellation",
    ]
    user_prompt: str
    expected_outcome: Literal[
        "success", "graceful_failure", "blocked_unsafe", "refusal", "recovered"
    ]
    max_interaction_steps: int = Field(default=1, ge=1, le=10)
    target_agent_card: AgentCard
    expected_task_state: TaskState | None = None
    expected_artifact: ArtifactMatchRule | None = None
    simulated_remote_behavior: list[A2ARemoteStep]
    simulated_client_actions: list[A2AActionSpec]
    expected_client_action: A2AActionSpec | None = None
    failure_mode: Literal[
        "normal",
        "unavailable",
        "malformed",
        "unsupported_content_type",
        "remote_task_failure",
        "cross_agent_injection",
    ] = "normal"
    notes: str | None = None

    @model_validator(mode="after")
    def _scripts_fit_turn_budget(self) -> A2ABenchmarkCase:
        if len(self.simulated_client_actions) > self.max_interaction_steps:
            raise ValueError(
                f"Case '{self.id}' has {len(self.simulated_client_actions)} scripted client "
                f"actions but max_interaction_steps={self.max_interaction_steps}."
            )
        return self


class A2ABenchmarkSuite(BaseModel):
    """A named collection of A2A benchmark cases. Structurally parallel to
    ``BenchmarkSuite`` but never unified with it (see module docstring)."""

    name: str
    version: str
    cases: list[A2ABenchmarkCase]

    @model_validator(mode="after")
    def _unique_ids(self) -> A2ABenchmarkSuite:
        seen: set[str] = set()
        for case in self.cases:
            if case.id in seen:
                raise ValueError(f"Duplicate A2A benchmark case id: {case.id}")
            seen.add(case.id)
        return self


# --- Persisted interaction trace (not a protocol object; report-shaped) ---


class A2AInteractionRecord(BaseModel):
    """One step of a persisted A2A interaction trace. Deliberately does not
    inherit from ``TurnResult`` and carries no MCP vocabulary (no
    ``requested_tool``/``tool_known``/``is_mutating``/``blocked_unsafe``/
    ``tool_output``) — see the Phase 3A/3B.0 architecture audit."""

    step_index: int
    client_action: Literal["send_message", "get_task", "cancel_task", "stop"]
    protocol_operation: str | None = None
    request_message_id: str | None = None
    request_content: str | None = None
    task_id: str | None = None
    context_id: str | None = None
    observed_task_state: TaskState | None = None
    remote_message: Message | None = None
    artifacts: list[Artifact] = Field(default_factory=list)
    protocol_error: dict[str, Any] | None = None
    termination_classification: (
        Literal[
            "completed",
            "failed",
            "canceled",
            "rejected",
            "stopped",
            "step_limit_reached",
            "in_progress",
        ]
        | None
    ) = None
