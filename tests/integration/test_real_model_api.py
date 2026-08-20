"""API-level tests for Phase 2C real-model run submission: cost-safety
preconditions (feature flag, SDK availability, credential), request
validation before queueing, and confirmation that a deterministic run never
constructs a provider client or makes any network call to a provider.

No test in this file requires OPENAI_API_KEY or the `openai` package to be
installed, and none of them depend on whether the optional extra happens to
be installed in the environment the suite runs in: SDK availability is
injected via the `openai_sdk_available()` seam (both the "absent" and
"present" paths are tested explicitly), and every full happy-path test
injects a fake adapter factory so no real provider is ever touched even
when "enabled". This file's results must be identical whether or not
`openai` is actually installed.
"""

from __future__ import annotations

import dataclasses
import json
import logging
import time

import pytest
from fastapi.testclient import TestClient

import app.api.main as main_module
from app.api.main import app, app_state
from app.models.execution import ToolCallDecision
from app.models.provenance import ModelRunProvenance


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _settings_with(**overrides):
    return dataclasses.replace(main_module.settings, **overrides)


def _wait_for_status(client, run_id, target_statuses, timeout=15.0, poll_interval=0.05):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/runs/{run_id}")
        assert response.status_code == 200
        body = response.json()
        if body["status"] in target_statuses:
            return body
        time.sleep(poll_interval)
    raise AssertionError(f"Run {run_id} did not reach {target_statuses} within {timeout}s")


class FakeRealAdapter:
    """A fake real-model adapter injected directly as RunManager's factory
    result — never touches the real openai package or any network."""

    def __init__(self, model: str):
        self.model = model
        self.provenance = ModelRunProvenance(
            adapter_type="fake",
            provider="fake",
            requested_model=model,
            baseline_policy_version="real-model-baseline-v1",
            baseline_policy_sha256="0" * 64,
            tool_schema_sha256="",
            configured_timeout_seconds=1.0,
            configured_max_retries=0,
            configured_max_output_tokens=1,
        )

    def bind_case(self, case_id: str) -> None:
        pass

    async def decide(self, prompt, available_tools, history):
        return ToolCallDecision(tool_name=None)


# ---- deterministic default is unaffected (Part M) ----


def test_default_adapter_is_deterministic_when_field_omitted(client):
    response = client.post("/runs")
    assert response.status_code == 202


def test_explicit_deterministic_adapter_still_works(client):
    response = client.post("/runs", json={"adapter": "deterministic"})
    assert response.status_code == 202


def test_deterministic_run_never_invokes_real_model_adapter_factory_even_if_configured(
    client, monkeypatch
):
    """The strongest available proof at the API layer: even with a
    real-model factory installed and ready, a deterministic submission must
    never call it — confirming no provider SDK client is ever constructed
    for the default path."""

    def exploding_factory(request):
        raise AssertionError(
            "real_model_adapter_factory must not be invoked for a deterministic run"
        )

    monkeypatch.setattr(app_state.run_manager, "_real_model_adapter_factory", exploding_factory)

    response = client.post("/runs")
    assert response.status_code == 202
    final = _wait_for_status(client, response.json()["run_id"], {"completed", "failed"})
    assert final["status"] == "completed"


def test_deterministic_run_opens_no_outbound_network_socket(client, monkeypatch):
    """Network-spy proof for Part M: a deterministic run must make zero
    outbound network connections. The mock MCP server communicates over
    local stdio pipes (not sockets), so blocking socket.socket.connect
    entirely during the run proves no HTTP/TCP call — to OpenAI or anyone
    else — occurred."""
    import socket

    def exploding_connect(self, address):
        raise AssertionError(
            f"deterministic run attempted an outbound socket connection to {address}"
        )

    monkeypatch.setattr(socket.socket, "connect", exploding_connect)

    response = client.post("/runs")
    assert response.status_code == 202
    final = _wait_for_status(client, response.json()["run_id"], {"completed", "failed"})
    assert final["status"] == "completed"


def test_deterministic_report_has_no_model_provenance(client):
    create = client.post("/runs")
    final = _wait_for_status(client, create.json()["run_id"], {"completed", "failed"})
    assert final["status"] == "completed"
    report = client.get(f"/runs/{create.json()['run_id']}/report").json()
    assert report["model_provenance"] is None


# ---- cost-safety preconditions (Part H / L) ----


def test_openai_adapter_disabled_by_default_returns_503(client):
    response = client.post("/runs", json={"adapter": "openai", "model": "gpt-test"})
    assert response.status_code == 503
    assert "disabled" in response.json()["detail"].lower()
    assert response.json()["detail"] != ""


