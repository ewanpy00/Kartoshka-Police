"""Audit log: who decided what, when, and why. Rows are append-only (trigger in migration 0003)."""
import json

from sqlalchemy.orm import Session

from app.models import AuditLog


def _plain(value):
    return json.loads(json.dumps(value, default=str)) if value is not None else None


def record(session: Session, actor: str, action: str, target_kind: str, target: str,
           before: dict | None = None, after: dict | None = None, reason: str | None = None) -> None:
    session.add(AuditLog(actor=actor, action=action, target_kind=target_kind, target=target,
                         before=_plain(before), after=_plain(after), reason=reason))
