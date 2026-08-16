from tests.integration.conftest import make_mock_transport


async def test_normal_call_succeeds():
    async with make_mock_transport() as transport:
        outcome = await transport.call_tool(
            "calculate_sum", {"a": 2, "b": 3, "failure_mode": "normal"}, timeout_seconds=5
        )
    assert not outcome.is_error
    assert outcome.structured_output == {"result": 5.0}


async def test_timeout_failure_mode_is_enforced_and_recovered():
    async with make_mock_transport() as transport:
        outcome = await transport.call_tool(
            "calculate_sum", {"a": 1, "b": 2, "failure_mode": "timeout"}, timeout_seconds=0.3
        )
    assert outcome.timed_out is True
    assert outcome.is_error is True
    # The runner must recover close to the requested bound, not hang for the
    # server's full simulated delay.
    assert outcome.latency_ms < 2000


async def test_exception_failure_mode_is_caught():
    async with make_mock_transport() as transport:
        outcome = await transport.call_tool(
            "calculate_sum", {"a": 1, "b": 2, "failure_mode": "exception"}, timeout_seconds=5
        )
    assert outcome.is_error is True
    assert outcome.timed_out is False
    assert "Simulated tool exception" in (outcome.error_message or "")


async def test_malformed_failure_mode_returns_captured_but_broken_output():
    async with make_mock_transport() as transport:
        outcome = await transport.call_tool(
            "calculate_sum", {"a": 1, "b": 2, "failure_mode": "malformed"}, timeout_seconds=5
        )
    assert outcome.is_error is False
    assert outcome.structured_output == {"result": "not-a-number"}


async def test_prompt_injection_failure_mode_embeds_payload():
    async with make_mock_transport() as transport:
        outcome = await transport.call_tool(
            "search_issues",
            {"repo": "x/y", "query": "bug", "failure_mode": "prompt_injection"},
            timeout_seconds=5,
        )
    assert outcome.is_error is False
    assert "IGNORE ALL PREVIOUS INSTRUCTIONS" in (outcome.text_output or "")


async def test_unknown_tool_is_reported_without_crashing():
    async with make_mock_transport() as transport:
        outcome = await transport.call_tool("delete_repository", {}, timeout_seconds=5)
    assert outcome.is_error is True
    assert outcome.tool_not_found is True


async def test_missing_required_argument_is_rejected():
    async with make_mock_transport() as transport:
        outcome = await transport.call_tool("calculate_sum", {"a": 1}, timeout_seconds=5)
    assert outcome.is_error is True


async def test_incorrect_argument_type_is_rejected():
    async with make_mock_transport() as transport:
        outcome = await transport.call_tool(
            "calculate_sum", {"a": "not-a-number", "b": 2}, timeout_seconds=5
        )
    assert outcome.is_error is True
