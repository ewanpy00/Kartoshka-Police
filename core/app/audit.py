"""Audit log: who decided what, when, and why. Rows are append-only (trigger in migration 0003)."""
import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog


def _plain(value):
    return json.loads(json.dumps(value, default=str)) if value is not None else None


def record(session: Session, actor: str, action: str, target_kind: str, target: str,
           before: dict | None = None, after: dict | None = None, reason: str | None = None) -> None:
    session.add(AuditLog(actor=actor, action=action, target_kind=target_kind, target=target,
                         before=_plain(before), after=_plain(after), reason=reason))


def recent(session: Session, target: str | None = None, limit: int = 100) -> list[dict]:
    """Newest first. `limit` is bounded here as well as in the route, 500 at most."""
    query = select(AuditLog).order_by(AuditLog.id.desc()).limit(max(1, min(limit, 500)))
    if target:
        query = query.where(AuditLog.target == target)
    return [
        {"id": row.id, "actor": row.actor, "action": row.action, "target_kind": row.target_kind, "target": row.target,
         "before": row.before, "after": row.after, "reason": row.reason, "created_at": row.created_at.isoformat()}
        for row in session.scalars(query)
    ]