def test_openai_adapter_enabled_but_sdk_not_installed_returns_503(client, monkeypatch):
    """Uses the injectable openai_sdk_available() seam rather than relying on
    whether the optional extra happens to be installed in this environment —
    this test must pass identically whether or not `openai` is actually
    installed (see Part 5 of the Phase 2C hardening audit)."""
    monkeypatch.setattr(main_module, "settings", _settings_with(enable_real_model_runs=True))
    monkeypatch.setattr(main_module, "openai_sdk_available", lambda: False)

    response = client.post("/runs", json={"adapter": "openai", "model": "gpt-test"})
    assert response.status_code == 503
    assert "openai" in response.json()["detail"].lower()
    assert "install" in response.json()["detail"].lower()


def test_openai_adapter_enabled_and_sdk_available_passes_that_precondition(client, monkeypatch):
    """The mirror-image case: with the seam reporting the SDK as available
    (regardless of whether it truly is in this environment), the request
    proceeds past that specific precondition — proven by reaching a 202,
    not a 503 mentioning the SDK."""
    monkeypatch.setattr(main_module, "settings", _settings_with(enable_real_model_runs=True))
    monkeypatch.setattr(main_module, "openai_sdk_available", lambda: True)
    monkeypatch.setattr(main_module, "real_model_api_key_configured", lambda: True)
    monkeypatch.setattr(
        app_state.run_manager, "_real_model_adapter_factory", lambda r: FakeRealAdapter(r.model)
    )

    response = client.post(
        "/runs",
        json={"adapter": "openai", "model": "gpt-test", "case_ids": ["correct-001-search-issues"]},
    )
    assert response.status_code == 202


def test_openai_adapter_missing_api_key_returns_503(client, monkeypatch):
    monkeypatch.setattr(main_module, "settings", _settings_with(enable_real_model_runs=True))
    monkeypatch.setattr(main_module, "openai_sdk_available", lambda: True)
    monkeypatch.setattr(main_module, "real_model_api_key_configured", lambda: False)

    response = client.post("/runs", json={"adapter": "openai", "model": "gpt-test"})
    assert response.status_code == 503
    assert "OPENAI_API_KEY" in response.json()["detail"]


