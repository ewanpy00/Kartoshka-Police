import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select

from app import jobs
from app.checks import run_check
from app.config import get_settings
from app.deep import rdap
from app.evidence.store import verify_chain
from app.models import Domain, Evidence

FIXTURES = Path(__file__).parent / "deep_fixtures"
PNG = b"\x89PNG\r\n\x1a\n" + b"screenshot"
IP = "203.0.113.5"


def domain_document(registered_days_ago: int) -> dict:
    document = json.loads((FIXTURES / "rdap_domain.json").read_text())
    registered = datetime.now(UTC) - timedelta(days=registered_days_ago)
    document["events"][0]["eventDate"] = registered.isoformat()
    return document


def sandbox_client(answer: dict | int | Exception) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        if isinstance(answer, Exception):
            raise answer
        return httpx.Response(answer) if isinstance(answer, int) else httpx.Response(200, json=answer)

    return httpx.Client(base_url="http://sandbox", transport=httpx.MockTransport(handler))


def rdap_client(domain: dict | None) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.startswith("/domain/") and domain:
            return httpx.Response(200, json=domain)
        if request.url.path.startswith("/ip/"):
            return httpx.Response(200, json=json.loads((FIXTURES / "rdap_ip.json").read_text()))
        return httpx.Response(404)

    return httpx.Client(transport=httpx.MockTransport(handler))


def page(final_url: str, title: str, text: str, forms: list, links: list, screenshot: Path | None) -> dict:
    return {
        "final_url": final_url,
        "title": title,
        "text": text,
        "forms": forms,
        "links": links,
        "facts_available": True,
        "screenshot_path": str(screenshot) if screenshot else None,
        "navigation_blocked": False,
        "internal_requests_blocked": 2,
        "internal_hosts_blocked": [],
    }


PASSWORD_FORM = [{"action": "https://collect.example.net/pay", "inputs": [{"type": "password", "name": "pw"}]}]


@pytest.fixture
def captures(tmp_path, monkeypatch):
    (tmp_path / "shot.png").write_bytes(PNG)
    monkeypatch.setattr(get_settings(), "captures_dir", str(tmp_path))
    return tmp_path


@pytest.fixture
def resolved(monkeypatch):
    monkeypatch.setattr(rdap, "resolve", lambda host: IP)


def start(session, url):
    return run_check(session, url, "api", "deep", get_settings().data_dir)


def evidence_of(session, check):
    return session.get(Evidence, check.evidence_id)


def test_lookalike_page_with_password_form_is_blocked_with_evidence(session, captures, resolved, published):
    check = start(session, "https://tamm-secure-pay.test/fines")
    capture = page(
        "https://tamm-secure-pay.test/fines",
        "TAMM fines",
        "Call 050 123 4567",
        PASSWORD_FORM,
        ["https://wa.me/971559876543"],
        captures / "shot.png",
    )
    jobs.run_deep_check(session, check.id, sandbox_client(capture), rdap_client(domain_document(400)))

    assert (check.verdict, check.score, check.stage) == ("block", 90, "deep")
    assert [reason["code"] for reason in check.reasons] == ["BRAND_LOOKALIKE_DOMAIN", "CREDENTIAL_FORM", "BRAND_IN_PAGE"]
    assert check.brand == "TAMM"
    assert check.safe_action["url"].startswith("https://")
    assert check.final_url == "https://tamm-secure-pay.test/fines"
    assert check.internal_requests_blocked == 2
    assert check.domain == "tamm-secure-pay.test"

    payload = evidence_of(session, check).payload
    assert payload["schema"] == 1
    assert payload["identity"]["domain"] == "tamm-secure-pay.test"
    assert payload["capture"]["screenshot"]["file"] == "shot.png"
    assert payload["risk"]["credential_form"] is True
    assert payload["infrastructure"]["rdap_status"] == "ok"
    assert payload["infrastructure"]["ip"] == IP
    assert payload["scam"] == {
        "brand": "TAMM",
        "phones": ["+971501234567"],
        "whatsapp": ["+971559876543"],
        "payment_hosts": ["collect.example.net"],
    }
    assert payload["discovery"] == {"source": "api", "check_id": check.id}
    assert verify_chain(session)["intact"]
    assert published == [
        (
            "check.completed",
            {
                "check_id": check.id,
                "domain": "tamm-secure-pay.test",
                "verdict": "block",
                "score": 90,
                "source": "api",
                "evidence_id": check.evidence_id,
            },
        )
    ]
    assert session.get(Domain, "tamm-secure-pay.test") is None


