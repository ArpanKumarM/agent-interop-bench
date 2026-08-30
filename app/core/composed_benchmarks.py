"""Loads the composed (cross-protocol) benchmark suite from its YAML file.

Structurally parallel to ``app.core.a2a_benchmarks.load_a2a_suite``: a
single dedicated file, never scanned by ``app.core.benchmarks``'s
non-recursive MCP loader, so a composed case is never mistakenly validated
as an MCP ``BenchmarkCase``.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from app.models.composed import ComposedBenchmarkSuite


def load_composed_suite(path: str | Path) -> ComposedBenchmarkSuite:
    """Load the composed benchmark suite from a single YAML file."""
    data = yaml.safe_load(Path(path).read_text())
    return ComposedBenchmarkSuite.model_validate(data)
