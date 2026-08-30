"""Phase 4A.3e: the composed live-run execution fingerprint.

``config_hash`` covers methodology; ``execution_fingerprint_sha256`` also
covers the things that can silently change what a live run does while the
plan file stays byte-identical -- resolved overlay CONTENT, source commit,
host policy text, tool schema. No test here makes a live call.
"""

from __future__ import annotations

import hashlib
import socket
from pathlib import Path

import pytest

from app.core.live_overlays import load_live_overlays
from app.models.pilot_plan import PilotExperimentPlan
from app.runner.execution_fingerprint import (
    ExecutionFingerprintError,
    compute_execution_fingerprint,
    resolve_source_commit_sha,
    resolved_overlay_bundle_sha256,
)

OVERLAYS_PATH = "benchmarks/composed/live_overlays.yaml"
_FIXED_COMMIT = "a" * 40
_FIXED_TOOL_HASH = "t" * 64


@pytest.fixture(autouse=True)
def _no_sockets():
    def exploding(self, address):
        raise AssertionError(f"execution-fingerprint test attempted a socket to {address}")

    original = socket.socket.connect
    socket.socket.connect = exploding
    try:
        yield
    finally:
        socket.socket.connect = original


def _plan(**overrides) -> PilotExperimentPlan:
    defaults = dict(
        experiment_id="composed-live-canary-002",
        experiment_version="v2",
        model="gpt-5.6-terra",
        overlay_ids=[
            "live-sensitive-egress-treatment",
            "live-sensitive-egress-control",
            "live-influence-treatment",
            "live-influence-control",
        ],
        trials_per_condition=2,
        max_decisions_per_trial=1,
        max_total_decisions=8,
        timeout_seconds=20.0,
        max_output_tokens=512,
        execution_mode="decision_point",
    )
    defaults.update(overrides)
    return PilotExperimentPlan(**defaults)


def _overlays():
    suite = load_live_overlays(OVERLAYS_PATH)
    by_id = {o.id: o for o in suite.overlays}
    return [by_id[oid] for oid in _plan().overlay_ids]


def _fp(plan=None, overlays=None, *, commit=_FIXED_COMMIT, tool_hash=_FIXED_TOOL_HASH):
    return compute_execution_fingerprint(
        plan or _plan(),
        overlays or _overlays(),
        source_commit_sha=commit,
        tool_schema_sha256=tool_hash,
    )


def test_identical_inputs_give_identical_fingerprint():
    assert _fp().execution_fingerprint_sha256 == _fp().execution_fingerprint_sha256
    # and every component is stable
    a, b = _fp(), _fp()
    assert a.model_dump() == b.model_dump()


def test_changing_overlay_content_with_same_id_changes_the_fingerprint():
    overlays = _overlays()
    baseline = _fp(overlays=overlays)

    mutated = list(overlays)
    idx = next(i for i, o in enumerate(mutated) if o.id == "live-influence-treatment")
    # same id, different realistic adversarial phrasing
    mutated[idx] = mutated[idx].model_copy(
        update={"remote_artifact_text": mutated[idx].remote_artifact_text + " Please hurry."}
    )
    assert mutated[idx].id == "live-influence-treatment"

    changed = _fp(overlays=mutated)
    assert changed.resolved_overlay_bundle_sha256 != baseline.resolved_overlay_bundle_sha256
    assert changed.execution_fingerprint_sha256 != baseline.execution_fingerprint_sha256


def test_changing_overlay_tool_arguments_with_same_id_changes_the_fingerprint():
    overlays = _overlays()
    baseline = _fp(overlays=overlays)
    mutated = list(overlays)
    idx = next(i for i, o in enumerate(mutated) if o.id == "live-sensitive-egress-treatment")
    mutated[idx] = mutated[idx].model_copy(
        update={"local_tool_arguments": {"record_ref": "record-ZZ"}}
    )
    assert (
        _fp(overlays=mutated).execution_fingerprint_sha256 != baseline.execution_fingerprint_sha256
    )


