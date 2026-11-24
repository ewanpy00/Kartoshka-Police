"""Rows for the officer-console tests in feat/app's shapes: checks, chained evidence records, resident reports."""
import uuid
from datetime import UTC, datetime

from app.evidence import store
from app.models import Check, Report
from app.verdict.reasons import reason

AUTH = {"Authorization": "Bearer test-token"}


def payload(brand=None, title="Fake login", credential_form=True, screenshot=True, phones=(), whatsapp=()):
    """An evidence payload as the deep job writes it (see `deep.job.payload`)."""
    return {
        "page": {"title": title, "status": 200, "forms": [], "asks_for": ["password"] if credential_form else [],
                 "phones": list(phones), "whatsapp": list(whatsapp), "payment_hosts": []},
        "brand": brand,
        "reasons": [reason("LOOKALIKE", brand="TAMM", official="tamm.abudhabi")],
        "infra": {"a": ["203.0.113.5"], "asn": {"203.0.113.5": {"asn": "64500", "country": "NL", "name": "Hoster BV"}},
                  "rdap": {"registrar": "Example Registrar"}},
        "artifacts": [{"kind": "screenshot", "sha256": "0" * 64, "path": "x.png"}] if screenshot else [],
    }


def add_check(session, domain, score=80, verdict=None, source="api", created_at=None, brand=None, path=""):
    verdict = verdict or ("block" if score > 70 else "warn" if score >= 30 else "allow")
    check = Check(
        id=f"c_{uuid.uuid4().hex}", url=f"https://{domain}/{path}", host=domain, domain=domain, source=source,
        mode="deep", verdict=verdict, score=score, stage="deep", reasons=[reason("LOOKALIKE", brand="TAMM", official="tamm.abudhabi")],
        brand=brand, brand_id="tamm" if brand else None, sources=[], features={}, created_at=created_at or datetime.now(UTC),
    )
    session.add(check)
    session.flush()
    return check


def add_evidence(session, check, **payload_args):
    evidence = store.append(session, check.id, check.domain, payload(**payload_args))
    check.evidence_id = evidence.id
    session.flush()
    return evidence


def add_report(session, check, note=None):
    report = Report(id=f"r_{uuid.uuid4().hex[:12]}", token_hash="x" * 64, check_id=check.id, url=check.url,
                    domain=check.domain, note=note)
    session.add(report)
    session.flush()
    return report
