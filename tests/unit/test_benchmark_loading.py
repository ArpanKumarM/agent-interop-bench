import pytest
from pydantic import ValidationError

from app.core.benchmarks import load_benchmark_suite
from app.models.benchmark import BenchmarkCase, BenchmarkSuite


def test_loads_core_suite_from_directory():
    suite = load_benchmark_suite("benchmarks/")
    assert suite.name == "agent-interop-core"
    assert len(suite.cases) >= 15


def test_all_required_categories_present():
    suite = load_benchmark_suite("benchmarks/")
    categories = {case.category.value for case in suite.cases}
    required = {
        "correct_tool_selection",
        "incorrect_tool_selection",
        "valid_arguments",
        "missing_required_argument",
        "incorrect_argument_type",
        "hallucinated_tool",
        "timeout_behavior",
        "tool_exception",
        "malformed_response",
        "prompt_injection",
        "unsafe_mutation",
    }
    assert required <= categories


def test_case_ids_are_unique():
    suite = load_benchmark_suite("benchmarks/")
    ids = [case.id for case in suite.cases]
    assert len(ids) == len(set(ids))


def test_duplicate_case_id_rejected():
    with pytest.raises(ValidationError):
        BenchmarkSuite(
            name="dup",
            cases=[
                BenchmarkCase(
                    id="same-id",
                    category="correct_tool_selection",
                    user_prompt="a",
                    expected_tool="calculate_sum",
                    expected_outcome="success",
                ),
                BenchmarkCase(
                    id="same-id",
                    category="correct_tool_selection",
                    user_prompt="b",
                    expected_tool="calculate_sum",
                    expected_outcome="success",
                ),
            ],
        )


def test_simulated_agent_response_defaults_to_expected():
    case = BenchmarkCase(
        id="x",
        category="correct_tool_selection",
        user_prompt="add 1 and 2",
        expected_tool="calculate_sum",
        expected_arguments={"a": 1, "b": 2},
        expected_outcome="success",
    )
    assert case.simulated_agent_response is not None
    assert case.simulated_agent_response.tool_name == "calculate_sum"
    assert case.simulated_agent_response.arguments == {"a": 1, "b": 2}


def test_max_turns_defaults_to_one():
    case = BenchmarkCase(
        id="x",
        category="correct_tool_selection",
        user_prompt="add 1 and 2",
        expected_tool="calculate_sum",
        expected_outcome="success",
    )
    assert case.max_turns == 1


def test_simulated_reaction_without_turn_budget_is_rejected():
    """A case that sets simulated_reaction but leaves max_turns at 1 is a config
    mistake the runner would never surface: the loop stops after turn 0."""
    with pytest.raises(ValidationError):
        BenchmarkCase(
            id="x",
            category="prompt_injection",
            user_prompt="search for something",
            expected_tool="search_issues",
            simulated_failure_mode="prompt_injection",
            expected_outcome="success",
            simulated_reaction={"tool_name": None},
        )


def test_simulated_reaction_with_turn_budget_is_accepted():
    case = BenchmarkCase(
        id="x",
        category="prompt_injection",
        user_prompt="search for something",
        expected_tool="search_issues",
        simulated_failure_mode="prompt_injection",
        expected_outcome="success",
        max_turns=2,
        simulated_reaction={"tool_name": None},
    )
    assert case.max_turns == 2
    assert case.simulated_reaction is not None
    assert case.simulated_reaction.tool_name is None


def test_argument_match_rule_for_unknown_argument_is_rejected():
    with pytest.raises(ValidationError):
        BenchmarkCase(
            id="x",
            category="correct_tool_selection",
            user_prompt="search for something",
            expected_tool="search_issues",
            expected_arguments={"repo": "acme/webapp", "query": "login failures"},
            expected_outcome="success",
            argument_match_rules={
                "nonexistent_field": {"matcher": "contains_substrings", "terms": ["x"]}
            },
        )


def test_contains_substrings_matcher_without_terms_is_rejected():
    with pytest.raises(ValidationError):
        BenchmarkCase(
            id="x",
            category="correct_tool_selection",
            user_prompt="search for something",
            expected_tool="search_issues",
            expected_arguments={"repo": "acme/webapp", "query": "login failures"},
            expected_outcome="success",
            argument_match_rules={"query": {"matcher": "contains_substrings"}},
        )


def test_default_argument_match_rules_is_empty():
    case = BenchmarkCase(
        id="x",
        category="correct_tool_selection",
        user_prompt="search for something",
        expected_tool="search_issues",
        expected_arguments={"repo": "acme/webapp", "query": "login failures"},
        expected_outcome="success",
    )
    assert case.argument_match_rules == {}


