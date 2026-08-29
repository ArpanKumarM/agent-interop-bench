"""Loads the A2A benchmark suite from its YAML file.

Deliberately separate from ``app.core.benchmarks.load_benchmark_suite``:
that loader scans a directory non-recursively for ``*.yaml``/``*.yml`` and
merges everything into one ``BenchmarkSuite`` -- letting an A2A suite file
sit anywhere under the same scanned directory would make it try (and fail)
to validate A2A cases as MCP ``BenchmarkCase``s. The A2A suite lives at
``benchmarks/a2a/a2a_suite.yaml``, in a subdirectory the MCP loader's
non-recursive scan never reaches, and is loaded only through this function.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from app.models.a2a import A2ABenchmarkSuite


def load_a2a_suite(path: str | Path) -> A2ABenchmarkSuite:
    """Load the A2A benchmark suite from a single YAML file."""
    data = yaml.safe_load(Path(path).read_text())
    return A2ABenchmarkSuite.model_validate(data)