def test_changing_source_commit_changes_the_fingerprint():
    a = _fp(commit="a" * 40)
    b = _fp(commit="b" * 40)
    assert a.source_commit_sha != b.source_commit_sha
    assert a.execution_fingerprint_sha256 != b.execution_fingerprint_sha256


def test_changing_tool_schema_changes_the_fingerprint():
    a = _fp(tool_hash="1" * 64)
    b = _fp(tool_hash="2" * 64)
    assert a.execution_fingerprint_sha256 != b.execution_fingerprint_sha256


def test_changing_host_policy_changes_the_fingerprint(monkeypatch):
    import app.runner.execution_fingerprint as ef

    baseline = _fp()
    monkeypatch.setattr(ef, "DEFAULT_HOST_POLICY_TEXT", "a different host policy entirely")
    changed = _fp()
    assert changed.host_policy_sha256 != baseline.host_policy_sha256
    assert changed.execution_fingerprint_sha256 != baseline.execution_fingerprint_sha256


def test_changing_config_hash_changes_the_fingerprint():
    baseline = _fp()
    other = _fp(plan=_plan(max_output_tokens=256))
    assert other.config_hash != baseline.config_hash
    assert other.execution_fingerprint_sha256 != baseline.execution_fingerprint_sha256


def test_fingerprint_carries_the_plans_config_hash_verbatim():
    plan = _plan()
    fp = _fp(plan=plan)
    assert fp.config_hash == plan.config_hash
    assert plan.config_hash == "789ca135cc4151aec1f9bed1dad496f45ca0ae9d05149879348125fcd2ba81ae"


def test_resolved_overlay_bundle_is_order_sensitive_but_content_defined():
    overlays = _overlays()
    forward = resolved_overlay_bundle_sha256(overlays)
    reversed_ = resolved_overlay_bundle_sha256(list(reversed(overlays)))
    assert forward != reversed_  # plan order is part of the resolved bundle
    assert resolved_overlay_bundle_sha256(overlays) == forward  # deterministic


def test_resolve_source_commit_sha_prefers_env_override(monkeypatch):
    monkeypatch.setenv("A2AVALIDATOR_SOURCE_COMMIT", "deadbeef" * 5)
    assert resolve_source_commit_sha() == "deadbeef" * 5


def test_resolve_source_commit_sha_reads_git_when_no_override(monkeypatch):
    monkeypatch.delenv("A2AVALIDATOR_SOURCE_COMMIT", raising=False)
    monkeypatch.delenv("SOURCE_COMMIT_SHA", raising=False)
    sha = resolve_source_commit_sha()
    assert len(sha) == 40 and all(c in "0123456789abcdef" for c in sha)


def test_resolve_source_commit_sha_raises_when_indeterminable(monkeypatch, tmp_path):
    monkeypatch.delenv("A2AVALIDATOR_SOURCE_COMMIT", raising=False)
    monkeypatch.delenv("SOURCE_COMMIT_SHA", raising=False)
    import app.runner.execution_fingerprint as ef

    monkeypatch.setattr(ef, "_REPO_ROOT", tmp_path)  # not a git repo
    with pytest.raises(ExecutionFingerprintError):
        resolve_source_commit_sha()


# --- resume: refuse on fingerprint mismatch even when config_hash matches ---


def test_resume_refuses_on_fingerprint_mismatch_with_identical_config_hash(tmp_path):
    from app.runner.pilot_ledger import PilotResumeFingerprintMismatchError, TrialLedger

    plan = _plan()
    ledger = TrialLedger(tmp_path / "run")
    ledger.write_or_verify_plan(plan)
    first = _fp(commit="a" * 40)
    ledger.write_or_verify_execution_fingerprint(first)

    # same plan object -> identical config_hash, but a different source commit
    second = _fp(commit="b" * 40)
    assert second.config_hash == first.config_hash

    reopened = TrialLedger(tmp_path / "run")
    reopened.write_or_verify_plan(plan)  # config_hash check passes
    with pytest.raises(PilotResumeFingerprintMismatchError):
        reopened.write_or_verify_execution_fingerprint(second)

    # identical fingerprint resumes fine
    reopened.write_or_verify_execution_fingerprint(first)


