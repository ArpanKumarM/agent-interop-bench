"""Unit tests for OpenAIResponsesAdapter.

Uses fake ResponsesClient implementations throughout — plain objects
satisfying the ResponsesClient Protocol — so these tests never import the
real `openai` package, make no network call, and never touch a live model,
even though they're testing the module that would.

`ProtocolValidatingFakeResponsesClient` is a stricter fake than a plain
stub: it actively rejects any `function_call_output` whose `call_id` wasn't
actually issued by this fake in a prior response, and rejects a replayed
`function_call` item whose `call_id` it didn't issue — simulating the real
API's referential-integrity requirement, so a regression back to inventing
synthetic call_ids would be caught by these tests, not just by inspection.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.models.execution import TurnResult
from app.models.tools import ToolDefinition
from app.runner.openai_adapter import (
    DEFAULT_MAX_RETRIES,
    OpenAIAdapterError,
    OpenAIResponsesAdapter,
    _sanitize_provider_error,
    openai_sdk_available,
)

CALC_TOOL = ToolDefinition(
    name="calculate_sum",
    description="Add two numbers together.",
    input_schema={
        "properties": {"a": {"type": "number"}, "b": {"type": "number"}},
        "required": ["a", "b"],
        "type": "object",
    },
    required_arguments=["a", "b"],
    is_mutating=False,
)


class FakeResponsesClient:
    """A minimal stand-in for ``openai.AsyncOpenAI().responses``: records
    calls and returns pre-scripted responses, with no protocol validation."""

    def __init__(self, responses=None, exception: Exception | None = None):
        self._responses = list(responses or [])
        self._exception = exception
        self.calls: list[dict] = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if self._exception is not None:
            raise self._exception
        return self._responses.pop(0)


class ProtocolValidatingFakeResponsesClient:
    """A stricter fake: validates that every function_call_output and every
    replayed function_call item in a request correlates to a call_id THIS
    FAKE actually issued in a prior response — simulating the real API's
    referential-integrity requirement rather than accepting arbitrary test
    dictionaries. See module docstring."""

    def __init__(self, turns: list[list]):
        self._turns = list(turns)
        self.calls: list[dict] = []
        self._issued_call_ids: set[str] = set()

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        input_list = kwargs["input"]

        for item in input_list:
            item_type = item.get("type") if isinstance(item, dict) else getattr(item, "type", None)
            call_id = (
                item.get("call_id") if isinstance(item, dict) else getattr(item, "call_id", None)
            )
            if item_type in ("function_call_output", "function_call") and call_id is not None:
                assert call_id in self._issued_call_ids, (
                    f"{item_type} references call_id={call_id!r} that this fake "
                    f"provider never issued (issued so far: {self._issued_call_ids}) "
                    "-- looks like a synthetic/invented call_id, not a replayed one"
                )

        output = self._turns.pop(0)
        for item in output:
            if getattr(item, "type", None) == "function_call":
                self._issued_call_ids.add(item.call_id)
        return SimpleNamespace(
            id=f"resp_{len(self.calls)}", model="gpt-test", output=output, usage=None
        )


def _function_call(name, arguments, call_id="call_1"):
    return SimpleNamespace(
        type="function_call", name=name, arguments=json.dumps(arguments), call_id=call_id
    )


def _reasoning_item(item_id="reasoning_1"):
    """An opaque reasoning item, as a reasoning-capable model might emit
    alongside a function call. Content is never inspected by the adapter —
    only replayed verbatim."""
    return SimpleNamespace(type="reasoning", id=item_id, summary=[])


def _response(
    output=None, usage=None, response_id="resp_1", model="gpt-test", incomplete_details=None
):
    return SimpleNamespace(
        id=response_id,
        model=model,
        output=output or [],
        usage=usage,
        incomplete_details=incomplete_details,
    )


def _usage(input_tokens=10, output_tokens=5, total_tokens=15):
    return SimpleNamespace(
        input_tokens=input_tokens, output_tokens=output_tokens, total_tokens=total_tokens
    )


def _executed_turn(turn_index, tool, arguments, raw_text_output=None, error=None):
    return TurnResult(
        turn_index=turn_index,
        requested_tool=tool,
        requested_arguments=arguments,
        executed=True,
        raw_text_output=raw_text_output,
        error=error,
    )


# ---- basic decision translation (Part K) ----


async def test_one_valid_function_call_becomes_a_decision():
    client = FakeResponsesClient(
        [_response(output=[_function_call("calculate_sum", {"a": 1, "b": 2})], usage=_usage())]
    )
    adapter = OpenAIResponsesAdapter(client, model="gpt-test")
    decision = await adapter.decide("add 1 and 2", [CALC_TOOL], [])
    assert decision.tool_name == "calculate_sum"
    assert decision.arguments == {"a": 1, "b": 2}


async def test_no_tool_call_becomes_voluntary_stop():
    client = FakeResponsesClient([_response(output=[], usage=_usage())])
    adapter = OpenAIResponsesAdapter(client, model="gpt-test")
    decision = await adapter.decide("say hello", [CALC_TOOL], [])
    assert decision.tool_name is None


async def test_unknown_tool_call_passes_through_unaltered():
    client = FakeResponsesClient(
        [_response(output=[_function_call("delete_repository", {"owner": "x"})])]
    )
    adapter = OpenAIResponsesAdapter(client, model="gpt-test")
    decision = await adapter.decide("delete the repo", [CALC_TOOL], [])
    assert decision.tool_name == "delete_repository"
    assert decision.arguments == {"owner": "x"}


async def test_malformed_arguments_are_not_silently_corrected():
    """The model's arguments (wrong type/missing key) pass through exactly
    as given — the runner's schema validator retains authority."""
    client = FakeResponsesClient(
        [_response(output=[_function_call("calculate_sum", {"a": "five"})])]
    )
    adapter = OpenAIResponsesAdapter(client, model="gpt-test")
    decision = await adapter.decide("add five and two", [CALC_TOOL], [])
    assert decision.tool_name == "calculate_sum"
    assert decision.arguments == {"a": "five"}  # missing "b", "a" wrong type — untouched


