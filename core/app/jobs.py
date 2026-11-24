from datetime import UTC, datetime
from pathlib import Path

import httpx
from sqlalchemy.orm import Session, sessionmaker

from app import events
from app.admin.review import auto_confirm
from app.brands import load_brands, safe_action
from app.checks import host_and_parents
from app.config import get_settings
from app.db import get_engine
from app.deep import extract, rdap
from app.deep.score import score
from app.evidence.store import append_evidence
from app.graph.cluster import ingest_evidence
from app.models import Check

SANDBOX_TIMEOUT = 30
AUTO_CONFIRM_ABOVE = 90
NO_CAPTURE = {"title": "", "text": "", "forms": [], "links": [], "facts_available": False, "screenshot_path": None, "internal_requests_blocked": 0}


def capture_page(sandbox: httpx.Client, url: str) -> dict:
    """The sandbox capture. A refused or unloadable page gives an empty capture; an unreachable sandbox raises."""
    response = sandbox.post("/capture", json={"url": url})
    if response.status_code in (422, 502):
        return {**NO_CAPTURE, "final_url": "", "navigation_blocked": response.status_code == 422}
    response.raise_for_status()
    return response.json()


def run_deep_check(session: Session, check_id: str, sandbox: httpx.Client, rdap_client: httpx.Client) -> None:
    settings = get_settings()
    check = session.get(Check, check_id)
    capture = capture_page(sandbox, check.url)
    host = host_and_parents(check.url)[0]
    domain = host.removeprefix("www.")
    forms = capture["forms"]
    credential_form = extract.credential_form(forms)
    page_loaded = not capture["navigation_blocked"] and bool(capture["final_url"])
    infrastructure = rdap.lookup(rdap_client, host, rdap.resolve(host))
    brands = load_brands(settings.data_dir)
    result = score(
        host,
        f"{capture['title']}\n{capture['text']}",
        infrastructure["registered_at"],
        credential_form,
        page_loaded and not capture["facts_available"],
        brands,
        datetime.now(UTC),
    )
    brand = result["brand"]
    payload = {
        "schema": 1,
        "identity": {"url": check.url, "final_url": capture["final_url"], "domain": domain, "captured_at": datetime.now(UTC).isoformat()},
        "capture": {
            "title": capture["title"],
            "text": capture["text"],
            "forms": forms,
            "facts_available": capture["facts_available"],
            "internal_requests_blocked": capture["internal_requests_blocked"],
            "navigation_blocked": capture["navigation_blocked"],
        },
        "risk": {"score": result["score"], "verdict": result["verdict"], "credential_form": credential_form, "reasons": result["reasons"]},
        "infrastructure": infrastructure,
        "scam": {
            "brand": brand["names"][0] if brand else None,
            "phones": extract.phones(capture["text"], capture["links"]),
            "whatsapp": extract.whatsapp(capture["links"]),
            "payment_hosts": extract.payment_hosts(forms, host),
        },
        "discovery": {"source": check.source, "check_id": check.id},
    }
    screenshot = capture["screenshot_path"]
    evidence = append_evidence(session, check.id, payload, Path(screenshot).name if screenshot else None)
    if result["verdict"] in ("warn", "block"):
        ingest_evidence(session, evidence.id)

    check.domain = domain
    check.verdict, check.score, check.stage, check.reasons = result["verdict"], result["score"], "deep", result["reasons"]
    check.brand = brand["names"][0] if brand else None
    check.safe_action = safe_action(brand, check.url) if brand else None
    check.final_url = None if capture["navigation_blocked"] else capture["final_url"] or None
    check.evidence_id = evidence.id
    check.internal_requests_blocked = capture["internal_requests_blocked"]
    check.navigation_blocked = capture["navigation_blocked"]
    if result["score"] > AUTO_CONFIRM_ABOVE and credential_form:
        auto_confirm(session, domain, brand["id"], evidence.id)
    session.commit()
    events.publish(
        "check.completed",
        {"check_id": check.id, "domain": domain, "verdict": check.verdict, "score": check.score, "source": check.source, "evidence_id": evidence.id},
    )


def deep_check(check_id: str) -> None:
    with sessionmaker(get_engine())() as session, httpx.Client(
        base_url=get_settings().sandbox_url, timeout=SANDBOX_TIMEOUT
    ) as sandbox, rdap.make_client() as rdap_client:
        run_deep_check(session, check_id, sandbox, rdap_client)
