"""Phase 8 offline preflight (docs/phase_8_change_list.md S8).
Mirrors tests/unit/test_phase_6c_preflight.py / the Phase 7A preflight
tests: constructs no provider client, makes no call, is deterministic."""

from __future__ import annotations

from app.cli.phase_8_preflight import run_preflight


def test_preflight_passes_and_makes_no_provider_call():
    report = run_preflight()
    assert report["provider_calls_made"] == 0
    assert report["provisional"] is True
    assert report["headroom_framing"] == "F1"
    assert report["overlay_count"] == 280
    assert report["substudies"]["v8a"]["overlay_count"] == 144
    assert report["substudies"]["v8a2"]["overlay_count"] == 16
    assert report["substudies"]["v8b"]["overlay_count"] == 48
    assert report["substudies"]["v8c"]["overlay_count"] == 48
    assert report["substudies"]["v8d"]["overlay_count"] == 24
    assert len(report["execution_fingerprints"]) == 20  # 4 models x 5 sub-studies
    for fp in report["execution_fingerprints"].values():
        assert len(fp["execution_fingerprint_sha256"]) == 64


def test_all_twenty_fingerprints_distinct():
    report = run_preflight()
    shas = [v["execution_fingerprint_sha256"] for v in report["execution_fingerprints"].values()]
    assert len(set(shas)) == 20


def test_v8d_uses_the_operational_policy_hash_everywhere_else_strict():
    report = run_preflight()
    strict = "32e6ba77c56554de69705f85d547b3e3c48d9d2e2be35d07ed093570d893f2be"
    operational = "2d04974c8db5c8dad624b1a5862d462cea3a345f614ab69ddfcdb0331339a608"
    for key, fp in report["execution_fingerprints"].items():
        expected = operational if key.endswith("/v8d") else strict
        assert fp["host_policy_sha256"] == expected, key


def test_preflight_is_deterministic():
    a = run_preflight()["execution_fingerprints"]
    b = run_preflight()["execution_fingerprints"]
    assert a == b


def test_preflight_rejects_a_generator_drift(monkeypatch):
    import pytest

    import app.cli.phase_8_preflight as pf

    monkeypatch.setattr(pf, "build_plan_doc", lambda substudy: {"tampered": True})
    with pytest.raises(pf.Phase8PreflightError, match="drifted"):
        pf.run_preflight()