def test_score_above_90_with_credential_form_is_auto_confirmed(session, captures, resolved, published):
    check = start(session, "https://tamm-secure-pay.test/")
    capture = page("https://tamm-secure-pay.test/", "TAMM", "TAMM", PASSWORD_FORM, [], captures / "shot.png")
    jobs.run_deep_check(session, check.id, sandbox_client(capture), rdap_client(domain_document(3)))

    assert check.score == 100
    row = session.get(Domain, "tamm-secure-pay.test")
    assert (row.status, row.brand_id, row.confirmed_by) == ("confirmed", "tamm", "auto")


def test_plain_page_is_allowed_and_still_gets_a_record(session, captures, resolved, published):
    check = start(session, "https://plain-site.test/")
    capture = page("https://plain-site.test/", "Plain", "Hello", [], [], captures / "shot.png")
    jobs.run_deep_check(session, check.id, sandbox_client(capture), rdap_client(None))

    assert (check.verdict, check.score, check.stage, check.reasons, check.brand) == ("allow", 0, "deep", [], None)
    payload = evidence_of(session, check).payload
    assert payload["infrastructure"]["rdap_status"] == "failed"
    assert payload["infrastructure"]["registrar"] is None
    assert len(published) == 1
    assert session.scalars(select(Domain).where(Domain.domain == "plain-site.test")).first() is None


@pytest.mark.parametrize(("status", "blocked"), [(422, True), (502, False)])
def test_unloaded_page_is_scored_from_the_domain_alone(session, captures, resolved, published, status, blocked):
    check = start(session, "https://tamm-secure-pay.test/")
    jobs.run_deep_check(session, check.id, sandbox_client(status), rdap_client(domain_document(400)))

    assert (check.verdict, check.score, check.final_url, check.navigation_blocked) == ("warn", 40, None, blocked)
    payload = evidence_of(session, check).payload
    assert [reason["code"] for reason in check.reasons] == ["BRAND_LOOKALIKE_DOMAIN"]
    assert payload["capture"]["screenshot"] is None
    assert (payload["capture"]["title"], payload["capture"]["text"], payload["capture"]["forms"]) == ("", "", [])
    assert payload["capture"]["navigation_blocked"] is blocked
    assert payload["scam"]["brand"] == "TAMM"


def test_unreadable_facts_of_a_loaded_page_add_the_reason_and_are_recorded(session, captures, resolved, published):
    check = start(session, "https://tamm-secure-pay.test/")
    capture = {**page("https://tamm-secure-pay.test/", "", "", [], [], captures / "shot.png"), "facts_available": False}
    jobs.run_deep_check(session, check.id, sandbox_client(capture), rdap_client(None))

    assert (check.verdict, check.score) == ("block", 70)
    assert [reason["code"] for reason in check.reasons] == ["BRAND_LOOKALIKE_DOMAIN", "PAGE_FACTS_UNAVAILABLE"]
    assert evidence_of(session, check).payload["capture"]["facts_available"] is False


@pytest.mark.parametrize(
    "hostile_ip_record",
    [{"name": 42, "country": 1.5, "entities": [{"roles": ["registrant"], "vcardArray": "x"}]}, {"entities": [{"roles": ["abuse"], "vcardArray": ["vcard", [["email", {}, "text", 2.5]]]}]}],
)
def test_hostile_rdap_records_still_end_with_a_verdict_and_evidence(session, captures, resolved, published, hostile_ip_record):
    check = start(session, "https://tamm-secure-pay.test/")
    document = domain_document(400)
    document["events"][0]["eventDate"] = "not a date"
    document["entities"][0]["vcardArray"] = ["vcard", "broken"]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=document if request.url.path.startswith("/domain/") else hostile_ip_record)

    hostile = httpx.Client(transport=httpx.MockTransport(handler))
    capture = page("https://tamm-secure-pay.test/", "TAMM", "", PASSWORD_FORM, [], captures / "shot.png")
    jobs.run_deep_check(session, check.id, sandbox_client(capture), hostile)

    assert (check.verdict, check.stage) == ("block", "deep")
    infrastructure = evidence_of(session, check).payload["infrastructure"]
    assert (infrastructure["registered_at"], infrastructure["registrar"], infrastructure["ip_network"]) == (None, None, None)
    assert len(published) == 1


def test_unreachable_sandbox_fails_the_job_and_leaves_the_check_pending(session, captures, resolved, published):
    check = start(session, "https://plain-site.test/")
    with pytest.raises(httpx.ConnectError):
        jobs.run_deep_check(session, check.id, sandbox_client(httpx.ConnectError("down")), rdap_client(None))
    assert (check.verdict, check.stage, check.evidence_id) == ("pending", "fast", None)
    assert published == []