def test_503_detail_never_reveals_key_value_only_presence(client, monkeypatch):
    monkeypatch.setattr(main_module, "settings", _settings_with(enable_real_model_runs=True))
    monkeypatch.setattr(main_module, "openai_sdk_available", lambda: True)
    monkeypatch.setattr(main_module, "real_model_api_key_configured", lambda: False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-shouldneverappearinaresponse1234567890")

    response = client.post("/runs", json={"adapter": "openai", "model": "gpt-test"})
    assert "sk-shouldneverappearinaresponse1234567890" not in response.text


def test_openai_adapter_without_model_rejected_with_400_when_enabled(client, monkeypatch):
    monkeypatch.setattr(main_module, "settings", _settings_with(enable_real_model_runs=True))
    monkeypatch.setattr(main_module, "openai_sdk_available", lambda: True)
    monkeypatch.setattr(main_module, "real_model_api_key_configured", lambda: True)
    monkeypatch.setattr(
        app_state.run_manager, "_real_model_adapter_factory", lambda r: FakeRealAdapter(r.model)
    )

    response = client.post("/runs", json={"adapter": "openai"})
    assert response.status_code == 400
    assert "model" in response.json()["detail"].lower()


def test_openai_adapter_unknown_case_ids_rejected_with_400_when_enabled(client, monkeypatch):
    monkeypatch.setattr(main_module, "settings", _settings_with(enable_real_model_runs=True))
    monkeypatch.setattr(main_module, "openai_sdk_available", lambda: True)
    monkeypatch.setattr(main_module, "real_model_api_key_configured", lambda: True)
    monkeypatch.setattr(
        app_state.run_manager, "_real_model_adapter_factory", lambda r: FakeRealAdapter(r.model)
    )

    response = client.post(
        "/runs",
        json={"adapter": "openai", "model": "gpt-test", "case_ids": ["not-a-real-case-id"]},
    )
    assert response.status_code == 400
    assert "not-a-real-case-id" in response.json()["detail"]


def test_openai_adapter_case_count_over_limit_rejected_with_400(client, monkeypatch):
    monkeypatch.setattr(main_module, "settings", _settings_with(enable_real_model_runs=True))
    monkeypatch.setattr(main_module, "openai_sdk_available", lambda: True)
    monkeypatch.setattr(main_module, "real_model_api_key_configured", lambda: True)
    monkeypatch.setattr(
        app_state.run_manager, "_real_model_adapter_factory", lambda r: FakeRealAdapter(r.model)
    )

    all_case_ids = [c["id"] for c in client.get("/benchmarks").json()]
    assert len(all_case_ids) > main_module.settings.real_model_max_cases

    response = client.post(
        "/runs", json={"adapter": "openai", "model": "gpt-test"}
    )  # no case_ids -> all
    assert response.status_code == 400
    assert "exceeding" in response.json()["detail"].lower()


def test_invalid_request_does_not_create_an_orphan_run_record(client, monkeypatch):
    monkeypatch.setattr(main_module, "settings", _settings_with(enable_real_model_runs=True))
    monkeypatch.setattr(main_module, "openai_sdk_available", lambda: True)
    monkeypatch.setattr(main_module, "real_model_api_key_configured", lambda: True)
    monkeypatch.setattr(
        app_state.run_manager, "_real_model_adapter_factory", lambda r: FakeRealAdapter(r.model)
    )

    before = len(app_state.run_repository.list_all())
    response = client.post("/runs", json={"adapter": "openai"})  # missing model
    assert response.status_code == 400
    after = len(app_state.run_repository.list_all())
    assert after == before


# ---- full happy path with a fake factory (no real provider ever touched) ----


def test_openai_run_end_to_end_via_fake_factory_carries_provenance(client, monkeypatch):
    monkeypatch.setattr(main_module, "settings", _settings_with(enable_real_model_runs=True))
    monkeypatch.setattr(main_module, "openai_sdk_available", lambda: True)
    monkeypatch.setattr(main_module, "real_model_api_key_configured", lambda: True)
    monkeypatch.setattr(
        app_state.run_manager, "_real_model_adapter_factory", lambda r: FakeRealAdapter(r.model)
    )

    create = client.post(
        "/runs",
        json={
            "adapter": "openai",
            "model": "gpt-test-model",
            "case_ids": ["correct-001-search-issues"],
        },
    )
    assert create.status_code == 202
    run_id = create.json()["run_id"]

    final = _wait_for_status(client, run_id, {"completed", "failed"})
    assert final["status"] == "completed", final

    report = client.get(f"/runs/{run_id}/report").json()
    assert report["summary"]["total_tests"] == 1
    assert report["per_test"][0]["case_id"] == "correct-001-search-issues"
    assert report["model_provenance"] is not None
    assert report["model_provenance"]["requested_model"] == "gpt-test-model"
    assert report["model_provenance"]["provider"] == "fake"


# ---- exception/log sanitization: full-chain regression (Part 6) ----


class HostileResponsesClient:
    """A fake provider client whose exception message contains
    secret-shaped strings that must never leak anywhere. Used with a REAL
    OpenAIResponsesAdapter (not a bypass fake), so this exercises the actual
    production sanitization chain end to end: adapter -> RunManager logging
    -> stored failure metadata -> API response -> serialized report."""

    async def create(self, **kwargs):
        raise RuntimeError(
            "Upstream provider error: sk-TEST-SHOULD-NOT-LEAK / "
            "Authorization: Bearer SECRET-SHOULD-NOT-LEAK"
        )


def _hostile_real_adapter_factory(request):
    from app.runner.openai_adapter import OpenAIResponsesAdapter

    return OpenAIResponsesAdapter(HostileResponsesClient(), model=request.model)


def test_hostile_provider_exception_never_leaks_secret_through_the_full_chain(
    client, monkeypatch, caplog
):
    """Deliberately hostile fake provider exception containing
    'sk-TEST-SHOULD-NOT-LEAK' and 'Authorization: Bearer SECRET-SHOULD-NOT-LEAK'.
    Proves neither value appears in: the stored run error (GET /runs/{id}),
    any API response (including the 409 report-not-ready body), captured
    logs, or a serialized report/provenance (none is fabricated since the
    run fails)."""
    monkeypatch.setattr(main_module, "settings", _settings_with(enable_real_model_runs=True))
    monkeypatch.setattr(main_module, "openai_sdk_available", lambda: True)
    monkeypatch.setattr(main_module, "real_model_api_key_configured", lambda: True)
    monkeypatch.setattr(
        app_state.run_manager, "_real_model_adapter_factory", _hostile_real_adapter_factory
    )
    caplog.set_level(logging.DEBUG)

    create = client.post(
        "/runs",
        json={"adapter": "openai", "model": "gpt-test", "case_ids": ["correct-001-search-issues"]},
    )
    assert create.status_code == 202
    run_id = create.json()["run_id"]

    final = _wait_for_status(client, run_id, {"completed", "failed"})
    assert final["status"] == "failed"

    secrets = ["sk-TEST-SHOULD-NOT-LEAK", "SECRET-SHOULD-NOT-LEAK"]

    # 1. Stored run error, surfaced via GET /runs/{id}.
    assert final["error"] is not None
    for secret in secrets:
        assert secret not in json.dumps(final)

    # 2. Every API response touched during this test, including the
    #    documented 409 for a failed run's report.
    report_response = client.get(f"/runs/{run_id}/report")
    assert report_response.status_code == 409
    for secret in secrets:
        assert secret not in report_response.text
        assert secret not in create.text
        assert secret not in json.dumps(client.get(f"/runs/{run_id}").json())

    # 3. Captured logs (this is the specific hardening this test exists
    #    for: `from None` at the adapter boundary must prevent
    #    logger.exception()'s traceback formatting from walking into the
    #    original, unsanitized provider exception).
    for secret in secrets:
        assert secret not in caplog.text

    # 4. No report/provenance was fabricated for the failed run at all.
    assert app_state.run_manager.get(run_id).report is None
