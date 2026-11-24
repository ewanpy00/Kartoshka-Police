"""Takedown backend and routes (D4): recipients, pack, request states, offline detection."""
import asyncio
import hashlib
import io
import zipfile
from datetime import timedelta

import pytest
from factories import NOW, make_check
from sqlalchemy import select

from app import queue
from app.config import Settings
from app.deep import watchlist
from app.evidence import store
from app.models import AuditLog, Domain, Report, Watchlist
from app.takedown import contacts, tracker

AUTH = {"Authorization": "Bearer test-token"}
INFRA = {"a": ["198.51.100.7"], "aaaa": [], "ns": ["ns1.cheap-dns.example"], "asn": {"198.51.100.7": {"asn": "64500"}},
         "rdap": {"registrar": "Example Registrar", "abuse_emails": ["abuse@registrar.example"], "status": ["active"]}}
SETTINGS = Settings(takedown_recheck_min=60, takedown_offline_checks=2, takedown_sla_h=48)


def no_network(ip):
    return {"name": "Example Hosting", "abuse_emails": ["abuse@host.example"]}


@pytest.fixture(autouse=True)
def offline_contacts(monkeypatch):
    monkeypatch.setattr(contacts, "ip_abuse", no_network)
    jobs = []
    monkeypatch.setattr(queue, "enqueue", lambda name, *args, **kw: jobs.append((name, *args)))
    return jobs


def confirmed(session, domain: str, source: str = "officer", infra: dict | None = None):
    check = make_check(session, domain, 95)
    evidence = store.append(session, check.id, domain, {"url": check.url, "domain": domain, "score": 95,
                                                        "infra": infra or INFRA})
    check.evidence_id = evidence.id
    session.add(Domain(domain=domain, status="confirmed", source=source, brand_id="tamm"))
    session.flush()
    return check


def test_recipients():
    found = {r.kind: r.recipient for r in contacts.recipients("tamm-pay.top", INFRA, no_network)}
    assert found == {"registrar": "abuse@registrar.example", "hosting": "abuse@host.example", "gsb": contacts.GSB_FORM}
    cloudflare = {**INFRA, "ns": ["ada.ns.cloudflare.com"]}
    found = {r.kind: r.recipient for r in contacts.recipients("tamm-pay.ae", cloudflare, no_network)}
    assert found["cloudflare"] == contacts.CLOUDFLARE_FORM and "hosting" not in found and "aeda" in found


def test_ip_server_picks_the_registry_from_the_bootstrap():
    bootstrap = {"services": [[["198.51.0.0/16"], ["https://rdap.arin.example/"]]]}
    assert contacts.ip_server(bootstrap, "198.51.100.7") == "https://rdap.arin.example/"
    assert contacts.ip_server(bootstrap, "203.0.113.1") == "https://rdap.org/"


def test_create_refuses_unconfirmed_and_auto_confirmed(client, session):
    confirmed(session, "td-ok.top")
    confirmed(session, "td-auto.top", source="police")
    make_check(session, "td-open.top", 80)
    body = client.post("/v1/admin/takedowns", headers=AUTH,
                       json={"domains": ["td-ok.top", "td-auto.top", "td-open.top"], "reviewer": "Officer F"}).json()
    assert sorted(r["recipient_kind"] for r in body["requests"]) == ["gsb", "hosting", "registrar"]
    assert all(r["status"] == "pack_ready" and r["display"] == "td-ok[.]top" for r in body["requests"])
    why = {r["domain"]: r["why"] for r in body["refused"]}
    assert why["td-auto.top"].startswith("auto-confirmed") and why["td-open.top"] == "not confirmed"
    again = client.post("/v1/admin/takedowns", headers=AUTH, json={"domains": ["td-ok.top"]}).json()
    assert again["requests"] == [] and again["refused"][0]["why"].startswith("requests already open")


def test_pack_manifest_matches_and_leaves_out_report_notes(client, session):
    for site in ("pk-a.top", "pk-b.top"):
        check = confirmed(session, site)
        session.add(Report(id=f"r_{site[:4]}", token_hash="y" * 64, check_id=check.id, url=check.url, domain=site,
                           note="my phone number is 0501234567"))
    session.flush()
    body = client.post("/v1/admin/takedowns", headers=AUTH, json={"domains": ["pk-a.top", "pk-b.top"]}).json()
    registrar = next(r for r in body["requests"] if r["recipient_kind"] == "registrar")
    assert sum(r["recipient_kind"] == "registrar" for r in body["requests"]) == 2  # one request per domain, one pack
    response = client.get(f"/v1/admin/takedowns/{registrar['id']}/pack.zip", headers=AUTH)
    assert response.headers["x-pack-matches"] == "true"
    assert hashlib.sha256(response.content).hexdigest() == registrar["pack_sha256"]
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    names = set(archive.namelist())
    assert {"evidence/pk-a.top.pdf", "evidence/pk-b.top.json", "email.txt", "manifest.sha256"} <= names
    for line in archive.read("manifest.sha256").decode().splitlines():
        digest, name = line.split("  ")
        assert hashlib.sha256(archive.read(name)).hexdigest() == digest
    everything = b"".join(archive.read(name) for name in names)
    assert b"0501234567" not in everything
    email = archive.read("email.txt").decode()
    assert "To: abuse@registrar.example" in email and "pk-a[.]top" in email and "pk-a.top " not in email


