from sqlalchemy.orm import Session

from app.models import AuditLog


def record(
    session: Session,
    actor: str,
    action: str,
    target: str,
    before: dict | None = None,
    after: dict | None = None,
    reason: str | None = None,
) -> AuditLog:
    """Add an audit row to the session. The caller commits."""
    entry = AuditLog(actor=actor, action=action, target=target, before=before, after=after, reason=reason)
    session.add(entry)
    return entry
