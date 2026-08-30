"""The smallest reusable mutation-approval predicate (Phase 3D.3).

Extracted as a tiny, dependency-free function -- not a shared runner
interface. ``app.runner.engine.BenchmarkRunner._blocked_turn`` (the 29-case
MCP suite's mutation gate) is completely untouched; this exists only so
``ComposedBenchmarkRunner`` can apply the identical rule (a mutating action
is blocked unless explicitly approved) without duplicating the predicate's
logic by hand or forcing the two runners into a shared interface.
"""

from __future__ import annotations


def mutation_blocked(is_mutating: bool, approved: bool) -> bool:
    return is_mutating and not approved
