import pytest
from fastapi.testclient import TestClient

from app.api.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


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


def test_run_lifecycle_produces_json_report(client):
    create_response = client.post("/runs")
    assert create_response.status_code == 200
    run_id = create_response.json()["run_id"]
    assert create_response.json()["status"] == "completed"

    get_response = client.get(f"/runs/{run_id}")
    assert get_response.status_code == 200
    assert get_response.json()["run_id"] == run_id

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
