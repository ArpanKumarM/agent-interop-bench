"""The sanitized model boundary between ``ComposedBenchmarkRunner`` and any
``HostAgentAdapter`` (Phase 4A.1).

``HostDecisionContext`` is the ONLY thing an adapter's ``decide()`` ever
receives -- never a ``ComposedBenchmarkCase`` and never a raw
``CrossProtocolEvent``. It carries only what a real host agent embedded in
a real system could plausibly observe: the task prompt, the policy it must
follow, the protocol interaction so far, the tools/capabilities available
to it, and which decision step it's on.

Deliberately excluded, because these are benchmark ground truth or
fixture-authored research labels a real host agent would never have access
to: ``expected_outcome``/``category`` (what SHOULD happen), ``content_class``/
``origin_trust``/``sensitivity`` (fixture-declared provenance labels),
``canary_ids``/``propagated_canary_ids``/``adversarial_ancestor_ids``/
``sensitive_ancestor_ids`` (provenance bookkeeping), ``allowed_sensitive_edges``
(the policy an evaluator checks against, not a fact the host is told),
evaluator results, and any future/remaining scripted behavior. Literal
canary or trigger text already present inside an observed payload is not
excluded -- it is real content the host actually saw, exactly like a
prompt-injection payload already visible in a real tool's output.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.models.a2a import AgentCard
from app.models.composed import Actor
from app.models.tools import ToolDefinition


class ObservableEvent(BaseModel):
    """A model-visible view of one already-occurred protocol step.

    Carries the same protocol-observable facts an ``AgentAdapter`` already
    receives via ``TurnResult`` today (was this mutating, was it approved,
    did it execute) -- these are procedural outcomes, not fixture-authored
    provenance labels. ``seq`` is the event's position in the trace, for
    ordering only.
    """

    seq: int
    event_type: str
    source: Actor
    dest: Actor
    protocol: str
    payload: dict[str, Any] = Field(default_factory=dict)
    is_mutating: bool = False
    approved: bool | None = None
    executed: bool | None = None


class HostDecisionContext(BaseModel):
    """Everything -- and only what -- a host agent (scripted or real) may
    use to decide its next action."""

    user_prompt: str
    host_policy: str
    history: list[ObservableEvent] = Field(default_factory=list)
    available_tools: list[ToolDefinition] = Field(default_factory=list)
    target_agent_card: AgentCard
    current_step: int
