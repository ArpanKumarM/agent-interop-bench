"""Loads the frozen real-model baseline agent policy.

Real-model benchmark results are meaningless without knowing exactly what
system prompt produced them. The policy text lives as a versioned,
plain-text repository artifact (``policies/real_model_baseline_v1.txt``)
rather than an inline string, and this module exposes it alongside its
version tag and a SHA-256 hash of the exact bytes — both are persisted in
every live-model run's provenance (see ``app.models.provenance``) so a
score can always be traced back to the exact policy that produced it.

This module must not be edited to "tune" the policy after observing live
results; a behavior change requires a new versioned file and a new version
tag (e.g. ``real_model_baseline_v2``), never a silent edit of v1's text.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

BASELINE_POLICY_VERSION = "real-model-baseline-v1"

_POLICY_PATH = (
    Path(__file__).resolve().parent.parent.parent / "policies" / "real_model_baseline_v1.txt"
)

BASELINE_POLICY_TEXT = _POLICY_PATH.read_text(encoding="utf-8")
BASELINE_POLICY_SHA256 = hashlib.sha256(BASELINE_POLICY_TEXT.encode("utf-8")).hexdigest()
