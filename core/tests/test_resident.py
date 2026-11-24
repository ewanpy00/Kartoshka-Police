"""Resident routes: report timeline with a secret token, SMS paste, scam radar, safe preview."""
from factories import make_check, with_evidence

from app import radar
from app.config import get_settings
from app.fast import sms
from app.models import Artifact, Check, Domain, Hit

AUTH = {"Authorization": "Bearer test-token"}
DEVICE = {"X-Device-Id": "test-device-1"}


def test_report_timeline_needs_the_token(client, session, enqueued):
    response = client.post("/v1/report", headers=DEVICE, json={"url": "https://tamm-pay-fines.xyz/pay", "note": "got an SMS"})
    assert response.status_code == 202
    body = response.json()
    assert body["report_id"].startswith("r_") and len(body["token"]) > 20
    assert body["check_id"] in enqueued
    assert client.get(f"/v1/reports/{body['report_id']}").status_code == 404
    assert client.get(f"/v1/reports/{body['report_id']}", headers={"X-Report-Token": "wrong"}).status_code == 404
    timeline = client.get(f"/v1/reports/{body['report_id']}", headers={"X-Report-Token": body["token"]}).json()
    assert [step["id"] for step in timeline["steps"]][:2] == ["sent", "analysed"]
    assert timeline["steps"][0]["done"] is True
    assert "note" not in timeline and "weight" not in str(timeline)


def test_report_timeline_follows_the_officer(client, session, enqueued):
    body = client.post("/v1/report", headers=DEVICE, json={"url": "https://report-flow.xyz/pay"}).json()
    check = session.get(Check, body["check_id"])
    check.verdict, check.score, check.deep_status, check.stage = "block", 85, "done", "deep"
    evidence_id = with_evidence(session, check)
    client.post(f"/v1/review/{evidence_id}", headers=AUTH, json={"decision": "confirm"})
    session.add(Hit(domain="report-flow.xyz", channel="dns", count=7))
    session.flush()
    timeline = client.get(f"/v1/reports/{body['report_id']}", headers={"X-Report-Token": body["token"]}).json()
    assert timeline["status"] == "confirmed"
    steps = {step["id"]: step for step in timeline["steps"]}
    assert steps["confirmed"]["done"] and steps["impact"]["done"] and timeline["blocked_count"] == 7
    assert "7" in steps["impact"]["en"]


def test_report_is_rate_limited(client, monkeypatch):
    from app import cache

    monkeypatch.setattr(cache, "rate_limited", lambda key, limit, window: True)
    assert client.post("/v1/report", headers=DEVICE, json={"url": "https://x-rate.xyz/"}).status_code == 429


def test_sms_links_and_story():
    text = "RTA: You have an unpaid traffic fine of 250 AED. Pay now to avoid penalty: rta-fines-ae.com/pay or https://bit.ly/3xYz."
    reading = sms.classify(text)
    assert reading["category"] == "fine" and reading["urgent"]
    assert reading["links"] == ["https://rta-fines-ae.com/pay", "https://bit.ly/3xYz"]
    arabic = sms.classify("عزيزي العميل، تم إيقاف بطاقتك. حدّث بياناتك فورًا عبر adcb-update.top")
    assert arabic["category"] == "bank" and arabic["links"] == ["https://adcb-update.top"]
    assert sms.classify("See you at 5, ok?")["category"] is None


def test_sms_route_adds_the_text_reason(client):
    body = client.post("/v1/sms", headers=DEVICE, json={
        "text": "Your parcel is on hold at customs. Pay the delivery fee within 24 hours: emiratespost-parcel.xyz/track"}).json()
    assert body["found_links"] == 1 and body["text"]["category"] == "delivery"
    codes = [item["code"] for item in body["links"][0]["reasons"]]
    assert "SMS_SCAM_TEXT" in codes
    assert all(item["weight"] is None for item in body["links"][0]["reasons"])


def test_radar_counts_confirmed_and_suspected(session):
    session.add(Domain(domain="radar-tamm.xyz", status="confirmed", brand_id="tamm", source="officer"))
    make_check(session, "radar-tamm-2.xyz", 80, hours_ago=2)
    make_check(session, "radar-low.xyz", 20, hours_ago=2)
    session.flush()
    body = radar.build(session, get_settings().data_dir)
    tamm = next(item for item in body["brands"] if item["brand_id"] == "tamm")
    assert tamm["confirmed"] >= 1 and tamm["suspected"] >= 1
    assert "radar-tamm[.]xyz" in tamm["examples"]
    assert all("radar-tamm-2" not in example for example in tamm["examples"])  # suspected names are never shown
    assert tamm["safe_action"]["url"].startswith("https://")
    assert any(line["category"] == "government" for line in body["headlines"]) or body["headlines"]


def test_preview_image_stays_inside_the_captures_volume(client, session):
    evidence_id = with_evidence(session, make_check(session, "preview-escape.xyz", 80))
    session.add(Artifact(evidence_id=evidence_id, kind="screenshot", path="/etc/passwd", sha256="0" * 64))
    session.flush()
    assert client.get(f"/v1/preview/{evidence_id}.png", headers=DEVICE).status_code == 404
    assert client.get("/v1/preview/ev_missing.png", headers=DEVICE).status_code == 404


def test_evidence_pdf(client, session):
    evidence_id = with_evidence(session, make_check(session, "pdf-case.xyz", 80))
    response = client.get(f"/v1/evidence/{evidence_id}.pdf")
    assert response.status_code == 200 and response.content.startswith(b"%PDF")
    assert response.headers["content-type"] == "application/pdf"
