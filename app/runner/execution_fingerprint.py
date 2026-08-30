"""Execution fingerprint for composed live experiment runs (Phase 4A.3e).

``PilotExperimentPlan.config_hash`` answers "is this the same experiment
*methodology*". It deliberately does NOT cover the things that can silently
change what a live run actually does while the plan file stays byte-
identical: the resolved overlay CONTENT behind an unchanged overlay id, the
exact source commit, the host policy text, or the host-action tool schema.

``execution_fingerprint_sha256`` is a second, strictly additive identity
derived from all five:

    config_hash
    source_commit_sha
    resolved_overlay_bundle_sha256   (overlay CONTENT, not just ids)
    host_policy_sha256
    tool_schema_sha256

A resume is refused if the fingerprint differs even when config_hash is
identical -- so "same methodology, different stimulus text / different
code" can never be silently appended to an existing run's ledger.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

from app.models.execution_fingerprint import ExecutionFingerprint
from app.models.live_overlay import LiveExperimentOverlay
from app.models.pilot_plan import PilotExperimentPlan
from app.runner.host_action_schema_openai import host_action_schema_fingerprint
from app.runner.host_adapters import DEFAULT_HOST_POLICY_TEXT

__all__ = [
    "ExecutionFingerprint",
    "ExecutionFingerprintError",
    "compute_execution_fingerprint",
    "host_policy_sha256",
    "resolve_source_commit_sha",
    "resolved_overlay_bundle_sha256",
]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SOURCE_COMMIT_ENV_VARS = ("A2AVALIDATOR_SOURCE_COMMIT", "SOURCE_COMMIT_SHA")


class ExecutionFingerprintError(RuntimeError):
    """The execution fingerprint could not be computed (e.g. the source
    commit SHA is indeterminable and no override env var is set)."""


def host_policy_sha256() -> str:
    """SHA-256 of the exact host policy text sent on every request
    (``DEFAULT_HOST_POLICY_TEXT``) -- the same value
    ``RealHostAgentAdapter`` records as ``host_policy_sha256`` at decide
    time, computed here up front without any provider call."""
    return hashlib.sha256(DEFAULT_HOST_POLICY_TEXT.encode("utf-8")).hexdigest()


def resolve_source_commit_sha() -> str:
    """The exact source commit. An explicit env override wins (for CI /
    reproducible builds); otherwise ``git rev-parse HEAD`` in the repo
    root. Raises rather than guessing."""
    for var in _SOURCE_COMMIT_ENV_VARS:
        value = os.environ.get(var)
        if value and value.strip():
            return value.strip()
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            cwd=_REPO_ROOT,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ExecutionFingerprintError(
            f"cannot determine the source commit SHA; set {_SOURCE_COMMIT_ENV_VARS[0]} explicitly."
        ) from exc
    sha = result.stdout.strip()
    if not sha:
        raise ExecutionFingerprintError("`git rev-parse HEAD` returned nothing.")
    return sha


def resolved_overlay_bundle_sha256(overlays: list[LiveExperimentOverlay]) -> str:
    """Canonical SHA-256 of the RESOLVED overlay contents, in the given
    order. Two overlays that share an id but differ in any field
    (``remote_artifact_text``, ``local_tool_arguments``, canaries, prompt,
    ...) produce different bundles."""
    canonical = json.dumps(
        [overlay.model_dump(mode="json") for overlay in overlays],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _combine(
    *,
    config_hash: str,
    source_commit_sha: str,
    resolved_overlay_bundle_sha256: str,
    host_policy_sha256: str,
    tool_schema_sha256: str,
    schedule_sha256: str | None,
) -> str:
    payload = {
        "config_hash": config_hash,
        "source_commit_sha": source_commit_sha,
        "resolved_overlay_bundle_sha256": resolved_overlay_bundle_sha256,
        "host_policy_sha256": host_policy_sha256,
        "tool_schema_sha256": tool_schema_sha256,
    }
    # Folded in only when a blocked schedule applies (Phase 4B+), so every
    # already-frozen v1/v2 fingerprint stays byte-identical.
    if schedule_sha256 is not None:
        payload["schedule_sha256"] = schedule_sha256
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compute_execution_fingerprint(
    plan: PilotExperimentPlan,
    resolved_overlays: list[LiveExperimentOverlay],
    *,
    source_commit_sha: str | None = None,
    tool_schema_sha256: str | None = None,
    schedule_sha256: str | None = None,
) -> ExecutionFingerprint:
    """Build the fingerprint from a resolved plan + its resolved overlays.
    ``source_commit_sha``/``tool_schema_sha256`` may be injected (tests);
    otherwise they are resolved from the working tree / the canonical
    host-action schema. ``schedule_sha256`` is the run's frozen blocked
    trial-schedule hash (Phase 4B); ``None`` for v1/v2."""
    commit = source_commit_sha if source_commit_sha is not None else resolve_source_commit_sha()
    tool_hash = (
        tool_schema_sha256 if tool_schema_sha256 is not None else host_action_schema_fingerprint()
    )
    policy_hash = host_policy_sha256()
    bundle_hash = resolved_overlay_bundle_sha256(resolved_overlays)
    fingerprint = _combine(
        config_hash=plan.config_hash,
        source_commit_sha=commit,
        resolved_overlay_bundle_sha256=bundle_hash,
        host_policy_sha256=policy_hash,
        tool_schema_sha256=tool_hash,
        schedule_sha256=schedule_sha256,
    )
    return ExecutionFingerprint(
        config_hash=plan.config_hash,
        source_commit_sha=commit,
        resolved_overlay_bundle_sha256=bundle_hash,
        host_policy_sha256=policy_hash,
        tool_schema_sha256=tool_hash,
        schedule_sha256=schedule_sha256,
        execution_fingerprint_sha256=fingerprint,
    )