async def test_multiple_function_calls_raise_a_controlled_error():
    client = FakeResponsesClient(
        [
            _response(
                output=[
                    _function_call("calculate_sum", {"a": 1, "b": 2}, "c1"),
                    _function_call("calculate_sum", {"a": 3, "b": 4}, "c2"),
                ]
            )
        ]
    )
    adapter = OpenAIResponsesAdapter(client, model="gpt-test")
    with pytest.raises(OpenAIAdapterError, match="2 function calls"):
        await adapter.decide("add numbers", [CALC_TOOL], [])


async def test_unparseable_arguments_json_raises_a_controlled_error():
    bad_call = SimpleNamespace(
        type="function_call", name="calculate_sum", arguments="{not json", call_id="c1"
    )
    client = FakeResponsesClient([_response(output=[bad_call])])
    adapter = OpenAIResponsesAdapter(client, model="gpt-test")
    with pytest.raises(OpenAIAdapterError, match="unparseable"):
        await adapter.decide("add numbers", [CALC_TOOL], [])


# ---- request construction (Part D / H) ----


async def test_parallel_tool_calls_disabled_and_tool_choice_auto():
    client = FakeResponsesClient([_response(output=[])])
    adapter = OpenAIResponsesAdapter(client, model="gpt-test")
    await adapter.decide("say hello", [CALC_TOOL], [])
    call = client.calls[0]
    assert call["parallel_tool_calls"] is False
    assert call["tool_choice"] == "auto"


async def test_parallel_tool_calls_disabled_on_every_call_across_multiple_turns():
    """Request-shape assertion (not just detection after the fact): the
    one-tool-per-turn provider control must be present on EVERY request in
    a multi-turn sequence, not just the first."""
    client = ProtocolValidatingFakeResponsesClient(
        turns=[
            [_function_call("search_issues", {"repo": "x", "query": "y"}, "call_a")],
            [],  # turn 2: model stops
        ]
    )
    adapter = OpenAIResponsesAdapter(client, model="gpt-test")
    decision1 = await adapter.decide("search for bugs", [CALC_TOOL], [])
    assert decision1.tool_name == "search_issues"

    history = [
        _executed_turn(0, "search_issues", {"repo": "x", "query": "y"}, raw_text_output="ok")
    ]
    await adapter.decide("search for bugs", [CALC_TOOL], history)

    assert len(client.calls) == 2
    for call in client.calls:
        assert call["parallel_tool_calls"] is False


