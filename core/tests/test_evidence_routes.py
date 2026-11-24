"""Evidence routes: exports and the screenshot need the write token; the screenshot is checked before it is served."""
import pytest
from factories import make_check
from sqlalchemy import text

from app.config import Settings
from app.evidence import store
from app.models import Artifact

AUTH = {"Authorization": "Bearer test-token"}
PNG = store.PNG_SIGNATURE + b"\x00" * 16


@pytest.fixture
def captures(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "get_settings", lambda: Settings(captures_dir=str(tmp_path)))
    return tmp_path


def record(session, shot=None):
    check = make_check(session, "route.example", 90)
    evidence = store.append(session, check.id, check.domain, {"url": check.url, "domain": check.domain, "score": 90,
                                                                "reasons": [{"code": "X", "en": "e", "ar": "ع"}]})
    if shot is not None:
        session.add(Artifact(evidence_id=evidence.id, kind="screenshot", sha256="0" * 64, path=str(shot)))
        session.flush()
    return evidence


@pytest.mark.parametrize("suffix", ["pdf", "json"])
def test_exports_need_the_write_token(client, session, suffix):
    evidence = record(session)
    assert client.get(f"/v1/evidence/{evidence.id}.{suffix}").status_code == 401
    assert client.get(f"/v1/evidence/{evidence.id}.{suffix}", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get(f"/v1/evidence/{evidence.id}.{suffix}", headers=AUTH).status_code == 200


def test_export_bodies(client, session):
    evidence = record(session)
    body = client.get(f"/v1/evidence/{evidence.id}.json", headers=AUTH).json()
    assert body["hash"] == evidence.hash and body["payload"]["domain"] == "route.example"
    pdf = client.get(f"/v1/evidence/{evidence.id}.pdf", headers=AUTH)
    assert pdf.headers["content-type"] == "application/pdf" and pdf.content.startswith(b"%PDF")
    assert client.get("/v1/evidence/ev_unknown.pdf", headers=AUTH).status_code == 404


def test_verify_route_names_the_broken_record(client, session):
    evidence = record(session)
    assert client.get("/v1/admin/evidence/verify", headers=AUTH).json()["message"] == "chain intact"
    session.execute(text("ALTER TABLE evidence DISABLE TRIGGER evidence_no_update"))
    session.execute(text("UPDATE evidence SET payload = CAST('{}' AS json) WHERE id = :id"), {"id": evidence.id})
    session.expire_all()
    body = client.get("/v1/admin/evidence/verify", headers=AUTH).json()
    assert body["intact"] is False and evidence.id in body["message"]
    assert body["first_broken"]["reason"] == "payload_hash_mismatch" and body["first_broken"]["seq"] == evidence.seq
    assert client.get("/v1/admin/evidence/verify").status_code == 401


def test_screenshot_is_served_with_nosniff(client, session, captures):
    (captures / "shot.png").write_bytes(PNG)
    evidence = record(session, captures / "shot.png")
    response = client.get(f"/v1/admin/evidence/{evidence.id}/screenshot.png", headers=AUTH)
    assert response.status_code == 200 and response.content == PNG
    assert response.headers["content-type"] == "image/png" and response.headers["x-content-type-options"] == "nosniff"
    assert client.get(f"/v1/admin/evidence/{evidence.id}/screenshot.png").status_code == 401


def test_screenshot_refuses_non_png_and_paths_outside_captures(client, session, captures, tmp_path_factory):
    (captures / "fake.png").write_text("<html>x</html>")
    assert client.get(f"/v1/admin/evidence/{record(session, captures / 'fake.png').id}/screenshot.png",
                      headers=AUTH).status_code == 404
    outside = tmp_path_factory.mktemp("outside") / "a.png"
    outside.write_bytes(PNG)
    assert client.get(f"/v1/admin/evidence/{record(session, outside).id}/screenshot.png", headers=AUTH).status_code == 404
    assert client.get(f"/v1/admin/evidence/{record(session).id}/screenshot.png", headers=AUTH).status_code == 404
    assert client.get("/v1/admin/evidence/ev_unknown/screenshot.png", headers=AUTH).status_code == 404
