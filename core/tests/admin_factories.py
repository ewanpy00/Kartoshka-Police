import uuid
from datetime import UTC, datetime

from app.models import Check, Evidence

AUTH = {"Authorization": "Bearer test-token"}


def payload(brand=None, title="Fake login", credential_form=True, screenshot=True):
    """A schema-1 evidence payload."""
    return {
        "schema": 1,
        "identity": {"url": "", "final_url": "", "domain": "", "captured_at": "2026-01-01T00:00:00+00:00"},
        "capture": {
            "title": title,
            "text": "",
            "forms": [],
            "screenshot": {"file": "x.png", "sha256": "0" * 64} if screenshot else None,
            "internal_requests_blocked": 0,
            "navigation_blocked": False,
        },
        "risk": {
            "score": 80,
            "verdict": "block",
            "credential_form": credential_form,
            "reasons": [{"code": "BRAND", "weight": 40, "source": "deep", "en": "Brand name", "ar": "اسم"}],
        },
        "infrastructure": {"rdap_status": "ok", "registrar": "Example Registrar", "ip": "203.0.113.5"},
        "scam": {"brand": brand, "phones": [], "whatsapp": [], "payment_hosts": []},
        "discovery": {"source": "test", "check_id": ""},
    }


def add_check(session, domain, score=80, verdict=None, source="api", created_at=None, brand=None, path=""):
    verdict = verdict or ("block" if score >= 70 else "warn" if score >= 30 else "allow")
    check = Check(
        id=f"c_{uuid.uuid4().hex}", url=f"https://{domain}/{path}", source=source, mode="deep", verdict=verdict,
        score=score, stage="deep", reasons=[], domain=domain, brand=brand,
        created_at=created_at or datetime.now(UTC),
    )
    session.add(check)
    session.flush()
    return check


def add_evidence(session, check, **payload_args):
    evidence = Evidence(
        id=f"e_{uuid.uuid4().hex}", check_id=check.id, hash=uuid.uuid4().hex * 2, payload=payload(**payload_args)
    )
    session.add(evidence)
    session.flush()
    return evidence
