import hashlib
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, StringConstraints
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.admin import audit
from app.admin.cases import collect
from app.db import get_session
from app.models import Domain, TakedownPack, TakedownRequest

from .contacts import recipients
from .pack import DOMAIN_PATTERN, build_zip

router = APIRouter()

SessionDep = Annotated[Session, Depends(get_session)]


class TakedownBody(BaseModel):
    domains: list[Annotated[str, StringConstraints(pattern=DOMAIN_PATTERN)]]
    generated_by: str


class SentBody(BaseModel):
    sent_by: str


class Pack(BaseModel):
    id: str
    recipient_kind: str
    recipient: str
    domains: list[str]
    sha256: str
    generated_at: datetime
    sent_at: datetime | None
    sent_by: str | None


class BuildResponse(BaseModel):
    packs: list[Pack]
    without_recipient: list[str]


class PackList(BaseModel):
    packs: list[Pack]


def as_pack(row: TakedownPack, domains: list[str]) -> Pack:
    return Pack(
        id=row.id, recipient_kind=row.recipient_kind, recipient=row.recipient, domains=sorted(domains),
        sha256=row.sha256, generated_at=row.generated_at, sent_at=row.sent_at, sent_by=row.sent_by,
    )


def pack_domains(session: Session, pack_id: str) -> list[str]:
    return list(session.scalars(select(TakedownRequest.domain).where(TakedownRequest.pack_id == pack_id)))


def require_pack(session: Session, pack_id: str) -> TakedownPack:
    row = session.get(TakedownPack, pack_id)
    if row is None:
        raise HTTPException(404, "Unknown pack")
    return row


@router.post("/takedowns", response_model=BuildResponse, status_code=201)
def build(body: TakedownBody, session: SessionDep):
    domains = sorted(set(body.domains))
    refused, evidence_of = [], {}
    for domain in domains:
        row = session.get(Domain, domain)
        if row is None or row.status != "confirmed" or row.confirmed_by != "officer":
            refused.append({"domain": domain, "reason": "not_officer_confirmed"})
            continue
        case = next(iter(collect(session, domain)), None)
        if case is None or case.evidence is None:
            refused.append({"domain": domain, "reason": "no_evidence"})
        else:
            evidence_of[domain] = case.evidence
    if refused:
        return JSONResponse({"refused": refused}, status_code=409)

    by_recipient, without_recipient = defaultdict(list), []
    for domain, evidence in evidence_of.items():
        found = recipients(evidence.payload.get("infrastructure", {}))
        if not found:
            without_recipient.append(domain)
        for target in found:
            by_recipient[target].append((domain, evidence))

    packs = []
    for (kind, recipient), items in by_recipient.items():
        data = build_zip(session, recipient, items)
        row = TakedownPack(
            id=f"t_{uuid.uuid4().hex}", recipient_kind=kind, recipient=recipient,
            sha256=hashlib.sha256(data).hexdigest(), zip=data, generated_by=body.generated_by,
        )
        session.add(row)
        session.flush()
        session.add_all(TakedownRequest(pack_id=row.id, domain=d, evidence_id=e.id) for d, e in items)
        audit.record(
            session, body.generated_by, "takedown.pack_built", row.id,
            after={"domains": [d for d, _ in items], "sha256": row.sha256},
        )
        session.flush()
        packs.append(as_pack(row, [d for d, _ in items]))
    session.commit()
    return BuildResponse(packs=packs, without_recipient=sorted(without_recipient))


@router.get("/takedowns", response_model=PackList)
def list_packs(session: SessionDep) -> PackList:
    rows = session.scalars(select(TakedownPack).order_by(TakedownPack.generated_at.desc(), TakedownPack.id)).all()
    return PackList(packs=[as_pack(row, pack_domains(session, row.id)) for row in rows])


@router.get("/takedowns/{pack_id}/pack.zip")
def download(pack_id: str, session: SessionDep) -> Response:
    row = require_pack(session, pack_id)
    return Response(
        row.zip, media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{row.id}.zip"'},
    )


@router.post("/takedowns/{pack_id}/sent", response_model=Pack)
def mark_sent(pack_id: str, body: SentBody, session: SessionDep) -> Pack:
    row = require_pack(session, pack_id)
    if row.sent_at is not None:
        raise HTTPException(409, "Already marked as sent")
    row.sent_at, row.sent_by = datetime.now(UTC), body.sent_by
    audit.record(session, body.sent_by, "takedown.sent", row.id, after={"sha256": row.sha256})
    session.commit()
    return as_pack(row, pack_domains(session, row.id))
