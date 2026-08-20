import asyncio
import threading
import time

import pytest
from fastapi.testclient import TestClient

from app.api.main import app, app_state
from app.models.evaluation import Report, ScoreSummary
from app.runner.run_manager import RunQueueFullError


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _canned_report(run_id: str) -> Report:
    return Report(
        run_id=run_id,
        suite_name="fake-suite-for-tests",
        summary=ScoreSummary(
            total_tests=1,
            passed_tests=1,
            failed_tests=0,
            tool_selection_accuracy=1.0,
            argument_accuracy=1.0,
            recovery_rate=None,
            unsafe_action_rate=None,
            prompt_injection_resistance=None,
            average_latency_ms=1.0,
        ),
        per_test=[],
    )


def _wait_for_status(client, run_id, target_statuses, timeout=10.0, poll_interval=0.02):
    """Bounded poll for a terminal-ish status over real HTTP calls.

    Not used for the core responsiveness/ordering assertions (those use
    threading.Event gates below) — only for waiting out a real subprocess
    run's actual completion, where no in-process synchronization primitive
    is available to the test.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        response = client.get(f"/runs/{run_id}")
        assert response.status_code == 200
        body = response.json()
        if body["status"] in target_statuses:
            return body
        time.sleep(poll_interval)
    raise AssertionError(f"Run {run_id} did not reach {target_statuses} within {timeout}s")


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_list_tools(client):
    response = client.get("/tools")
    assert response.status_code == 200
    names = {t["name"] for t in response.json()}
    assert names == {"search_issues", "get_repository", "create_comment", "calculate_sum"}


def test_list_benchmarks(client):
    response = client.get("/benchmarks")
    assert response.status_code == 200
    assert len(response.json()) >= 15


def test_create_run_returns_202_with_queued_status_and_location_header(client):
    response = client.post("/runs")
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    assert body["run_id"]
    assert body["created_at"] is not None
    assert body["started_at"] is None
    assert body["completed_at"] is None
    assert body["failed_at"] is None
    assert response.headers["location"] == f"/runs/{body['run_id']}"


def test_run_lifecycle_produces_json_report(client):
    create_response = client.post("/runs")
    assert create_response.status_code == 202
    run_id = create_response.json()["run_id"]

    final = _wait_for_status(client, run_id, {"completed", "failed"})
    assert final["status"] == "completed", final
    assert final["created_at"] is not None
    assert final["started_at"] is not None
    assert final["completed_at"] is not None
    assert final["failed_at"] is None
    assert final["error"] is None

    report_response = client.get(f"/runs/{run_id}/report")
    assert report_response.status_code == 200
    report = report_response.json()
    assert report["summary"]["total_tests"] >= 15
    assert len(report["per_test"]) == report["summary"]["total_tests"]


def test_get_unknown_run_returns_404(client):
    response = client.get("/runs/does-not-exist")
    assert response.status_code == 404


def test_get_report_for_unknown_run_returns_404(client):
    response = client.get("/runs/does-not-exist/report")
    assert response.status_code == 404


def test_get_run_for_malformed_run_id_returns_404_not_error(client):
    """A run ID that isn't even a plausible UUID must still 404 cleanly, not 500."""
    response = client.get("/runs/../../etc/passwd")
    assert response.status_code == 404
    response2 = client.get("/runs/' OR 1=1 --")
    assert response2.status_code == 404


def test_report_not_ready_returns_409_and_api_stays_responsive_during_execution(
    client, monkeypatch
):
    """Combines two required Phase 2B properties in one deterministic test:

    1. GET /runs/{id}/report on a still-running run returns 409 with
       structured detail, not a fabricated/partial report.
    2. The API remains responsive to other requests (including the run's own
       status endpoint) while that run's execution is still in progress —
       proving POST /runs did not block the event loop or the request cycle.

    Uses a threading.Event gate (the TestClient runs the app's event loop in
    a separate thread) instead of any sleep-based timing assumption.
    """
    gate = threading.Event()
    started = threading.Event()

    async def gated_execute(run_id, suite, transport):
        started.set()
        await asyncio.to_thread(gate.wait)
        return _canned_report(run_id)

    monkeypatch.setattr(app_state.run_manager, "_execute_fn", gated_execute)

    create_response = client.post("/runs")
    assert create_response.status_code == 202
    run_id = create_response.json()["run_id"]

    # Deterministically wait until the worker has actually picked this run up
    # and is blocked inside gated_execute — not a fixed sleep.
    assert started.wait(timeout=5.0), "worker never started executing the queued run"

    status_response = client.get(f"/runs/{run_id}")
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "running"
    assert status_response.json()["started_at"] is not None

    report_response = client.get(f"/runs/{run_id}/report")
    assert report_response.status_code == 409
    detail = report_response.json()["detail"]
    assert detail["run_id"] == run_id
    assert detail["status"] == "running"

    # The API must still serve unrelated requests too.
    health_response = client.get("/health")
    assert health_response.status_code == 200

    gate.set()
    final = _wait_for_status(client, run_id, {"completed", "failed"})
    assert final["status"] == "completed"

    report_response = client.get(f"/runs/{run_id}/report")
    assert report_response.status_code == 200


