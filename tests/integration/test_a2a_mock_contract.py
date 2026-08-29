"""Validates the mock A2A agent's HTTP+JSON/REST wire shapes directly,
independent of any benchmark case -- proves the mock's request/response
JSON matches the v1.0 binding's shape (route paths without a /v1 prefix,
per the corrected Phase 3B design lock), not just "some homemade objects."

No network call: exercised entirely through ``fastapi.testclient.TestClient``.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.models.a2a import A2ARemoteStep, AgentCard, AgentInterface, TaskState
from mock_servers.a2a_mock import build_a2a_mock_app

CARD = AgentCard(
    name="contract-test-agent",
    supported_interfaces=[
        AgentInterface(
            url="http://mock-a2a-agent", protocol_binding="HTTP_JSON", protocol_version="1.0"
        )
    ],
    default_input_modes=["text/plain"],
    default_output_modes=["text/plain"],
)


def test_agent_card_discovery_path_and_shape():
    app = build_a2a_mock_app(CARD, [], "contract-test-case")
    with TestClient(app) as client:
        response = client.get("/.well-known/agent-card.json")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "contract-test-agent"
    assert body["supported_interfaces"][0]["protocol_binding"] == "HTTP_JSON"
    assert body["supported_interfaces"][0]["protocol_version"] == "1.0"


def test_send_message_route_has_no_v1_prefix():
    script = [A2ARemoteStep(task_state=TaskState.COMPLETED, artifact_text="done")]
    app = build_a2a_mock_app(CARD, script, "contract-test-case")
    with TestClient(app) as client:
        response = client.post(
            "/message:send",
            json={"message": {"message_id": "m1", "role": "ROLE_USER", "parts": [{"text": "hi"}]}},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["status"]["state"] == "TASK_STATE_COMPLETED"
    assert body["artifacts"][0]["parts"][0]["text"] == "done"
    assert "id" in body and "context_id" in body


def test_get_task_route_shape():
    script = [
        A2ARemoteStep(task_state=TaskState.WORKING),
        A2ARemoteStep(task_state=TaskState.COMPLETED),
    ]
    app = build_a2a_mock_app(CARD, script, "contract-test-case")
    with TestClient(app) as client:
        send = client.post(
            "/message:send",
            json={"message": {"message_id": "m1", "role": "ROLE_USER", "parts": [{"text": "hi"}]}},
        )
        task_id = send.json()["id"]
        response = client.get(f"/tasks/{task_id}")
    assert response.status_code == 200
    assert response.json()["status"]["state"] == "TASK_STATE_COMPLETED"


def test_get_task_unknown_id_returns_404():
    app = build_a2a_mock_app(CARD, [], "contract-test-case")
    with TestClient(app) as client:
        response = client.get("/tasks/does-not-exist")
    assert response.status_code == 404
    assert response.json()["detail"]["reason"] == "TASK_NOT_FOUND"


def test_cancel_task_route_shape():
    script = [
        A2ARemoteStep(task_state=TaskState.WORKING),
        A2ARemoteStep(task_state=TaskState.CANCELED),
    ]
    app = build_a2a_mock_app(CARD, script, "contract-test-case")
    with TestClient(app) as client:
        send = client.post(
            "/message:send",
            json={"message": {"message_id": "m1", "role": "ROLE_USER", "parts": [{"text": "hi"}]}},
        )
        task_id = send.json()["id"]
        response = client.post(f"/tasks/{task_id}:cancel")
    assert response.status_code == 200
    assert response.json()["status"]["state"] == "TASK_STATE_CANCELED"


def test_cancel_terminal_task_rejected():
    script = [A2ARemoteStep(task_state=TaskState.COMPLETED, artifact_text="done")]
    app = build_a2a_mock_app(CARD, script, "contract-test-case")
    with TestClient(app) as client:
        send = client.post(
            "/message:send",
            json={"message": {"message_id": "m1", "role": "ROLE_USER", "parts": [{"text": "hi"}]}},
        )
        task_id = send.json()["id"]
        response = client.post(f"/tasks/{task_id}:cancel")
    assert response.status_code == 409
    assert response.json()["detail"]["reason"] == "TASK_NOT_CANCELABLE"


def test_unsupported_content_type_rejected_with_415():
    app = build_a2a_mock_app(CARD, [], "contract-test-case")
    with TestClient(app) as client:
        response = client.post(
            "/message:send",
            json={
                "message": {
                    "message_id": "m1",
                    "role": "ROLE_USER",
                    "parts": [{"content_type": "image/png", "text": "a diagram"}],
                }
            },
        )
    assert response.status_code == 415
    detail = response.json()["detail"]
    assert detail["reason"] == "CONTENT_TYPE_NOT_SUPPORTED"
    assert detail["unsupported_content_type"] == "image/png"


def test_no_outbound_network_used():
    """The mock is exercised purely in-process; TestClient never opens a socket."""
    app = build_a2a_mock_app(
        CARD, [A2ARemoteStep(task_state=TaskState.COMPLETED)], "contract-test-case"
    )
    with TestClient(app, base_url="http://testserver") as client:
        response = client.post(
            "/message:send",
            json={"message": {"message_id": "m1", "role": "ROLE_USER", "parts": [{"text": "hi"}]}},
        )
    assert response.status_code == 200
