"""Append-only, hash-chained evidence records (ARCHITECTURE.md 1.5).

Each row stores the SHA-256 of the previous row and its own hash over (previous hash + canonical JSON of
the payload). Rows are numbered by `seq` under a transaction-level advisory lock, so two workers cannot
fork the chain. The database rejects UPDATE and DELETE on the table (migration 0002).
"""
import hashlib
import json
import uuid

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import Artifact, Evidence

CHAIN_LOCK = 7_301_001


def canonical(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def row_hash(prev_hash: str | None, payload: dict) -> str:
    return hashlib.sha256(((prev_hash or "") + canonical(payload)).encode("utf-8")).hexdigest()


def new_evidence_id() -> str:
    return f"ev_{uuid.uuid4().hex[:24]}"


def append(session: Session, check_id: str, domain: str | None, payload: dict, artifacts: list[dict] = ()) -> Evidence:
    """Add one record at the end of the chain. The caller commits."""
    payload = json.loads(canonical(payload))
    session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": CHAIN_LOCK})
    last = session.execute(select(Evidence.seq, Evidence.hash).order_by(Evidence.seq.desc()).limit(1)).first()
    seq, prev_hash = (last[0] + 1, last[1]) if last else (1, None)
    evidence = Evidence(
        id=new_evidence_id(), seq=seq, check_id=check_id, domain=domain,
        prev_hash=prev_hash, hash=row_hash(prev_hash, payload), payload=payload,
    )
    session.add(evidence)
    session.flush()
    for item in artifacts:
        session.add(Artifact(evidence_id=evidence.id, kind=item["kind"], sha256=item["sha256"], path=item["path"]))
    return evidence


def verify(session: Session, limit: int | None = None) -> dict:
    """Recompute the chain from the first row. Returns the first broken seq, if any."""
    prev_hash, rows = None, 0
    query = select(Evidence).order_by(Evidence.seq)
    if limit:
        query = query.limit(limit)
    for evidence in session.scalars(query):
        rows += 1
        if evidence.prev_hash != prev_hash or evidence.hash != row_hash(prev_hash, evidence.payload):
            return {"ok": False, "rows": rows, "broken_at": evidence.seq}
        prev_hash = evidence.hash
    return {"ok": True, "rows": rows, "broken_at": None, "head": prev_hash}
