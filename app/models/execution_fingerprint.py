"""The execution-fingerprint record (Phase 4A.3e).

A plain data model with no runner/loader dependencies, so it can be
embedded in ``ComposedModelRunProvenance`` and written to run metadata
without an import cycle. The values are computed by
``app.runner.execution_fingerprint``.
"""

from __future__ import annotations

from pydantic import BaseModel


class ExecutionFingerprint(BaseModel):
    """The five component identities plus the single derived fingerprint.

    ``execution_fingerprint_sha256`` is SHA-256 over the canonical JSON of
    the other five fields. It is strictly additive to
    ``PilotExperimentPlan.config_hash`` (still carried here as
    ``config_hash``) -- a resume is refused when it differs even if
    ``config_hash`` is identical.
    """

    config_hash: str
    source_commit_sha: str
    resolved_overlay_bundle_sha256: str
    host_policy_sha256: str
    tool_schema_sha256: str
    # Phase 4B: SHA-256 of this run's frozen BLOCKED trial schedule (the
    # per-model 80-entry ordering). None for runs with no explicit schedule
    # (v1/v2) -- folded into execution_fingerprint_sha256 only when present,
    # so pre-Phase-4B fingerprints are byte-unchanged.
    schedule_sha256: str | None = None
    # Phase 6B (fingerprint v2). All None on a v1 fingerprint -- folded into
    # execution_fingerprint_sha256 only when present, so every already-frozen
    # Phase 4A/4B fingerprint verifies byte-identically.
    fingerprint_version: str = "v1"
    canonical_action_schema_sha256: str | None = None
    uv_lock_sha256: str | None = None
    python_runtime_version: str | None = None
    # Phase 6C (fingerprint v2, finalised): SHA-256 over the exact
    # provider-specific inference interface -- provider id, exact model id,
    # provider wire-tool-schema hash, provider request-parameter hash, and
    # API mode. None on any pre-6C fingerprint (folded in only when present,
    # so Phase 4B v1 verification stays byte-identical).
    provider_config_sha256: str | None = None
    execution_fingerprint_sha256: str
