"""Loads benchmark suites from YAML files on disk."""

from __future__ import annotations

from pathlib import Path

import yaml

from app.models.benchmark import BenchmarkCase, BenchmarkSuite

DEFAULT_SUITE_NAME = "agent-interop-core"
DEFAULT_SUITE_VERSION = "0.1.0"


def load_benchmark_suite(path: str | Path) -> BenchmarkSuite:
    """Load a benchmark suite from a single YAML file or a directory of them.

    A directory is scanned (non-recursively) for ``*.yaml``/``*.yml`` files,
    each containing either a full ``{name, version, cases}`` document or a
    bare list of cases; all cases are merged into one suite.
    """
    resolved = Path(path)

    if resolved.is_dir():
        cases: list[BenchmarkCase] = []
        name = DEFAULT_SUITE_NAME
        version = DEFAULT_SUITE_VERSION
        files = sorted(resolved.glob("*.yaml")) + sorted(resolved.glob("*.yml"))
        for file in files:
            data = yaml.safe_load(file.read_text())
            if data is None:
                continue
            if isinstance(data, dict) and "cases" in data:
                name = data.get("name", name)
                version = data.get("version", version)
                cases.extend(BenchmarkCase.model_validate(c) for c in data["cases"])
            elif isinstance(data, list):
                cases.extend(BenchmarkCase.model_validate(c) for c in data)
            else:
                raise ValueError(f"Unrecognized benchmark file format: {file}")
        return BenchmarkSuite(name=name, version=version, cases=cases)

    data = yaml.safe_load(resolved.read_text())
    return BenchmarkSuite.model_validate(data)
