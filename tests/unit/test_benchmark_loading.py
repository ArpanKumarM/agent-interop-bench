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
