import pytest
from starlette.testclient import WebSocketDisconnect

from app import events


def test_socket_is_refused_without_a_token(client):
    with pytest.raises(WebSocketDisconnect) as refused, client.websocket_connect("/v1/events"):
        pass
    assert refused.value.code == 4401


def test_socket_is_refused_with_a_wrong_token(client):
    with pytest.raises(WebSocketDisconnect) as refused, client.websocket_connect("/v1/events?token=nope"):
        pass
    assert refused.value.code == 4401


def test_socket_is_refused_when_no_token_is_configured(client, settings):
    settings.core_write_token = ""
    with pytest.raises(WebSocketDisconnect) as refused, client.websocket_connect("/v1/events?token="):
        pass
    assert refused.value.code == 4401


def test_published_event_reaches_a_connected_client(client):
    with client.websocket_connect("/v1/events?token=test-token") as socket:
        assert socket.receive_json() == {"type": "hello"}
        events.publish("case.reviewed", {"domain": "tamm-pay.xyz", "decision": "confirm", "reviewer": "officer"})
        message = socket.receive_json()
    assert message["type"] == "case.reviewed"
    assert message["data"]["domain"] == "tamm-pay.xyz"
