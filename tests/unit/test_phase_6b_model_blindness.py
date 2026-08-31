"""Phase 6B model-blindness: the model never sees is_mutating / gate /
taxonomy labels, and the influence action schema is exactly call_tool +
stop."""

from __future__ import annotations

import json

from app.models.tools import ToolDefinition
from app.runner.host_action_schema_openai import (
    PHASE_6B_INFLUENCE_ACTIONS,
    canonical_action_schema,
)


def test_tool_definition_model_visible_dump_omits_is_mutating():
    td = ToolDefinition(
        name="rollback_config",
        description="Set a service's configuration to a named prior revision.",
        input_schema={"type": "object", "properties": {"target": {"type": "string"}}},
        is_mutating=True,
    )
    visible = td.model_visible_dump()
    assert "is_mutating" not in visible
    assert set(visible) == {"name", "description", "input_schema", "required_arguments"}
    assert "mutat" not in json.dumps(visible).lower()
    assert "destructive" not in json.dumps(visible).lower()


def test_canonical_influence_schema_is_exactly_call_tool_and_stop():
    assert PHASE_6B_INFLUENCE_ACTIONS == ("call_tool", "stop")
    schema = canonical_action_schema()
    names = sorted(t["name"] for t in schema)
    assert names == ["call_tool", "stop"]
    blob = json.dumps(schema).lower()
    for forbidden in ("is_mutating", "mutating", "destructive", "gate", "blocked", "approved"):
        assert forbidden not in blob, f"leaky token {forbidden!r} in the model-visible schema"


def test_call_tool_description_is_neutral():
    (call_tool,) = [t for t in canonical_action_schema() if t["name"] == "call_tool"]
    desc = call_tool["description"].lower()
    assert "mutat" not in desc
    assert "wrapper" not in desc
    assert "danger" not in desc


def test_discovered_tool_surface_has_no_mutating_signal_in_model_visible_fields():
    """Every tool the Phase 6B mock server exposes -- as the MODEL would see
    it (model_visible_dump) -- must carry no is_mutating flag and no
    mutating/destructive/dangerous wording in its neutral description."""
    import asyncio

    from tests.integration.test_composed_engine import make_composed_tool_transport

    async def _tools():
        async with make_composed_tool_transport() as t:
            return list(await t.list_tools())

    banned = ("is_mutating", "mutating", "mutation", "destructive", "dangerous", "irreversible")
    for td in asyncio.run(_tools()):
        visible = json.dumps(td.model_visible_dump()).lower()
        assert "is_mutating" not in visible
        for word in banned:
            assert word not in visible, f"{td.name}: model-visible field contains {word!r}"


def test_real_adapter_input_strips_is_mutating_from_tools_and_history():
    from app.models.a2a import AgentCard
    from app.models.host_context import HostDecisionContext, ObservableEvent
    from app.runner.real_host_adapter import _build_input

    card = AgentCard(
        name="mock-composed-agent",
        description="Mock remote agent.",
        supported_interfaces=[
            {"url": "http://mock", "protocol_binding": "HTTP_JSON", "protocol_version": "1.0"}
        ],
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
    )
    ctx = HostDecisionContext(
        user_prompt="do the thing",
        host_policy="policy text",
        history=[
            ObservableEvent(
                seq=0,
                event_type="a2a_artifact",
                source="remote",
                dest="host",
                protocol="a2a",
                payload={"text": "hello"},
                is_mutating=True,
                approved=True,
                executed=True,
            )
        ],
        available_tools=[
            ToolDefinition(name="rollback_config", description="Set config.", is_mutating=True)
        ],
        target_agent_card=card,
        current_step=1,
    )
    payload = _build_input(ctx)
    blob = json.dumps(payload)
    assert '"is_mutating"' not in blob
    assert '"approved"' not in blob
    assert '"executed"' not in blob
