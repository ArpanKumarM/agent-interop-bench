"""Loads live-experiment overlays (Phase 4A.2) from a single YAML file.

Structurally parallel to ``app.core.composed_benchmarks.load_composed_suite``:
a single dedicated loader, never scanned by any other loader, so an
overlay file is never mistakenly validated as a deterministic
``ComposedBenchmarkCase``.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from app.models.live_overlay import LiveOverlaySuite


def load_live_overlays(path: str | Path) -> LiveOverlaySuite:
    data = yaml.safe_load(Path(path).read_text())
    return LiveOverlaySuite.model_validate(data)