def test_create_run_returns_429_when_queue_is_full(client, monkeypatch):
    def full_submit(request=None):
        raise RunQueueFullError("Run queue is full (10 pending); try again shortly.")

    monkeypatch.setattr(app_state.run_manager, "submit", full_submit)

    response = client.post("/runs")
    assert response.status_code == 429


def test_queue_full_returns_429_at_real_configured_capacity_with_no_orphan_state(
    client, monkeypatch
):
    """Fills the manager's REAL configured capacity (worker slots + queue
    bound) with gated, never-finishing runs, then proves the next submission
    is rejected with 429 and leaves no trace: the rejected submission gets no
    run_id, and every previously-accepted run is untouched."""
    from app.core.config import settings

    gate = threading.Event()

    async def gated_execute(run_id, suite, transport):
        await asyncio.to_thread(gate.wait)
        return _canned_report(run_id)

    monkeypatch.setattr(app_state.run_manager, "_execute_fn", gated_execute)

    total_capacity = settings.run_worker_count + settings.run_queue_maxsize
    accepted_ids = []
    for _ in range(total_capacity):
        response = client.post("/runs")
        assert response.status_code == 202
        accepted_ids.append(response.json()["run_id"])

    # Every worker slot and every queue slot is now occupied by a gated
    # (never-finishing) run — the next submission must be rejected.
    overflow_response = client.post("/runs")
    assert overflow_response.status_code == 429

    # No orphan state: every previously-accepted run is untouched and still
    # exactly where it was (queued or running, not somehow lost or altered).
    for run_id in accepted_ids:
        status_response = client.get(f"/runs/{run_id}")
        assert status_response.status_code == 200
        assert status_response.json()["status"] in ("queued", "running")

    gate.set()
    for run_id in accepted_ids:
        final = _wait_for_status(client, run_id, {"completed", "failed"})
        assert final["status"] == "completed"


def test_create_run_accepts_matching_suite_name(client):
    response = client.post("/runs", json={"suite_name": "agent-interop-core"})
    assert response.status_code == 202
    assert response.json()["status"] == "queued"


def test_create_run_rejects_unknown_suite_name_before_queueing(client):
    before_count = len(app_state.run_repository.list_all())

    response = client.post("/runs", json={"suite_name": "some-other-suite-that-does-not-exist"})

    assert response.status_code == 400
    assert "some-other-suite-that-does-not-exist" in response.json()["detail"]

    # Nothing was queued: no new run record exists, so the caller can never
    # be misled into thinking a different (or any) suite ran.
    after_count = len(app_state.run_repository.list_all())
    assert after_count == before_count


def test_execution_failure_becomes_failed_no_fabricated_report_worker_continues(
    client, monkeypatch
):
    calls = []

    async def flaky_execute(run_id, suite, transport):
        calls.append(run_id)
        if len(calls) == 1:
            raise RuntimeError("boom: simulated benchmark failure")
        return _canned_report(run_id)

    monkeypatch.setattr(app_state.run_manager, "_execute_fn", flaky_execute)

    first = client.post("/runs")
    assert first.status_code == 202
    first_id = first.json()["run_id"]

    first_final = _wait_for_status(client, first_id, {"completed", "failed"})
    assert first_final["status"] == "failed"
    assert first_final["error"] is not None
    assert "RuntimeError" in first_final["error"]
    assert "boom" in first_final["error"]
    assert first_final["completed_at"] is None
    assert first_final["failed_at"] is not None
    # No Python traceback or internal detail leaked, just type + message.
    assert "Traceback" not in first_final["error"]

    report_response = client.get(f"/runs/{first_id}/report")
    assert report_response.status_code == 409
    assert report_response.json()["detail"]["status"] == "failed"

    # The worker must still be alive and able to process a subsequent run.
    second = client.post("/runs")
    assert second.status_code == 202
    second_id = second.json()["run_id"]
    second_final = _wait_for_status(client, second_id, {"completed", "failed"})
    assert second_final["status"] == "completed"

    second_report = client.get(f"/runs/{second_id}/report")
    assert second_report.status_code == 200


def test_concurrent_runs_are_isolated(client):
    """Two runs submitted back to back get distinct IDs, distinct reports, and
    neither's status/report leaks into the other's record."""
    first = client.post("/runs")
    second = client.post("/runs")
    assert first.status_code == 202
    assert second.status_code == 202
    first_id = first.json()["run_id"]
    second_id = second.json()["run_id"]
    assert first_id != second_id

    first_final = _wait_for_status(client, first_id, {"completed", "failed"})
    second_final = _wait_for_status(client, second_id, {"completed", "failed"})
    assert first_final["status"] == "completed"
    assert second_final["status"] == "completed"

    first_report = client.get(f"/runs/{first_id}/report").json()
    second_report = client.get(f"/runs/{second_id}/report").json()
    assert first_report["run_id"] == first_id
    assert second_report["run_id"] == second_id
    assert first_report["run_id"] != second_report["run_id"]
