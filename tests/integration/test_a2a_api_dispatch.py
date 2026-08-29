"""API-level coverage for Phase 3B's explicit MCP/A2A suite dispatch in
``POST /runs``. ``RunManager`` itself is completely unmodified -- dispatch
is achieved by routing a request to one of two independent ``RunManager``
instances (see ``app.api.main.AppState``), not a plugin/descriptor
framework and not a code change inside ``RunManager``.
"""

from __future__ import annotations

import time

from fastapi.testclient import TestClient

from app.api.main import app, app_state


def _wait_for_completion(client, run_id, timeout=15.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = client.get(f"/runs/{run_id}").json()["status"]
        if status in ("completed", "failed"):
            return status
        time.sleep(0.02)
    raise AssertionError(f"Run {run_id} did not finish within {timeout}s")


def test_omitted_suite_name_still_selects_mcp_core_suite_unchanged():
    with TestClient(app) as client:
        response = client.post("/runs")
        assert response.status_code == 202
        run_id = response.json()["run_id"]
        assert _wait_for_completion(client, run_id) == "completed"
        report = client.get(f"/runs/{run_id}/report").json()
    assert report["suite_name"] == "agent-interop-core"
    assert report["summary"]["total_tests"] == 29
    assert report["per_test"][0]["protocol"] == "mcp"


def test_explicit_a2a_suite_name_executes_a2a_suite():
    with TestClient(app) as client:
        response = client.post("/runs", json={"suite_name": "agent-interop-a2a"})
        assert response.status_code == 202
        run_id = response.json()["run_id"]
        assert _wait_for_completion(client, run_id) == "completed"
        report = client.get(f"/runs/{run_id}/report").json()
    assert report["suite_name"] == "agent-interop-a2a"
    assert report["suite_version"] == "0.1.0"
    assert report["summary"]["total_tests"] == 8
    assert report["summary"]["passed_tests"] == 5
    assert report["summary"]["failed_tests"] == 3
    assert report["summary"]["a2a_metrics"] == {
        "task_state_correctness": 1.0,
        "artifact_validity": 0.5,
        "cross_agent_injection_resistance": 0.5,
        "remote_error_handling": 1.0,
        "capability_compatibility": 0.0,
    }
    for case_report in report["per_test"]:
        assert case_report["protocol"] == "a2a"
        assert case_report["protocol_version"] == "1.0"
        assert case_report["protocol_binding"] == "http+json"
        assert case_report["turns"] is None
        assert case_report["a2a_interactions"] is not None


def test_unknown_suite_name_rejected_before_queueing_no_orphan_record():
    with TestClient(app) as client:
        before_mcp = len(app_state.run_repository.list_all())
        before_a2a = len(app_state.a2a_run_repository.list_all())
        response = client.post("/runs", json={"suite_name": "does-not-exist"})
        assert response.status_code == 400
        assert "does-not-exist" in response.json()["detail"]
        assert len(app_state.run_repository.list_all()) == before_mcp
        assert len(app_state.a2a_run_repository.list_all()) == before_a2a


def test_a2a_suite_with_openai_adapter_rejected_before_queueing():
    with TestClient(app) as client:
        before = len(app_state.a2a_run_repository.list_all())
        response = client.post(
            "/runs", json={"suite_name": "agent-interop-a2a", "adapter": "openai", "model": "x"}
        )
        assert response.status_code == 400
        assert "deterministic" in response.json()["detail"]
        assert len(app_state.a2a_run_repository.list_all()) == before


def test_a2a_case_ids_validated_against_a2a_suite():
    with TestClient(app) as client:
        response = client.post(
            "/runs",
            json={"suite_name": "agent-interop-a2a", "case_ids": ["not-a-real-a2a-case"]},
        )
        assert response.status_code == 400


def test_mcp_deterministic_behavior_still_unchanged_alongside_a2a_dispatch():
    """Submitting an MCP run and an A2A run against the same running app
    must not cross-contaminate either suite's execution or storage."""
    with TestClient(app) as client:
        mcp_response = client.post("/runs", json={"suite_name": "agent-interop-core"})
        a2a_response = client.post("/runs", json={"suite_name": "agent-interop-a2a"})
        assert mcp_response.status_code == 202
        assert a2a_response.status_code == 202

        mcp_run_id = mcp_response.json()["run_id"]
        a2a_run_id = a2a_response.json()["run_id"]
        assert _wait_for_completion(client, mcp_run_id) == "completed"
        assert _wait_for_completion(client, a2a_run_id) == "completed"

        mcp_report = client.get(f"/runs/{mcp_run_id}/report").json()
        a2a_report = client.get(f"/runs/{a2a_run_id}/report").json()

    assert mcp_report["summary"]["total_tests"] == 29
    assert a2a_report["summary"]["total_tests"] == 8
    assert mcp_report["per_test"][0]["protocol"] == "mcp"
    assert a2a_report["per_test"][0]["protocol"] == "a2a"
