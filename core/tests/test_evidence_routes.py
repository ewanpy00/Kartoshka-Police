import pytest

from app.config import Settings, get_settings
from app.main import app
from evidence_helpers import add_record, make_payload, png_bytes

AUTH = {"Authorization": "Bearer test-token"}


@pytest.fixture
def captures(tmp_path, client):
    app.dependency_overrides[get_settings] = lambda: Settings(core_write_token="test-token", captures_dir=str(tmp_path))
    return tmp_path


def test_verify_route_reports_an_intact_chain(client, session):
    add_record(session, "c0")
    body = client.get("/v1/admin/evidence/verify", headers=AUTH).json()
    assert body["intact"] is True and body["message"] == "chain intact"


def test_verify_route_names_the_broken_record(client, session):
    evidence = add_record(session, "c0")
    evidence.payload = {**evidence.payload, "scam": {}}
    session.flush()
    body = client.get("/v1/admin/evidence/verify", headers=AUTH).json()
    assert body["intact"] is False and evidence.id in body["message"]
    assert body["first_broken"]["reason"] == "payload_hash_mismatch"


def test_png_is_served_with_nosniff(client, session, captures):
    (captures / "shot.png").write_bytes(png_bytes())
    evidence = add_record(session, "c0", screenshot_file="shot.png", captures_dir=captures)
    response = client.get(f"/v1/admin/evidence/{evidence.id}/screenshot.png", headers=AUTH)
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.content == png_bytes()


def test_non_png_file_is_refused(client, session, captures):
    (captures / "fake.png").write_text("<html>not a png</html>")
    evidence = add_record(session, "c0", screenshot_file="fake.png", captures_dir=captures)
    assert client.get(f"/v1/admin/evidence/{evidence.id}/screenshot.png", headers=AUTH).status_code == 404


def test_traversal_name_returns_404(client, session, captures):
    payload = make_payload()
    payload["capture"]["screenshot"] = None
    evidence = add_record(session, "c0", payload)
    evidence.payload = {**evidence.payload, "capture": {"screenshot": {"file": "../../etc/passwd", "sha256": "0" * 64}}}
    session.flush()
    assert client.get(f"/v1/admin/evidence/{evidence.id}/screenshot.png", headers=AUTH).status_code == 404


def test_no_screenshot_and_unknown_id_return_404(client, session):
    evidence = add_record(session, "c0")
    assert client.get(f"/v1/admin/evidence/{evidence.id}/screenshot.png", headers=AUTH).status_code == 404
    assert client.get("/v1/admin/evidence/e_unknown/screenshot.png", headers=AUTH).status_code == 404


def test_admin_routes_need_the_token(client, session):
    evidence = add_record(session, "c0")
    assert client.get("/v1/admin/evidence/verify").status_code == 401
    assert client.get(f"/v1/admin/evidence/{evidence.id}/screenshot.png").status_code == 401