def test_injected_turns_defaults_to_none_meaning_turn_zero_only():
    case = BenchmarkCase(
        id="x",
        category="prompt_injection",
        user_prompt="search for something",
        expected_tool="search_issues",
        simulated_failure_mode="prompt_injection",
        expected_outcome="success",
    )
    assert case.injected_turns is None


def test_injected_turns_out_of_range_rejected():
    with pytest.raises(ValidationError):
        BenchmarkCase(
            id="x",
            category="prompt_injection",
            user_prompt="search for something",
            expected_tool="search_issues",
            simulated_failure_mode="prompt_injection",
            expected_outcome="success",
            max_turns=2,
            injected_turns=[0, 2],
        )


def test_injected_turns_with_normal_failure_mode_rejected():
    with pytest.raises(ValidationError):
        BenchmarkCase(
            id="x",
            category="correct_tool_selection",
            user_prompt="search for something",
            expected_tool="search_issues",
            expected_outcome="success",
            max_turns=2,
            injected_turns=[0],
        )


def test_injected_turns_empty_list_rejected():
    with pytest.raises(ValidationError):
        BenchmarkCase(
            id="x",
            category="prompt_injection",
            user_prompt="search for something",
            expected_tool="search_issues",
            simulated_failure_mode="prompt_injection",
            expected_outcome="success",
            max_turns=2,
            injected_turns=[],
        )


def test_simulated_reactions_list_accepted_for_more_than_one_reaction():
    case = BenchmarkCase(
        id="x",
        category="prompt_injection",
        user_prompt="search for something",
        expected_tool="search_issues",
        simulated_failure_mode="prompt_injection",
        expected_outcome="success",
        max_turns=3,
        injected_turns=[0, 1],
        simulated_reactions=[{"tool_name": "search_issues"}, {"tool_name": None}],
    )
    assert len(case.simulated_reactions) == 2


def test_simulated_reaction_and_simulated_reactions_are_mutually_exclusive():
    with pytest.raises(ValidationError):
        BenchmarkCase(
            id="x",
            category="prompt_injection",
            user_prompt="search for something",
            expected_tool="search_issues",
            simulated_failure_mode="prompt_injection",
            expected_outcome="success",
            max_turns=3,
            simulated_reaction={"tool_name": None},
            simulated_reactions=[{"tool_name": None}],
        )


def test_simulated_reactions_requires_enough_turn_budget():
    with pytest.raises(ValidationError):
        BenchmarkCase(
            id="x",
            category="prompt_injection",
            user_prompt="search for something",
            expected_tool="search_issues",
            simulated_failure_mode="prompt_injection",
            expected_outcome="success",
            max_turns=2,
            simulated_reactions=[{"tool_name": "search_issues"}, {"tool_name": None}],
        )


def test_max_turns_out_of_bounds_rejected():
    with pytest.raises(ValidationError):
        BenchmarkCase(
            id="x",
            category="correct_tool_selection",
            user_prompt="add 1 and 2",
            expected_tool="calculate_sum",
            expected_outcome="success",
            max_turns=0,
        )
    with pytest.raises(ValidationError):
        BenchmarkCase(
            id="x",
            category="correct_tool_selection",
            user_prompt="add 1 and 2",
            expected_tool="calculate_sum",
            expected_outcome="success",
            max_turns=11,
        )


def test_original_21_cases_multi_turn_cases_have_turn_budget():
    """Mechanical check that the two Phase 2A/2B multi-turn fixture cases are wired
    correctly, and that every other one of the original 21 cases is still
    single-turn (max_turns=1, no simulated_reaction). Scoped to the original
    21 IDs -- Phase 2D's own multi-turn cases are covered by
    tests/integration/test_phase_2d_adversarial_cases.py."""
    suite = load_benchmark_suite("benchmarks/")
    multi_turn_ids = {
        "injection-003-resists-hijack-attempt",
        "injection-004-hijacked-into-mutation",
    }
    phase_2d_ids = {
        "injection-005-redirects-to-different-tool",
        "injection-006-argument-poisoning",
        "injection-007-repeated-injection-resists-twice",
        "injection-008-repeated-injection-worn-down",
        "exception-003-unsafe-fallback-after-failure",
        "exception-004-safe-recovery-after-failure",
        "timeout-003-safe-recovery-after-timeout",
        "hallucinated-002-mid-conversation-hallucination",
    }
    for case in suite.cases:
        if case.id in phase_2d_ids:
            continue
        if case.id in multi_turn_ids:
            assert case.max_turns >= 2, case.id
            assert case.simulated_reaction is not None, case.id
        else:
            assert case.max_turns == 1, case.id
            assert case.simulated_reaction is None, case.id
