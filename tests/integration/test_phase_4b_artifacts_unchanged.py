"""Phase 6B must not touch Phase 4B scientific history. These SHA-256 pins
fail loudly if any frozen Phase 4B raw artifact, the frozen v3 stimuli/plan/
schedule, the outcome audit, or the published result tables/figures change.
See docs/phase_4b_errata.md -- corrections go forward at HEAD, never by
rewriting these bytes.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

_RUNS = "reports/experiments"
_ASSETS = "docs/assets/phase_4b"
_BENCH = "benchmarks/composed"

# (relative path, expected sha256)
_FROZEN_SHA256: list[tuple[str, str]] = [
    (
        f"{_RUNS}/composed-live-canary-003-sol-attempt-1/trials.jsonl",
        "13c776e7da586c540247d9630a825cb5788010ee06743150ab4e05ad4b626dec",
    ),
    (
        f"{_RUNS}/composed-live-canary-003-sol-attempt-1/summary.json",
        "d2bf407a14c15e5df2cd3b31daa55b74f447303bd0118a6dd030bf7a30c11310",
    ),
    (
        f"{_RUNS}/composed-live-canary-003-sol-attempt-1/execution_fingerprint.json",
        "5b2c854ba07679760c7cb67eae943f5a4f360f28ab1b1ea2a16709a41ea2b0b9",
    ),
    (
        f"{_RUNS}/composed-live-canary-003-sol-attempt-1/schedule.json",
        "172d8db101d40b4026db85170b93179fc20a76483616e736b254191074de9dd2",
    ),
    (
        f"{_RUNS}/composed-live-canary-003-sol-attempt-1/plan.json",
        "fb9693083d9142b0199ba0e4da294a481340efa55781348655a7065ddfd9e98b",
    ),
    (
        f"{_RUNS}/composed-live-canary-003-terra-attempt-1/trials.jsonl",
        "09794450135e1c868bf59752f815509a27c80b783fb55acd703199ace6acc325",
    ),
    (
        f"{_RUNS}/composed-live-canary-003-terra-attempt-1/summary.json",
        "c77e1a7ca345399a83e24703250549eff8d17260179ce4e3e6a393cc51322455",
    ),
    (
        f"{_RUNS}/composed-live-canary-003-terra-attempt-1/execution_fingerprint.json",
        "3245e93f315e323820586e20b2adef1a7d3f714b89f203509d57d1031d05926a",
    ),
    (
        f"{_RUNS}/composed-live-canary-003-luna-attempt-1/trials.jsonl",
        "f971886816331ebbf7c9431a9ff868ccf48004d6ce9f9b64ce8e4e465657e150",
    ),
    (
        f"{_RUNS}/composed-live-canary-003-luna-attempt-1/summary.json",
        "49ed61db0c9f51f2a7ef9962ec4ef8d12ae056e428a660ee0fed96985102a1e2",
    ),
    (
        f"{_RUNS}/composed-live-canary-003-luna-attempt-1/execution_fingerprint.json",
        "03c942e13022bc2a96b121b626d265aa92de3bea87dbe692e631f85601cfa91c",
    ),
    (
        f"{_RUNS}/phase_4b_outcome_audit.json",
        "84db273386acd82710f63947a8c3787ee7d70b3f79b4c9492b5dafd42d591de4",
    ),
    (
        f"{_BENCH}/live_overlays.yaml",
        "85427c6e4c30dd3c6471bef92f1fc5b80616fa48931fcfe8e71966bdba198460",
    ),
    (
        f"{_BENCH}/live_canary_plan_v3.json",
        "c23dcc4f3a2dcc57db5c8ad739e96309aa113b83cd3795965a8edb62ce9eba68",
    ),
    (
        f"{_BENCH}/live_canary_v3_schedule.json",
        "751fd917e68bc05cdc60acb9903ca3e7ef34deb1c756f374273046a2df6286f2",
    ),
    (
        f"{_ASSETS}/table_actual_mutating_requests.csv",
        "8b4e543b33ba82ddf5048cd4ae2b3a40e0985a48360bf9d3a513aed073340042",
    ),
    (
        f"{_ASSETS}/table_containment.csv",
        "2fe8eb5b031e0edbd7e1b74fb664684f57d02e19671a1dca4c0763c79d420eb0",
    ),
    (
        f"{_ASSETS}/table_experimental_integrity.csv",
        "ca85ab97d7f23c022825c1a2a051c34794e8c77733d9ff73cb5f7a780872a6a4",
    ),
    (
        f"{_ASSETS}/table_sensitive_relay_and_egress.csv",
        "a878bfbde63098e239e92160d23d27c29e1dd950f9e7b9f9b39d3209d7865d26",
    ),
    (
        f"{_ASSETS}/table_wrapper_tool_selection_diagnostic.csv",
        "f9605a57a64a611e67333bb8d95f76065fa95796985267b4d63af6807aedc427",
    ),
    (
        f"{_ASSETS}/fig_actual_mutating_rate_adversarial_vs_benign.svg",
        "18aa753294e4760612ebffc117418d22b8373b7bcd5ea2f4df6529442f97aceb",
    ),
    (
        f"{_ASSETS}/fig_containment_blocked_vs_executed.svg",
        "effff17a8e3da2f25153f147ad6e48ef1831d4b407073632ab52b54659067eb7",
    ),
    (
        f"{_ASSETS}/fig_relay_rate_confidential_vs_public.svg",
        "b8fa5697e9a7410e1af3c6bbdec562ed07483e7772c2cd530b609bf4a7bcd493",
    ),
    (
        f"{_ASSETS}/MANIFEST.json",
        "a54b3b02307d8fb4ceb0d2e9735f21ec8116f0a7a06dbc04d4d131c7c1d63b0b",
    ),
]


@pytest.mark.parametrize("relpath,expected", _FROZEN_SHA256, ids=[p for p, _ in _FROZEN_SHA256])
def test_phase_4b_artifact_byte_identical(relpath: str, expected: str):
    path = Path(relpath)
    assert path.exists(), f"frozen Phase 4B artifact missing: {relpath}"
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    assert actual == expected, f"{relpath} changed! Phase 4B history must stay byte-identical."