async def test_max_output_tokens_is_configured_and_bounded():
    client = FakeResponsesClient([_response(output=[])])
    adapter = OpenAIResponsesAdapter(client, model="gpt-test", max_output_tokens=64)
    await adapter.decide("say hello", [CALC_TOOL], [])
    assert client.calls[0]["max_output_tokens"] == 64


async def test_baseline_policy_is_sent_as_instructions():
    from app.core.baseline_policy import BASELINE_POLICY_TEXT

    client = FakeResponsesClient([_response(output=[])])
    adapter = OpenAIResponsesAdapter(client, model="gpt-test")
    await adapter.decide("say hello", [CALC_TOOL], [])
    assert client.calls[0]["instructions"] == BASELINE_POLICY_TEXT


async def test_tools_are_translated_for_the_provider():
    client = FakeResponsesClient([_response(output=[])])
    adapter = OpenAIResponsesAdapter(client, model="gpt-test")
    await adapter.decide("say hello", [CALC_TOOL], [])
    tools_sent = client.calls[0]["tools"]
    assert tools_sent[0]["type"] == "function"
    assert tools_sent[0]["name"] == "calculate_sum"
    assert "failure_mode" not in tools_sent[0]["parameters"]["properties"]


async def test_first_turn_input_is_the_benchmark_prompt_only():
    client = FakeResponsesClient([_response(output=[])])
    adapter = OpenAIResponsesAdapter(client, model="gpt-test")
    await adapter.decide("what is 1 + 2?", [CALC_TOOL], [])
    assert client.calls[0]["input"] == [{"role": "user", "content": "what is 1 + 2?"}]


# ---- multi-turn protocol fidelity: real call_id correlation (Part 1) ----


async def test_second_turn_replays_the_exact_provider_call_id_not_a_synthetic_one():
    """The core protocol-fidelity proof: turn 2's function_call_output must
    reference the REAL call_id the (fake) provider issued in turn 1's
    response, not an invented one. ProtocolValidatingFakeResponsesClient
    would reject a synthetic ID outright."""
    real_call_id = "call_xyz789_not_turn_0"
    client = ProtocolValidatingFakeResponsesClient(
        turns=[
            [
                _function_call(
                    "search_issues", {"repo": "acme/webapp", "query": "bug"}, real_call_id
                )
            ],
            [],  # turn 2: model observes output and stops
        ]
    )
    adapter = OpenAIResponsesAdapter(client, model="gpt-test")

    # Turn 1: model proposes the tool call.
    decision1 = await adapter.decide("search for bugs", [CALC_TOOL], [])
    assert decision1.tool_name == "search_issues"

    # The harness (BenchmarkRunner, not simulated here) would execute the
    # tool via MCP and produce a real TurnResult; we feed that back in.
    history = [
        _executed_turn(
            0,
            "search_issues",
            {"repo": "acme/webapp", "query": "bug"},
            raw_text_output="1 issue found",
        )
    ]

    # Turn 2: the adapter must replay the exact call_id from turn 1.
    await adapter.decide("search for bugs", [CALC_TOOL], history)

    second_request_input = client.calls[1]["input"]
    function_call_output = next(
        item
        for item in second_request_input
        if isinstance(item, dict) and item.get("type") == "function_call_output"
    )
    assert function_call_output["call_id"] == real_call_id
    assert function_call_output["output"] == "1 issue found"

    # The original function_call item itself (as the provider issued it) is
    # replayed verbatim, not reconstructed as a bare {name, arguments} dict.
    replayed_function_call = next(
        item for item in second_request_input if getattr(item, "type", None) == "function_call"
    )
    assert replayed_function_call.call_id == real_call_id

    # (ProtocolValidatingFakeResponsesClient's own assertions inside
    # create() already enforce this — reaching here without an
    # AssertionError from the fake is itself part of the proof.)


