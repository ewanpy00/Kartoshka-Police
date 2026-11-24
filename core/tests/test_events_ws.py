import pytest
from starlette.testclient import WebSocketDisconnect

from app import events


def refused_after(client, url, first_message):
    with pytest.raises(WebSocketDisconnect) as refused, client.websocket_connect(url) as socket:
        if first_message is not None:
            socket.send_text(first_message)
        socket.receive_text()
    return refused.value.code


def test_socket_is_refused_when_the_first_message_is_not_auth(client, monkeypatch):
    monkeypatch.setattr(events, "AUTH_TIMEOUT_SECONDS", 0.2)
    assert refused_after(client, "/v1/events", None) == 4401


def test_socket_is_refused_with_a_wrong_token(client):
    assert refused_after(client, "/v1/events", '{"type":"auth","token":"nope"}') == 4401


@pytest.mark.parametrize("first", ["not json", "[]", '{"type":"auth"}', '{"type":"auth","token":5}', '{"type":"hello","token":"test-token"}'])
def test_socket_is_refused_for_a_malformed_first_message(client, first):
    assert refused_after(client, "/v1/events", first) == 4401


def test_a_token_in_the_query_string_does_not_authenticate(client, monkeypatch):
    monkeypatch.setattr(events, "AUTH_TIMEOUT_SECONDS", 0.2)
    assert refused_after(client, "/v1/events?token=test-token", None) == 4401


def test_socket_is_refused_when_no_token_is_configured(client, settings):
    settings.core_write_token = ""
    assert refused_after(client, "/v1/events", '{"type":"auth","token":""}') == 4401


def test_published_event_reaches_an_authenticated_client(client):
    with client.websocket_connect("/v1/events") as socket:
        socket.send_json({"type": "auth", "token": "test-token"})
        assert socket.receive_json() == {"type": "hello"}
        events.publish("case.reviewed", {"domain": "tamm-pay.xyz", "decision": "confirm", "reviewer": "officer"})
        message = socket.receive_json()
    assert message["type"] == "case.reviewed"
    assert message["data"]["domain"] == "tamm-pay.xyz"
