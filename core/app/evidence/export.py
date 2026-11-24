import base64
import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from sqlalchemy import select
from sqlalchemy.orm import Session
from weasyprint import HTML
from weasyprint.urls import URLFetcher

from app.models import Evidence, Review

from .store import screenshot_png

env = Environment(loader=FileSystemLoader(Path(__file__).parent / "templates"), autoescape=True)


def defang(value: object) -> str:
    text = re.sub(r"^http", "hxxp", str(value or ""), flags=re.IGNORECASE)
    return text.replace(".", "[.]")


env.filters["defang"] = defang


class ScreenshotOnlyFetcher(URLFetcher):
    """Refuses every request except the one data: URI built from our own screenshot file."""

    def __init__(self, allowed_url: str | None):
        super().__init__()
        self.allowed_url = allowed_url

    def fetch(self, url, headers=None):
        if url != self.allowed_url:
            raise ValueError(f"Fetching is disabled during PDF rendering: {url[:80]}")
        return super().fetch(url, headers)


def _evidence(session: Session, evidence_id: str) -> Evidence:
    evidence = session.get(Evidence, evidence_id)
    if evidence is None:
        raise LookupError(evidence_id)
    return evidence


def _reviews(session: Session, evidence_id: str) -> list[dict]:
    rows = session.scalars(select(Review).where(Review.evidence_id == evidence_id).order_by(Review.id))
    return [
        {"decision": r.decision, "reason": r.reason, "reviewer": r.reviewer, "reviewed_at": r.reviewed_at.isoformat()}
        for r in rows
    ]


def export_json(session: Session, evidence_id: str) -> dict:
    evidence = _evidence(session, evidence_id)
    return {
        "id": evidence.id,
        "check_id": evidence.check_id,
        "seq": evidence.seq,
        "prev_hash": evidence.prev_hash,
        "hash": evidence.hash,
        "created_at": evidence.created_at.isoformat(),
        "payload": evidence.payload,
        "reviews": _reviews(session, evidence_id),
    }


def render_html(session: Session, evidence_id: str, screenshot_uri: str | None) -> str:
    record = export_json(session, evidence_id)
    return env.get_template("evidence.html").render(e=record, p=record["payload"], screenshot_uri=screenshot_uri)


def render_pdf(session: Session, evidence_id: str, *, captures_dir: str | Path | None = None) -> bytes:
    png = screenshot_png(_evidence(session, evidence_id), captures_dir=captures_dir)
    uri = f"data:image/png;base64,{base64.b64encode(png).decode()}" if png else None
    html = render_html(session, evidence_id, uri)
    return HTML(string=html, url_fetcher=ScreenshotOnlyFetcher(uri)).write_pdf()
