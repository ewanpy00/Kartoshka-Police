import hashlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Artifact, Evidence

GENESIS_HASH = "0" * 64
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
CHAIN_LOCK_KEY = 7_204_001


def _reject_floats(value: object) -> None:
    if isinstance(value, float):
        raise ValueError("Evidence payloads must not contain floats")
    if isinstance(value, dict):
        for item in value.values():
            _reject_floats(item)
    elif isinstance(value, list):
        for item in value:
            _reject_floats(item)


def _timestamp(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat()


def compute_hash(prev_hash: str, evidence_id: str, check_id: str, created_at: datetime, payload: dict) -> str:
    body = {"id": evidence_id, "check_id": check_id, "created_at": _timestamp(created_at), "payload": payload}
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256((prev_hash + "\n" + canonical).encode("utf-8")).hexdigest()


def _captures(captures_dir: str | Path | None) -> Path:
    return Path(captures_dir or get_settings().captures_dir)


def append_evidence(
    session: Session,
    check_id: str,
    payload: dict,
    screenshot_file: str | None = None,
    *,
    captures_dir: str | Path | None = None,
) -> Evidence:
    """Add one record to the hash chain. The caller commits."""
    capture = payload.setdefault("capture", {})
    screenshot_sha = None
    if screenshot_file:
        screenshot_sha = hashlib.sha256((_captures(captures_dir) / screenshot_file).read_bytes()).hexdigest()
        capture["screenshot"] = {"file": screenshot_file, "sha256": screenshot_sha}
    else:
        capture["screenshot"] = None
    _reject_floats(payload)

    session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": CHAIN_LOCK_KEY})
    prev_hash = session.scalar(select(Evidence.hash).order_by(Evidence.seq.desc()).limit(1)) or GENESIS_HASH
    evidence_id = f"e_{uuid.uuid4().hex}"
    created_at = datetime.now(UTC)
    evidence = Evidence(
        id=evidence_id,
        check_id=check_id,
        prev_hash=prev_hash,
        hash=compute_hash(prev_hash, evidence_id, check_id, created_at, payload),
        payload=payload,
        created_at=created_at,
    )
    session.add(evidence)
    session.flush()
    if screenshot_file:
        session.add(Artifact(evidence_id=evidence_id, sha256=screenshot_sha, path=screenshot_file))
        session.flush()
    return evidence


def verify_chain(session: Session) -> dict:
    count = session.scalar(select(func.count()).select_from(Evidence))
    expected_prev = GENESIS_HASH
    for row in session.scalars(select(Evidence).order_by(Evidence.seq)):
        reason = None
        if row.prev_hash != expected_prev:
            reason = "prev_hash_mismatch"
        elif row.hash != compute_hash(row.prev_hash, row.id, row.check_id, row.created_at, row.payload):
            reason = "payload_hash_mismatch"
        if reason:
            return {"count": count, "intact": False, "first_broken": {"id": row.id, "seq": row.seq, "reason": reason}}
        expected_prev = row.hash
    return {"count": count, "intact": True, "first_broken": None}


def screenshot_path(evidence: Evidence, *, captures_dir: str | Path | None = None) -> Path | None:
    screenshot = (evidence.payload.get("capture") or {}).get("screenshot")
    name = screenshot.get("file") if screenshot else None
    if not isinstance(name, str) or not name or "/" in name or "\\" in name or ".." in name:
        return None
    root = _captures(captures_dir).resolve()
    path = (root / name).resolve()
    return path if path.is_relative_to(root) and path.is_file() else None


def screenshot_png(evidence: Evidence, *, captures_dir: str | Path | None = None) -> bytes | None:
    """The screenshot bytes, only when the stored file really is a PNG."""
    path = screenshot_path(evidence, captures_dir=captures_dir)
    if path is None:
        return None
    data = path.read_bytes()
    return data if data.startswith(PNG_SIGNATURE) else None