async def test_no_synthetic_call_id_is_invented_for_multi_turn():
    """Guards against a regression to inventing IDs like 'turn-0': using the
    validating fake, a request whose function_call_output uses any call_id
    other than the one actually issued must be rejected by the fake — so
    if a future change reverts to synthesis, this test fails."""
    real_call_id = "call_real_0001"
    client = ProtocolValidatingFakeResponsesClient(
        turns=[
            [_function_call("calculate_sum", {"a": 1, "b": 2}, real_call_id)],
            [],
        ]
    )
    adapter = OpenAIResponsesAdapter(client, model="gpt-test")
    await adapter.decide("add 1 and 2", [CALC_TOOL], [])
    history = [_executed_turn(0, "calculate_sum", {"a": 1, "b": 2}, raw_text_output="3")]
    # If the adapter invented a call_id like "turn-0" instead of replaying
    # `real_call_id`, ProtocolValidatingFakeResponsesClient.create() would
    # raise an AssertionError here.
    await adapter.decide("add 1 and 2", [CALC_TOOL], history)


# ---- reasoning-item continuity (Part 2, Option A) ----


async def test_reasoning_items_are_replayed_verbatim_without_being_inspected():
    """A reasoning-capable model's opaque reasoning item (alongside the
    function call) must be replayed on the next turn — the adapter must
    never drop it or need to understand its content."""
    real_call_id = "call_reasoning_turn"
    reasoning = _reasoning_item("reasoning_abc")
    client = ProtocolValidatingFakeResponsesClient(
        turns=[
            [reasoning, _function_call("calculate_sum", {"a": 1, "b": 2}, real_call_id)],
            [],
        ]
    )
    adapter = OpenAIResponsesAdapter(client, model="gpt-test")
    await adapter.decide("add 1 and 2", [CALC_TOOL], [])
    history = [_executed_turn(0, "calculate_sum", {"a": 1, "b": 2}, raw_text_output="3")]
    await adapter.decide("add 1 and 2", [CALC_TOOL], history)

    second_request_input = client.calls[1]["input"]
    assert reasoning in second_request_input  # replayed verbatim, unmodified


async def test_reasoning_item_content_never_appears_in_provenance():
    """Opaque reasoning items are cached for replay but never inspected,
    logged, or surfaced — provenance carries only usage/identity metadata,
    never any item content."""
    reasoning = _reasoning_item("reasoning_should_not_leak_12345")
    client = ProtocolValidatingFakeResponsesClient(
        turns=[[reasoning, _function_call("calculate_sum", {"a": 1, "b": 2}, "call_1")]]
    )
    adapter = OpenAIResponsesAdapter(client, model="gpt-test")
    await adapter.decide("add 1 and 2", [CALC_TOOL], [])
    serialized = adapter.provenance.model_dump_json()
    assert "reasoning_should_not_leak_12345" not in serialized


# ---- incomplete response handling (Part 4) ----


async def test_incomplete_response_becomes_controlled_error_not_a_partial_decision():
    incomplete = SimpleNamespace(reason="max_output_tokens")
    client = FakeResponsesClient(
        [_response(output=[], usage=_usage(), incomplete_details=incomplete)]
    )
    adapter = OpenAIResponsesAdapter(client, model="gpt-test")
    with pytest.raises(OpenAIAdapterError, match="incomplete"):
        await adapter.decide("say hello", [CALC_TOOL], [])


async def test_incomplete_response_is_recorded_in_provenance_as_an_error():
    incomplete = SimpleNamespace(reason="max_output_tokens")
    client = FakeResponsesClient(
        [_response(output=[], usage=_usage(), incomplete_details=incomplete)]
    )
    adapter = OpenAIResponsesAdapter(client, model="gpt-test")
    with pytest.raises(OpenAIAdapterError):
        await adapter.decide("say hello", [CALC_TOOL], [])
    record = adapter.provenance.provider_calls[0]
    assert record.status == "error"
    assert "max_output_tokens" in record.error


# ---- provider errors, timeouts, sanitization (Part K / R) ----


