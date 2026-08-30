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
    execution_fingerprint_sha256: str
