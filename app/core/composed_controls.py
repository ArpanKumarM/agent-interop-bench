"""Loads scenario-specific matched isolated controls for composed cases
(Phase 3D.2.1) from ``benchmarks/composed/isolated_controls.yaml``.

Each entry loads three real cases -- never references into
``core_suite.yaml``/``a2a_suite.yaml``: the TRUE matched pair
(``mcp_control``, ``a2a_control``, sharing the composed case's semantic
task/policy but never individually performing the forbidden cross-protocol
transfer -- see ``MatchedIsolatedControl``'s docstring), and a separate
``a2a_native_gap_control`` diagnostic. ``{canary:NAME}`` placeholders in
string fields are substituted with that composed case's actual
deterministic canary token (``app.models.composed.canary_token``, keyed by
the composed case's own id) before validation, so a control's fixture text
can reference the exact same canary the composed case embeds -- or a
structurally matched public twin -- without hand-computing any UUID.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.models.a2a import A2ABenchmarkCase
from app.models.benchmark import BenchmarkCase
from app.models.composed import MatchedIsolatedControl, canary_token


def _substitute_canary_placeholders(
    value: Any, composed_case_id: str, canary_names: list[str]
) -> Any:
    if isinstance(value, str):
        result = value
        for name in canary_names:
            result = result.replace(f"{{canary:{name}}}", canary_token(composed_case_id, name))
        return result
    if isinstance(value, dict):
        return {
            key: _substitute_canary_placeholders(item, composed_case_id, canary_names)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            _substitute_canary_placeholders(item, composed_case_id, canary_names) for item in value
        ]
    return value


def load_matched_control(
    path: str | Path, composed_case_id: str, canary_names: list[str]
) -> MatchedIsolatedControl:
    """Load and instantiate the matched control pair declared for
    ``composed_case_id`` in the YAML file at ``path``."""
    data = yaml.safe_load(Path(path).read_text())
    entry = data["controls"][composed_case_id]

    mcp_raw = _substitute_canary_placeholders(entry["mcp_control"], composed_case_id, canary_names)
    a2a_raw = _substitute_canary_placeholders(entry["a2a_control"], composed_case_id, canary_names)
    a2a_gap_raw = _substitute_canary_placeholders(
        entry["a2a_native_gap_control"], composed_case_id, canary_names
    )

    return MatchedIsolatedControl(
        mcp_control=BenchmarkCase.model_validate(mcp_raw),
        a2a_control=A2ABenchmarkCase.model_validate(a2a_raw),
        a2a_native_gap_control=A2ABenchmarkCase.model_validate(a2a_gap_raw),
    )