async def test_provider_exception_becomes_controlled_adapter_error():
    client = FakeResponsesClient(exception=RuntimeError("connection reset"))
    adapter = OpenAIResponsesAdapter(client, model="gpt-test")
    with pytest.raises(OpenAIAdapterError, match="connection reset"):
        await adapter.decide("say hello", [CALC_TOOL], [])


async def test_provider_timeout_like_exception_becomes_controlled_adapter_error():
    class FakeTimeoutError(Exception):
        pass

    client = FakeResponsesClient(exception=FakeTimeoutError("Request timed out after 30.0s"))
    adapter = OpenAIResponsesAdapter(client, model="gpt-test")
    with pytest.raises(OpenAIAdapterError, match="timed out"):
        await adapter.decide("say hello", [CALC_TOOL], [])


async def test_provider_exception_chain_is_suppressed_not_just_message_sanitized():
    """The `from None` boundary: the raised OpenAIAdapterError must not
    carry the original exception as __cause__ for traceback formatting to
    walk into — see the exception-sanitization hardening."""
    original = RuntimeError("Authorization: Bearer SECRET-SHOULD-NOT-LEAK")
    client = FakeResponsesClient(exception=original)
    adapter = OpenAIResponsesAdapter(client, model="gpt-test")
    with pytest.raises(OpenAIAdapterError) as excinfo:
        await adapter.decide("say hello", [CALC_TOOL], [])
    assert excinfo.value.__cause__ is None
    assert excinfo.value.__suppress_context__ is True


def test_sanitize_provider_error_redacts_api_key_like_strings():
    exc = RuntimeError("Authentication failed for key sk-abcdefghij1234567890ABCDEFGHIJ")
    sanitized = _sanitize_provider_error(exc)
    assert "sk-abcdefghij1234567890ABCDEFGHIJ" not in sanitized
    assert "REDACTED" in sanitized


def test_sanitize_provider_error_redacts_bearer_and_authorization_header_strings():
    exc = RuntimeError("Authorization: Bearer SECRET-SHOULD-NOT-LEAK")
    sanitized = _sanitize_provider_error(exc)
    assert "SECRET-SHOULD-NOT-LEAK" not in sanitized


def test_sanitize_provider_error_has_no_traceback():
    exc = RuntimeError("boom")
    sanitized = _sanitize_provider_error(exc)
    assert "Traceback" not in sanitized
    assert 'File "' not in sanitized


def test_sanitize_provider_error_leads_with_exception_category():
    """Allow-list design: the exception's type name always leads, rather
    than an unstructured message-only string."""
    exc = RuntimeError("some detail")
    sanitized = _sanitize_provider_error(exc)
    assert sanitized.startswith("RuntimeError")


def test_sanitize_provider_error_includes_status_code_and_request_id_when_present():
    """Structured, known-safe fields (as the SDK's APIStatusError family
    exposes) are included explicitly, not extracted by parsing free text."""

    class FakeAPIError(Exception):
        def __init__(self):
            super().__init__("Rate limit exceeded")
            self.status_code = 429
            self.request_id = "req_abc123"

    sanitized = _sanitize_provider_error(FakeAPIError())
    assert "status=429" in sanitized
    assert "request_id=req_abc123" in sanitized


def test_sanitize_provider_error_message_excerpt_is_bounded_not_unrestricted():
    """The free-text portion is a bounded excerpt, not an open-ended blob —
    this project does not claim its redaction patterns are an exhaustive
    secret scanner, so boundedness (not pattern-matching alone) is the
    actual safety property for arbitrarily long/unexpected SDK messages."""
    huge_message = "x" * 10_000
    exc = RuntimeError(huge_message)
    sanitized = _sanitize_provider_error(exc)
    assert len(sanitized) < 300


def test_default_max_retries_is_zero():
    assert DEFAULT_MAX_RETRIES == 0


def test_openai_sdk_available_reflects_real_importability():
    """Not monkeypatched here — this is the one place we check the REAL
    importlib probe behaves sanely (a bool, consistent with whether openai
    is actually importable), separate from the injectable seam used
    elsewhere to make API-layer tests environment-independent."""
    import importlib.util

    assert openai_sdk_available() == (importlib.util.find_spec("openai") is not None)


# ---- provenance / usage accounting (Part G / O) ----


