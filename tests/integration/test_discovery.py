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
