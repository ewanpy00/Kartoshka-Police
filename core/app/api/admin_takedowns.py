"""Officer console, takedown tracker (D4 and D5 of docs/admin-dashboard.md). Every route needs the write token.

Requests are prepared, never sent: the console's "Send" opens a mailto link (or the recipient's form)
and downloads the pack, then the officer presses "Mark as sent".
"""
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import AfterValidator, BaseModel, Field, StringConstraints
from sqlalchemy import select

from app import queue
from app.auth import require_write_token
from app.defang import defang
from app.deps import SessionDep, SettingsDep
from app.models import Domain, TakedownRequest
from app.takedown import pack, tracker

router = APIRouter(prefix="/admin", dependencies=[Depends(require_write_token)])
PAGE = 50


# A domain is a plain host name; path separators, "..", control characters and whitespace are a 422.
PlainDomain = Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True, max_length=pack.MAX_DOMAIN,
                                               pattern=pack.DOMAIN_PATTERN), AfterValidator(pack.check_domain)]


class CreateBody(BaseModel):
    domains: list[PlainDomain] = Field(min_length=1, max_length=200)
    reviewer: str = Field("Demo Officer", max_length=200)


class SentBody(BaseModel):
    reviewer: str = Field("Demo Officer", max_length=200)


def view(request: TakedownRequest, now: datetime, settings) -> dict:
    return {
        "id": request.id, "domain": request.domain, "display": defang(request.domain), "campaign_id": request.campaign_id,
        "recipient_kind": request.recipient_kind, "recipient": request.recipient,
        "form": request.recipient.startswith("https://"), "status": request.status,
        "overdue": tracker.overdue(request, now, settings), "pack_sha256": request.pack_sha256,
        "generated_at": request.generated_at.isoformat(),
        "sent_at": request.sent_at.isoformat() if request.sent_at else None, "sent_by": request.sent_by,
        "offline_at": request.offline_at.isoformat() if request.offline_at else None,
        "offline_reason": request.offline_reason, "checks_offline": request.checks_offline,
    }


def get_request(session, request_id: str) -> TakedownRequest:
    request = session.get(TakedownRequest, request_id)
    if request is None:
        raise HTTPException(404, "Unknown takedown request")
    return request


@router.get("/takedowns", description="Takedown requests, newest first. `overdue` is derived from TAKEDOWN_SLA_H.")
def takedowns(
    session: SessionDep,
    settings: SettingsDep,
    status: Annotated[str | None, Query(pattern="^(pack_ready|sent|offline_pending|closed|reopened|overdue)$")] = None,
    recipient: str | None = None,
    cursor: int = 0,
) -> dict:
    now = datetime.now(UTC)
    query = select(TakedownRequest).order_by(TakedownRequest.generated_at.desc(), TakedownRequest.domain)
    if status and status != "overdue":
        query = query.where(TakedownRequest.status == status)
    elif status == "overdue":
        query = query.where(TakedownRequest.status.in_(tracker.OPEN))
    if recipient:
        query = query.where(TakedownRequest.recipient_kind == recipient)
    rows = [r for r in session.scalars(query) if status != "overdue" or tracker.overdue(r, now, settings)]
    return {"total": len(rows), "requests": [view(r, now, settings) for r in rows[cursor:cursor + PAGE]],
            "next_cursor": cursor + PAGE if cursor + PAGE < len(rows) else None}


@router.post("/takedowns", description="Prepare requests for officer-confirmed domains: one per domain and recipient, "
             "one pack per recipient. If any domain is not confirmed by an officer (never confirmed, or "
             "auto-confirmed) the answer is 409 listing them and nothing is built. Domains without evidence or with "
             "requests already open are refused and listed.")
def create(body: CreateBody, session: SessionDep, settings: SettingsDep) -> dict:
    wanted = sorted(set(body.domains))
    rows = {row.domain: row for row in session.scalars(select(Domain).where(Domain.domain.in_(wanted)))}
    unconfirmed = [{"domain": d, "display": defang(d), "why": "not confirmed by an officer"} for d in wanted
                   if d not in rows or rows[d].status != "confirmed" or rows[d].confirmed_by != "officer"]
    if unconfirmed:
        raise HTTPException(409, {"refused": unconfirmed})
    created, refused = tracker.create(session, body.domains, body.reviewer)
    session.commit()
    now = datetime.now(UTC)
    return {"requests": [view(r, now, settings) for r in created],
            "refused": [{**r, "display": defang(r["domain"])} for r in refused]}


@router.get("/takedowns/stats", description="Requests per state, overdue count, and median hours from sent to offline, "
            "overall and per recipient kind.")
def takedown_stats(session: SessionDep, settings: SettingsDep) -> dict:
    return tracker.stats(session, settings=settings)


@router.get("/takedowns/{request_id}", description="One request, with the other requests in the same pack.")
def takedown(request_id: str, session: SessionDep, settings: SettingsDep) -> dict:
    request = get_request(session, request_id)
    now = datetime.now(UTC)
    return {**view(request, now, settings),
            "pack": [view(r, now, settings) for r in tracker.batch(session, request)]}


@router.get("/takedowns/{request_id}/pack.zip", response_class=Response,
            description="The pack zip, rebuilt reproducibly; `X-Pack-Matches` says whether it still hashes to the "
            "SHA-256 stored when the request was prepared.")
def pack_zip(request_id: str, session: SessionDep) -> Response:
    request = get_request(session, request_id)
    data = tracker.pack_bytes(session, request)
    digest = pack.sha256(data)
    name = f"takedown-{request.recipient_kind}-{request.generated_at:%Y%m%d-%H%M}.zip"
    return Response(data, media_type="application/zip", headers={
        "Content-Disposition": f'attachment; filename="{name}"', "X-Pack-SHA256": digest,
        "X-Pack-Matches": "true" if digest == request.pack_sha256 else "false",
    })


@router.post("/takedowns/{request_id}/sent", description="The officer sent the pack. Marks every request of the pack "
             "sent and starts re-checks every TAKEDOWN_RECHECK_MIN minutes.")
def mark_sent(request_id: str, body: SentBody, session: SessionDep, settings: SettingsDep) -> dict:
    request = get_request(session, request_id)
    try:
        members = tracker.mark_sent(session, request, body.reviewer, settings=settings)
    except tracker.Refused as refused:
        raise HTTPException(409, str(refused)) from None
    session.commit()
    now = datetime.now(UTC)
    return {"requests": [view(r, now, settings) for r in members]}


@router.post("/takedowns/{request_id}/recheck", description="\"Check now\": queue an offline check of the domain with "
             "both sandbox profiles. Offline results count only when at least TAKEDOWN_RECHECK_MIN apart.")
def recheck(request_id: str, session: SessionDep) -> dict:
    request = get_request(session, request_id)
    if request.status not in tracker.OPEN + ("closed",):
        raise HTTPException(409, f"request is {request.status}; mark it sent first")
    queue.enqueue("app.jobs.takedown_recheck", request.domain, timeout=400)
    return {"queued": True, "domain": request.domain, "display": defang(request.domain)}
