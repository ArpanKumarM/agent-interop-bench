"""Phase 6C: complete offline preflight for all four models. No client is
constructed, no API key is required, zero provider calls are made.
"""

from __future__ import annotations

import socket

import pytest

from app.cli.composed_live_pilot import load_frozen_plan, preflight_report

_PANEL = ("gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna", "claude-sonnet-5")


@pytest.fixture(autouse=True)
def _no_sockets():
    def boom(self, address):
        raise AssertionError(f"preflight attempted a socket to {address}")

    original = socket.socket.connect
    socket.socket.connect = boom
    try:
        yield
    finally:
        socket.socket.connect = original


@pytest.fixture(autouse=True)
def _no_api_keys(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


@pytest.mark.parametrize("model", _PANEL)
def test_preflight_runs_offline_for_every_model(model):
    plan = load_frozen_plan(model, "v4")
    report = preflight_report(plan, run_id=f"phase6c-preflight-{model}")
    assert report["model"] == model
    assert report["provider_calls_made"] == 0
    assert report["fingerprint_version"] == "v2"
    assert report["provider_config_sha256"] and len(report["provider_config_sha256"]) == 64
    assert report["execution_fingerprint_sha256"]
    assert report["blocked_schedule"]["trials_in_schedule"] == 160
    # 160 trials * 1 decision, capped at max_total_decisions 160
    assert report["estimated_max_provider_calls"] == 160
    assert len(report["overlays"]) == 40


def test_preflight_reports_the_right_provider_per_model():
    for model in ("gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna"):
        r = preflight_report(load_frozen_plan(model, "v4"), run_id="x")
        assert r["provider"] == "openai"
        assert r["provider_api_surface"] == "openai.responses"
        assert r["provider_request_config"]["max_output_tokens"] == 512
    r = preflight_report(load_frozen_plan("claude-sonnet-5", "v4"), run_id="x")
    assert r["provider"] == "anthropic"
    assert r["provider_api_surface"] == "anthropic.messages"
    assert r["provider_request_config"]["max_tokens"] == 2048
    assert r["provider_request_config"]["effort_mode"] == {"output_config": {"effort": "low"}}
    assert r["provider_request_config"]["thinking"] == {"type": "adaptive", "display": "omitted"}


def test_total_projected_provider_calls_across_the_panel_is_640():
    total = 0
    for model in _PANEL:
        r = preflight_report(load_frozen_plan(model, "v4"), run_id="x")
        total += r["estimated_max_provider_calls"]
    assert total == 640


def test_the_three_existing_v4_schedule_hashes_are_unchanged_in_preflight():
    frozen = {
        "gpt-5.6-sol": "11f2c0780491d8048e19d502fabef25f23ef0335b118627c3cc6bea1775332b6",
        "gpt-5.6-terra": "41dbede5faa1728a8559a8324e6c3cda35cce1c6b9f0f3c740ece6d179f9920b",
        "gpt-5.6-luna": "c653e2bf8b3f2ba320dd754d12f755c2705d9ef988e8a9a469e812eaa4e6a83c",
    }
    for model, expected in frozen.items():
        r = preflight_report(load_frozen_plan(model, "v4"), run_id="x")
        assert r["schedule_sha256"] == expected


def test_preflight_does_not_require_any_api_key():
    # both env vars are deleted by the autouse fixture; this must still work
    r = preflight_report(load_frozen_plan("claude-sonnet-5", "v4"), run_id="x")
    assert r["anthropic_api_key_present"] is False
    assert r["openai_api_key_present"] is False
    assert r["provider_calls_made"] == 0
