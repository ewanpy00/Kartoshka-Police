"""Rows for tests: checks and chained evidence records, inside the test transaction."""
from datetime import UTC, datetime, timedelta

from app.evidence import store
from app.models import Check
from app.verdict.reasons import reason
from app.verdict.service import new_check_id

NOW = datetime.now(UTC)


def make_check(session, domain: str, score: int, hours_ago: float = 1, host: str | None = None, **extra) -> Check:
    verdict = "block" if score > 70 else "warn" if score >= 30 else "allow"
    check = Check(id=new_check_id(), url=f"https://{host or domain}/pay", host=host or domain, domain=domain,
                  source=extra.pop("source", "hunter"), mode="deep", verdict=verdict, score=score, stage="fast",
                  brand="TAMM", brand_id="tamm", reasons=[reason("LOOKALIKE", brand="TAMM", official="tamm.abudhabi")],
                  sources=[], features={}, created_at=NOW - timedelta(hours=hours_ago), **extra)
    session.add(check)
    session.flush()
    return check


def with_evidence(session, check: Check) -> str:
    evidence = store.append(session, check.id, check.domain, {"url": check.url, "domain": check.domain, "score": check.score})
    check.evidence_id = evidence.id
    session.flush()
    return evidence.id