async def test_provenance_records_token_usage_per_call():
    client = FakeResponsesClient(
        [
            _response(
                output=[_function_call("calculate_sum", {"a": 1, "b": 2})], usage=_usage(10, 5, 15)
            )
        ]
    )
    adapter = OpenAIResponsesAdapter(client, model="gpt-test")
    adapter.bind_case("case-1")
    await adapter.decide("add 1 and 2", [CALC_TOOL], [])

    assert adapter.provenance.total_provider_calls == 1
    assert adapter.provenance.total_input_tokens == 10
    assert adapter.provenance.total_output_tokens == 5
    assert adapter.provenance.total_tokens == 15
    assert adapter.provenance.provider_calls[0].case_id == "case-1"
    assert adapter.provenance.provider_calls[0].status == "ok"


async def test_provenance_records_failed_calls_without_inventing_zero_usage():
    client = FakeResponsesClient(exception=RuntimeError("rate limited"))
    adapter = OpenAIResponsesAdapter(client, model="gpt-test")
    adapter.bind_case("case-1")
    with pytest.raises(OpenAIAdapterError):
        await adapter.decide("add 1 and 2", [CALC_TOOL], [])

    record = adapter.provenance.provider_calls[0]
    assert record.status == "error"
    assert record.input_tokens is None  # not fabricated as 0
    assert record.output_tokens is None
    assert "rate limited" in record.error


async def test_provenance_never_contains_credential_data():
    client = FakeResponsesClient([_response(output=[], usage=_usage())])
    adapter = OpenAIResponsesAdapter(client, model="gpt-test")
    await adapter.decide("say hello", [CALC_TOOL], [])
    serialized = adapter.provenance.model_dump_json()
    assert "api_key" not in serialized.lower()
    assert "authorization" not in serialized.lower()
    assert "sk-" not in serialized


async def test_provenance_records_model_and_policy_identity():
    client = FakeResponsesClient([_response(output=[], usage=_usage(), model="gpt-test-returned")])
    adapter = OpenAIResponsesAdapter(client, model="gpt-test")
    await adapter.decide("say hello", [CALC_TOOL], [])
    assert adapter.provenance.requested_model == "gpt-test"
    assert adapter.provenance.provider_calls[0].returned_model == "gpt-test-returned"
    assert adapter.provenance.baseline_policy_version == "real-model-baseline-v1"
    assert len(adapter.provenance.baseline_policy_sha256) == 64


# ---- bind_case resets per-case provider-conversation-state cache ----


async def test_bind_case_resets_the_provider_output_cache():
    """A stale cached provider item from a previous case must never leak
    into the next case's requests."""
    client = ProtocolValidatingFakeResponsesClient(
        turns=[
            [_function_call("calculate_sum", {"a": 1, "b": 2}, "call_case1_turn0")],
            [_function_call("calculate_sum", {"a": 3, "b": 4}, "call_case2_turn0")],
        ]
    )
    adapter = OpenAIResponsesAdapter(client, model="gpt-test")

    adapter.bind_case("case-1")
    await adapter.decide("add 1 and 2", [CALC_TOOL], [])

    adapter.bind_case("case-2")  # new case: cache must reset
    decision = await adapter.decide("add 3 and 4", [CALC_TOOL], [])
    assert decision.tool_name == "calculate_sum"

    # Turn 0 of case-2 has no history, so no replay is attempted — if the
    # cache hadn't reset, a stale entry from case-1 could otherwise be
    # replayed into case-2's request by mistake in a future code path.
    assert client.calls[1]["input"] == [{"role": "user", "content": "add 3 and 4"}]


async def test_missing_cached_provider_output_raises_a_clear_defensive_error():
    """If history references a turn this adapter never actually produced
    (should not happen in normal operation), fail loudly rather than invent
    a call_id."""
    adapter = OpenAIResponsesAdapter(FakeResponsesClient([]), model="gpt-test")
    history = [_executed_turn(0, "calculate_sum", {"a": 1, "b": 2}, raw_text_output="3")]
    with pytest.raises(OpenAIAdapterError, match="No cached provider output"):
        adapter._build_input_list("add 1 and 2", history)  # noqa: SLF001 - deliberate white-box test
