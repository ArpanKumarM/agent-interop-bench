from app.runner.tool_schema_openai import translate_tools_for_openai
from tests.integration.conftest import make_mock_transport

EXPECTED_TOOLS = {"search_issues", "get_repository", "create_comment", "calculate_sum"}


async def test_discovers_all_mock_tools():
    async with make_mock_transport() as transport:
        tools = await transport.list_tools()
    assert {t.name for t in tools} == EXPECTED_TOOLS


async def test_discovered_tools_have_schema_and_required_args():
    async with make_mock_transport() as transport:
        tools = {t.name: t for t in await transport.list_tools()}
    calc = tools["calculate_sum"]
    assert set(calc.required_arguments) == {"a", "b"}
    assert calc.input_schema["type"] == "object"


async def test_create_comment_is_flagged_mutating():
    async with make_mock_transport() as transport:
        tools = {t.name: t for t in await transport.list_tools()}
    assert tools["create_comment"].is_mutating is True
    assert tools["calculate_sum"].is_mutating is False


async def test_openai_tool_translation_matches_the_real_discovered_schemas():
    """End-to-end sanity for Phase 2C's schema translation: translate the
    ACTUAL schemas discovered from the real (local, no-network) mock MCP
    server right now, not just hand-written stand-ins, and confirm the
    documented invariants hold (see tests/unit/test_tool_schema_openai.py
    for the detailed per-invariant unit tests)."""
    async with make_mock_transport() as transport:
        tools = await transport.list_tools()

    translated = translate_tools_for_openai(tools)
    assert {t["name"] for t in translated} == EXPECTED_TOOLS
    for translated_tool in translated:
        params = translated_tool["parameters"]
        assert "failure_mode" not in params["properties"]
        assert set(params["properties"]) == set(params["required"])
        assert params["additionalProperties"] is False
