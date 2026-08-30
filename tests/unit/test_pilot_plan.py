"""Unit tests for PilotExperimentPlan's config_hash determinism."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.pilot_plan import PilotExperimentPlan


def _plan(**overrides) -> PilotExperimentPlan:
    defaults = dict(
        experiment_id="pilot-001",
        experiment_version="v1",
        model="some-model",
        overlay_ids=["a", "b"],
        trials_per_condition=5,
        max_decisions_per_trial=10,
        max_total_decisions=100,
        timeout_seconds=30.0,
        max_output_tokens=256,
    )
    defaults.update(overrides)
    return PilotExperimentPlan(**defaults)


def test_reasoning_effort_defaults_to_low_and_is_never_left_to_provider_default():
    plan = _plan()
    assert plan.reasoning_effort == "low"


def test_config_hash_is_deterministic_for_identical_config():
    assert _plan().config_hash == _plan().config_hash


def test_config_hash_ignores_created_at():
    from datetime import UTC, datetime

    a = _plan(created_at=datetime(2020, 1, 1, tzinfo=UTC))
    b = _plan(created_at=datetime(2030, 1, 1, tzinfo=UTC))
    assert a.config_hash == b.config_hash


def test_config_hash_ignores_overlay_id_order():
    a = _plan(overlay_ids=["a", "b"])
    b = _plan(overlay_ids=["b", "a"])
    assert a.config_hash == b.config_hash


@pytest.mark.parametrize(
    "field,value",
    [
        ("model", "different-model"),
        ("trials_per_condition", 6),
        ("max_decisions_per_trial", 11),
        ("max_total_decisions", 101),
        ("timeout_seconds", 31.0),
        ("max_output_tokens", 257),
        ("overlay_ids", ["a", "c"]),
        ("reasoning_effort", "medium"),
    ],
)
def test_config_hash_changes_when_any_substantive_field_changes(field, value):
    baseline = _plan()
    changed = _plan(**{field: value})
    assert baseline.config_hash != changed.config_hash


def test_config_hash_cannot_be_hand_supplied():
    plan = PilotExperimentPlan(
        experiment_id="pilot-001",
        experiment_version="v1",
        model="some-model",
        overlay_ids=["a"],
        trials_per_condition=1,
        max_decisions_per_trial=1,
        max_total_decisions=1,
        timeout_seconds=1.0,
        max_output_tokens=1,
        config_hash="not-a-real-hash",
    )
    assert plan.config_hash != "not-a-real-hash"


@pytest.mark.parametrize(
    "field",
    ["trials_per_condition", "max_decisions_per_trial", "max_total_decisions", "max_output_tokens"],
)
def test_zero_or_negative_int_fields_rejected(field):
    with pytest.raises(ValidationError):
        _plan(**{field: 0})


def test_non_positive_timeout_rejected():
    with pytest.raises(ValidationError):
        _plan(timeout_seconds=0)


def test_does_not_hardcode_a_production_model():
    import inspect

    from app.models import pilot_plan

    source = inspect.getsource(pilot_plan)
    for banned in ("gpt-", "claude-", "o1-", "o3-"):
        assert banned not in source.lower()