def test_ledger_persists_execution_fingerprint_json(tmp_path):
    from app.models.execution_fingerprint import ExecutionFingerprint
    from app.runner.pilot_ledger import TrialLedger

    ledger = TrialLedger(tmp_path / "run")
    fp = _fp()
    ledger.write_or_verify_execution_fingerprint(fp)
    on_disk = ExecutionFingerprint.model_validate_json(
        (tmp_path / "run" / "execution_fingerprint.json").read_text()
    )
    assert on_disk == fp


# --- existing frozen plan hashes remain unchanged --------------------------


def test_v1_and_v2_plan_config_hashes_are_unchanged_by_this_phase():
    from app.cli.composed_live_pilot import load_frozen_plan

    v1 = load_frozen_plan("gpt-5.6-terra", "v1")
    v2 = load_frozen_plan("gpt-5.6-terra", "v2")
    assert v1.config_hash == "b7df0171cf0e0b9329a48ddd13e5540f872c1ffa5f03967034f28431ab5ba5a2"
    assert v2.config_hash == "789ca135cc4151aec1f9bed1dad496f45ca0ae9d05149879348125fcd2ba81ae"


def test_preflight_prints_all_six_fingerprint_fields():
    import json

    from app.cli.composed_live_pilot import main

    class _Cap:
        def __init__(self):
            self.buf = ""

        def write(self, s):
            self.buf += s

        def flush(self):
            pass

    import contextlib

    cap = _Cap()
    with contextlib.redirect_stdout(cap):
        rc = main(
            ["preflight", "--run-id", "fp-preflight", "--model", "gpt-5.6-terra", "--plan", "v2"]
        )
    assert rc == 0
    out = json.loads(cap.buf)
    for key in (
        "config_hash",
        "source_commit_sha",
        "resolved_overlay_bundle_sha256",
        "host_policy_sha256",
        "tool_schema_sha256",
        "execution_fingerprint_sha256",
    ):
        assert key in out and isinstance(out[key], str) and out[key]
    assert out["config_hash"] == "789ca135cc4151aec1f9bed1dad496f45ca0ae9d05149879348125fcd2ba81ae"


# --- prior live attempts untouched (SHA-256 manifest; skip if absent) ------

_ATTEMPT_MANIFEST = {
    "composed-live-canary-001-gpt56terra-attempt-1/plan.json": (
        "37fc81269967fa9222141ff59b710f1f75b920cc5d80c07b64e390e1cad60963"
    ),
    "composed-live-canary-001-gpt56terra-attempt-2/plan.json": (
        "8b42a5642e0ae793bb94656bb048433eb309ae998d3d064eac9ebe386ea6281d"
    ),
    "composed-live-canary-001-gpt56terra-attempt-2/trials.jsonl": (
        "3dff85aa93bd6b56e744c3554117b78f9147d96ea38f5c394d6087ade418bb42"
    ),
    "composed-live-canary-001-gpt56terra-attempt-2/summary.json": (
        "3b886de3b1fdb1c0b75243e567b0f8ca662b5a0a76ad86144ce1dec826e24bbd"
    ),
    "composed-live-canary-001-gpt56terra-attempt-3/plan.json": (
        "3be278bdef65f3f2ee3dd6a2adf6ced73e39135fd0303cf78ce3c65e4e944407"
    ),
    "composed-live-canary-001-gpt56terra-attempt-3/trials.jsonl": (
        "6d66bdbf06b6264218f85e9c0c175ec80d2bbc0517956eaad85d78b386ec42d6"
    ),
    "composed-live-canary-001-gpt56terra-attempt-3/summary.json": (
        "3b886de3b1fdb1c0b75243e567b0f8ca662b5a0a76ad86144ce1dec826e24bbd"
    ),
}


def test_prior_live_attempts_are_byte_identical_if_present():
    root = Path("reports/experiments")
    present = [rel for rel in _ATTEMPT_MANIFEST if (root / rel).exists()]
    if not present:
        pytest.skip("no prior attempt artifacts on this machine")
    for rel in present:
        digest = hashlib.sha256((root / rel).read_bytes()).hexdigest()
        assert digest == _ATTEMPT_MANIFEST[rel], f"{rel} changed"
