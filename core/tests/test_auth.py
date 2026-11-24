from app.config import Settings, get_settings
from app.main import app

BODY = {"decision": "confirm"}


def test_missing_token_is_rejected(client):
    assert client.post("/v1/review/ev_1", json=BODY).status_code == 401


def test_wrong_token_is_rejected(client):
    response = client.post("/v1/review/ev_1", json=BODY, headers={"Authorization": "Bearer nope"})
    assert response.status_code == 401


def test_right_token_passes_the_gate(client):
    response = client.post("/v1/review/ev_1", json=BODY, headers={"Authorization": "Bearer test-token"})
    assert response.status_code == 404


def test_unset_token_rejects_every_write(client):
    app.dependency_overrides[get_settings] = lambda: Settings(core_write_token="")
    for header in ("Bearer ", "Bearer x"):
        assert client.post("/v1/review/ev_1", json=BODY, headers={"Authorization": header}).status_code == 401
    assert client.post("/v1/review/ev_1", json=BODY).status_code == 401


def test_open_routes_need_no_token(client):
    assert client.post("/v1/report", json={"url": "https://unknown-site.example/"}).status_code == 202
