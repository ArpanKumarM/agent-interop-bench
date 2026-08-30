"""Validates the mock A2A agent's HTTP+JSON/REST wire shapes directly,
independent of any benchmark case -- proves the mock's request/response
JSON matches the v1.0 binding's shape: route paths without a /v1 prefix
(per the corrected Phase 3B design lock), and camelCase field names per the
v1.0 specification's JSON Field Naming Convention (Section 5.5) -- a real
spec non-conformance found and fixed in Phase 3C.1 (Phase 3B shipped these
fields serialized under their raw snake_case Python names instead).

No network call: exercised entirely through ``fastapi.testclient.TestClient``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.models.a2a import A2ARemoteStep, AgentCard, AgentInterface, Message, Task, TaskState
from mock_servers.a2a_mock import build_a2a_mock_app

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "a2a"

# Every snake_case name a _WireModel field could have been emitted under
# before Phase 3C.1 -- must never appear as a JSON key on the wire again.
FORBIDDEN_SNAKE_CASE_KEYS = {
    "message_id",
    "task_id",
    "context_id",
    "content_type",
    "supported_interfaces",
    "default_input_modes",
    "default_output_modes",
    "protocol_binding",
    "protocol_version",
}

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


def _all_keys(obj) -> set[str]:
    """Recursively collect every dict key appearing anywhere in a JSON value."""
    keys: set[str] = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            keys.add(k)
            keys |= _all_keys(v)
    elif isinstance(obj, list):
        for item in obj:
            keys |= _all_keys(item)
    return keys


def _load_fixture(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text())


def _send(client: TestClient, message_id: str = "m1", content: str = "hi") -> dict:
    response = client.post(
        "/message:send",
        json={
            "message": {"messageId": message_id, "role": "ROLE_USER", "parts": [{"text": content}]}
        },
    )
    return response.json()


def test_agent_card_discovery_path_and_shape_is_camel_case():
    app = build_a2a_mock_app(CARD, [], "contract-test-case")
    with TestClient(app) as client:
        response = client.get("/.well-known/agent-card.json")
    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "contract-test-agent"
    assert body["supportedInterfaces"][0]["protocolBinding"] == "HTTP_JSON"
    assert body["supportedInterfaces"][0]["protocolVersion"] == "1.0"
    assert body["defaultInputModes"] == ["text/plain"]
    assert body["defaultOutputModes"] == ["text/plain"]
    assert _all_keys(body).isdisjoint(FORBIDDEN_SNAKE_CASE_KEYS)


def test_agent_card_matches_golden_fixture_shape():
    """The mock's actual AgentCard response uses exactly the same key set as
    a hand-transcribed golden fixture built from the v1.0 spec's own field
    tables -- proof this isn't just internally self-consistent, it matches
    the officially documented wire shape."""
    app = build_a2a_mock_app(CARD, [], "contract-test-case")
    with TestClient(app) as client:
        response = client.get("/.well-known/agent-card.json")
    golden = _load_fixture("agent_card.json")
    assert set(response.json().keys()) == set(golden.keys())
    assert set(response.json()["supportedInterfaces"][0].keys()) == set(
        golden["supportedInterfaces"][0].keys()
    )


def test_send_message_request_golden_fixture_round_trips():
    golden = _load_fixture("send_message_request.json")
    parsed = Message.model_validate(golden["message"])
    assert parsed.message_id == golden["message"]["messageId"]
    assert parsed.parts[0].content_type == golden["message"]["parts"][0]["contentType"]
    re_emitted = parsed.model_dump(by_alias=True)
    assert re_emitted["messageId"] == golden["message"]["messageId"]
    assert re_emitted["parts"][0]["contentType"] == golden["message"]["parts"][0]["contentType"]
    assert _all_keys(re_emitted).isdisjoint(FORBIDDEN_SNAKE_CASE_KEYS)


def test_task_completed_golden_fixture_round_trips():
    golden = _load_fixture("task_completed.json")
    parsed = Task.model_validate(golden)
    assert parsed.id == golden["id"]
    assert parsed.context_id == golden["contextId"]
    assert parsed.status.state == TaskState.COMPLETED
    assert parsed.artifacts[0].parts[0].text == "Deployment status: healthy"
    assert parsed.history[0].message_id == golden["history"][0]["messageId"]

    re_emitted = parsed.model_dump(by_alias=True)
    assert re_emitted == golden
    assert _all_keys(re_emitted).isdisjoint(FORBIDDEN_SNAKE_CASE_KEYS)


def test_send_message_route_response_is_camel_case_with_no_v1_prefix():
    script = [A2ARemoteStep(task_state=TaskState.COMPLETED, artifact_text="done")]
    app = build_a2a_mock_app(CARD, script, "contract-test-case")
    with TestClient(app) as client:
        body = _send(client)
    assert body["status"]["state"] == "TASK_STATE_COMPLETED"
    assert body["artifacts"][0]["parts"][0]["contentType"] == "text/plain"
    assert body["artifacts"][0]["parts"][0]["text"] == "done"
    assert "id" in body and "contextId" in body
    assert _all_keys(body).isdisjoint(FORBIDDEN_SNAKE_CASE_KEYS)


def test_send_message_round_trip_preserves_content():
    script = [A2ARemoteStep(task_state=TaskState.WORKING, remote_message_text="ack")]
    app = build_a2a_mock_app(CARD, script, "contract-test-case")
    with TestClient(app) as client:
        body = _send(client, message_id="m1", content="hello there")
    task = Task.model_validate(body)
    assert task.status.state == TaskState.WORKING
    assert task.history[0].parts[0].text == "ack"


def test_get_task_round_trip_is_camel_case():
    script = [
        A2ARemoteStep(task_state=TaskState.WORKING),
        A2ARemoteStep(task_state=TaskState.COMPLETED),
    ]
    app = build_a2a_mock_app(CARD, script, "contract-test-case")
    with TestClient(app) as client:
        send_body = _send(client)
        task_id = send_body["id"]
        response = client.get(f"/tasks/{task_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["status"]["state"] == "TASK_STATE_COMPLETED"
    assert _all_keys(body).isdisjoint(FORBIDDEN_SNAKE_CASE_KEYS)


def test_get_task_unknown_id_returns_404():
    app = build_a2a_mock_app(CARD, [], "contract-test-case")
    with TestClient(app) as client:
        response = client.get("/tasks/does-not-exist")
    assert response.status_code == 404
    assert response.json()["detail"]["reason"] == "TASK_NOT_FOUND"


def test_cancel_task_round_trip_is_camel_case():
    script = [
        A2ARemoteStep(task_state=TaskState.WORKING),
        A2ARemoteStep(task_state=TaskState.CANCELED),
    ]
    app = build_a2a_mock_app(CARD, script, "contract-test-case")
    with TestClient(app) as client:
        send_body = _send(client)
        task_id = send_body["id"]
        response = client.post(f"/tasks/{task_id}:cancel")
    assert response.status_code == 200
    body = response.json()
    assert body["status"]["state"] == "TASK_STATE_CANCELED"
    assert _all_keys(body).isdisjoint(FORBIDDEN_SNAKE_CASE_KEYS)


def test_cancel_terminal_task_rejected():
    script = [A2ARemoteStep(task_state=TaskState.COMPLETED, artifact_text="done")]
    app = build_a2a_mock_app(CARD, script, "contract-test-case")
    with TestClient(app) as client:
        send_body = _send(client)
        task_id = send_body["id"]
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
                    "messageId": "m1",
                    "role": "ROLE_USER",
                    "parts": [{"contentType": "image/png", "text": "a diagram"}],
                }
            },
        )
    assert response.status_code == 415
    detail = response.json()["detail"]
    assert detail["reason"] == "CONTENT_TYPE_NOT_SUPPORTED"
    assert detail["unsupported_content_type"] == "image/png"


def test_camel_case_message_id_accepted():
    app = build_a2a_mock_app(
        CARD, [A2ARemoteStep(task_state=TaskState.COMPLETED)], "contract-test-case"
    )
    with TestClient(app) as client:
        response = client.post(
            "/message:send",
            json={"message": {"messageId": "m1", "role": "ROLE_USER", "parts": [{"text": "hi"}]}},
        )
    assert response.status_code == 200


def test_snake_case_message_id_rejected():
    app = build_a2a_mock_app(
        CARD, [A2ARemoteStep(task_state=TaskState.COMPLETED)], "contract-test-case"
    )
    with TestClient(app) as client:
        response = client.post(
            "/message:send",
            json={"message": {"message_id": "m1", "role": "ROLE_USER", "parts": [{"text": "hi"}]}},
        )
    assert response.status_code == 400
    assert response.json()["detail"]["reason"] == "INVALID_FIELD_CASING"


def test_camel_case_context_id_accepted():
    app = build_a2a_mock_app(
        CARD, [A2ARemoteStep(task_state=TaskState.COMPLETED)], "contract-test-case"
    )
    with TestClient(app) as client:
        response = client.post(
            "/message:send",
            json={
                "message": {
                    "messageId": "m1",
                    "role": "ROLE_USER",
                    "parts": [{"text": "hi"}],
                    "contextId": "c1",
                }
            },
        )
    assert response.status_code == 200


def test_snake_case_context_id_rejected():
    app = build_a2a_mock_app(
        CARD, [A2ARemoteStep(task_state=TaskState.COMPLETED)], "contract-test-case"
    )
    with TestClient(app) as client:
        response = client.post(
            "/message:send",
            json={
                "message": {
                    "messageId": "m1",
                    "role": "ROLE_USER",
                    "parts": [{"text": "hi"}],
                    "context_id": "c1",
                }
            },
        )
    assert response.status_code == 400
    assert response.json()["detail"]["reason"] == "INVALID_FIELD_CASING"


def test_camel_case_task_id_accepted():
    app = build_a2a_mock_app(
        CARD, [A2ARemoteStep(task_state=TaskState.COMPLETED)], "contract-test-case"
    )
    with TestClient(app) as client:
        response = client.post(
            "/message:send",
            json={
                "message": {
                    "messageId": "m1",
                    "role": "ROLE_USER",
                    "parts": [{"text": "hi"}],
                    "taskId": None,
                }
            },
        )
    assert response.status_code == 200


def test_snake_case_task_id_rejected():
    app = build_a2a_mock_app(
        CARD, [A2ARemoteStep(task_state=TaskState.COMPLETED)], "contract-test-case"
    )
    with TestClient(app) as client:
        response = client.post(
            "/message:send",
            json={
                "message": {
                    "messageId": "m1",
                    "role": "ROLE_USER",
                    "parts": [{"text": "hi"}],
                    "task_id": None,
                }
            },
        )
    assert response.status_code == 400
    assert response.json()["detail"]["reason"] == "INVALID_FIELD_CASING"


def test_snake_case_content_type_in_nested_part_rejected():
    """The strict guard walks nested structures too -- a snake_case key
    buried inside `parts` must be caught, not just top-level keys."""
    app = build_a2a_mock_app(
        CARD, [A2ARemoteStep(task_state=TaskState.COMPLETED)], "contract-test-case"
    )
    with TestClient(app) as client:
        response = client.post(
            "/message:send",
            json={
                "message": {
                    "messageId": "m1",
                    "role": "ROLE_USER",
                    "parts": [{"content_type": "text/plain", "text": "hi"}],
                }
            },
        )
    assert response.status_code == 400
    assert response.json()["detail"]["reason"] == "INVALID_FIELD_CASING"


def test_reject_snake_case_wire_keys_helper_directly():
    from app.models.a2a import reject_snake_case_wire_keys

    reject_snake_case_wire_keys({"messageId": "m1", "parts": [{"contentType": "text/plain"}]})
    with pytest.raises(ValueError, match="camelCase"):
        reject_snake_case_wire_keys({"message_id": "m1"})
    with pytest.raises(ValueError, match="camelCase"):
        reject_snake_case_wire_keys({"parts": [{"content_type": "text/plain"}]})


def test_no_outbound_network_used():
    """The mock is exercised purely in-process; TestClient never opens a socket."""
    app = build_a2a_mock_app(
        CARD, [A2ARemoteStep(task_state=TaskState.COMPLETED)], "contract-test-case"
    )
    with TestClient(app, base_url="http://testserver") as client:
        response = _send(client)
    assert "id" in response