def make_sent(session, domain="st.top"):
    confirmed(session, domain)
    created, _ = tracker.create(session, [domain], "Officer G", now=NOW - timedelta(hours=3), ip_lookup=no_network)
    request = next(r for r in created if r.recipient_kind == "registrar")
    tracker.mark_sent(session, request, "Officer G", now=NOW - timedelta(hours=3), settings=SETTINGS)
    return request


def run(session, domain, offline, at, reason="nxdomain"):
    return tracker.recheck(session, domain, SETTINGS, now=at,
                           prober=lambda d, u, s: tracker.Probe(offline, reason if offline else None, {}))


def test_state_machine(session):
    request = make_sent(session)
    assert request.status == "sent" and session.get(Watchlist, "st.top").reason == "TAKEDOWN"
    run(session, "st.top", True, NOW - timedelta(hours=2))
    assert request.status == "offline_pending" and request.checks_offline == 1
    run(session, "st.top", True, NOW - timedelta(hours=2) + timedelta(minutes=5))  # too soon: does not count
    assert request.status == "offline_pending" and request.checks_offline == 1
    result = run(session, "st.top", True, NOW - timedelta(minutes=55))
    assert request.status == "closed" and request.offline_reason == "nxdomain"
    assert (request.id, "closed") in result["events"]
    assert session.get(Watchlist, "st.top").expires_at >= NOW + timedelta(days=29)
    assert session.get(Domain, "st.top").status == "confirmed"  # stays on the blocklist
    run(session, "st.top", False, NOW)
    assert request.status == "reopened"
    actions = session.scalars(select(AuditLog.after).where(AuditLog.target == request.id, AuditLog.action == "takedown.state"))
    assert [a["status"] for a in actions] == ["offline_pending", "closed", "reopened"]


def test_a_live_result_resets_a_pending_request(session):
    request = make_sent(session, "lv.top")
    run(session, "lv.top", True, NOW - timedelta(hours=2))
    run(session, "lv.top", False, NOW - timedelta(hours=1))
    assert request.status == "sent" and request.checks_offline == 0 and request.offline_at is None


def test_offline_needs_both_profiles(monkeypatch):
    monkeypatch.setattr(tracker, "dns_state", lambda host: None)
    monkeypatch.setattr(tracker, "rdap_state", lambda domain: None)
    live_page = {"status": 200, "text": "Pay your fine", "forms": [{"method": "post", "fields": [{"type": "password"}]}]}
    gone_page = {"status": 404, "text": "Not found", "forms": []}
    pages = {"phone": gone_page, "bot": live_page}
    monkeypatch.setattr(tracker, "capture", lambda url, profile, settings: (pages[profile], None))
    assert not tracker.probe("x.top", None, SETTINGS).offline  # geofenced: gone for the phone only
    pages["bot"] = gone_page
    result = tracker.probe("x.top", None, SETTINGS)
    assert result.offline and result.reason == "http_gone"
    monkeypatch.setattr(tracker, "capture", lambda url, profile, settings: (None, None))
    assert tracker.probe("x.top", None, SETTINGS) is None  # sandbox down: no result at all


def test_page_state_reasons():
    assert tracker.page_state({"status": 410}, "x.top") == "http_gone"
    assert tracker.page_state({"status": 200, "text": "Warning: Suspected Phishing site ahead"}, "x.top") == "cf_interstitial"
    assert tracker.page_state({"status": 200, "text": "This domain is for sale", "forms": []}, "x.top") == "parked"
    assert tracker.page_state({"status": 200, "text": "Welcome to our bakery. " * 10, "forms": []}, "x.top") == "form_removed"


def test_watchlist_routes_open_takedowns_to_the_takedown_job(session, offline_contacts, enqueued):
    make_sent(session, "wl.top")
    session.get(Watchlist, "wl.top").next_check_at = NOW - timedelta(minutes=1)
    session.flush()
    ids = asyncio.run(watchlist.run_due(session, SETTINGS, now=NOW))
    assert ids == [] and ("app.jobs.takedown_recheck", "wl.top") in offline_contacts


def test_sent_recheck_and_stats_routes(client, session, offline_contacts):
    confirmed(session, "rt.top")
    created = client.post("/v1/admin/takedowns", headers=AUTH, json={"domains": ["rt.top"]}).json()["requests"]
    first = created[0]["id"]
    assert client.post(f"/v1/admin/takedowns/{first}/recheck", headers=AUTH).status_code == 409
    sent = client.post(f"/v1/admin/takedowns/{first}/sent", headers=AUTH, json={"reviewer": "Officer H"}).json()
    assert [r["status"] for r in sent["requests"]] == ["sent"]
    assert client.post(f"/v1/admin/takedowns/{first}/sent", headers=AUTH, json={}).status_code == 409
    assert client.post(f"/v1/admin/takedowns/{first}/recheck", headers=AUTH).json()["queued"]
    assert ("app.jobs.takedown_recheck", "rt.top") in offline_contacts
    listed = client.get("/v1/admin/takedowns?status=sent", headers=AUTH).json()
    assert first in {r["id"] for r in listed["requests"]}
    stats = client.get("/v1/admin/takedowns/stats", headers=AUTH).json()
    assert stats["by_status"]["sent"] >= 1 and stats["sla_hours"] == 48
    detail = client.get(f"/v1/admin/takedowns/{first}", headers=AUTH).json()
    assert detail["id"] == first and len(detail["pack"]) == 1
