"""Unit tests for the smallest reusable mutation-approval predicate."""

from __future__ import annotations

from app.runner.mutation_gate import mutation_blocked


def test_mutation_blocked_when_mutating_and_not_approved():
    assert mutation_blocked(is_mutating=True, approved=False) is True


def test_mutation_not_blocked_when_mutating_and_approved():
    assert mutation_blocked(is_mutating=True, approved=True) is False


def test_mutation_never_blocked_when_not_mutating():
    assert mutation_blocked(is_mutating=False, approved=False) is False
    assert mutation_blocked(is_mutating=False, approved=True) is False
