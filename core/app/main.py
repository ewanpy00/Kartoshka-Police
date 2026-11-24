import asyncio
import csv
import io
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Response
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app import events, queue
from app.admin.router import router as admin_router
from app.auth import require_write_token
from app.checks import run_check
from app.config import Settings, get_settings
from app.db import get_session
from app.evidence import routes as evidence_routes
from app.models import Check, Domain, Evidence, Review
from app.schemas import (
    BatchRequest,
    BatchResponse,
    BatchResult,
    BlocklistEntry,
    BlocklistResponse,
    CheckRequest,
    Health,
    ReportRequest,
    ReportResponse,
    ReviewRequest,
    ReviewResponse,
    Verdict,
)

app = FastAPI(title="Kartoshka Core", version="0.1.0")
v1 = APIRouter(prefix="/v1")

SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]

PENDING_NOTE = (
    "`pending` means no verdict yet, never safe. Clients poll `GET /v1/check/{id}`. "
    "Gatekeeper handles `pending` like the timeout branch of ARCHITECTURE.md section 3: "
    "forward the link if the local score is low, otherwise show 'Checking link' briefly, then warn."
)


@app.get("/healthz", response_model=Health, responses={503: {"model": Health}})
def healthz(session: SessionDep) -> Response:
    health = {"status": "ok", "db": "ok", "redis": "ok"}
    try:
        session.execute(text("SELECT 1"))
    except Exception as error:
        health["db"] = f"error: {type(error).__name__}"
    try:
        queue.get_redis().ping()
    except Exception as error:
        health["redis"] = f"error: {type(error).__name__}"
    failed = "ok" != health["db"] or "ok" != health["redis"]
    if failed:
        health["status"] = "error"
    return JSONResponse(health, status_code=503 if failed else 200)


@v1.post("/check", response_model=Verdict, description="Check one URL against the domains table. Official and confirmed domains match the host or any "
    f"parent domain; allowlisted domains match only the exact host or its www form.\n\n{PENDING_NOTE}")
def create_check(body: CheckRequest, session: SessionDep, settings: SettingsDep) -> Verdict:
    """Official and confirmed domains match the host or any parent; allowlisted ones only the host or its www form."""
    check = run_check(session, body.url, body.source, body.mode, settings.data_dir)
    if check.verdict == "pending" and body.mode == "deep":
        queue.enqueue_deep_check(check.id)
    return Verdict.model_validate(check)


@v1.get("/check/{check_id}", response_model=Verdict, description=f"Fetch a stored check.\n\n{PENDING_NOTE}")
def get_check(check_id: str, session: SessionDep) -> Verdict:
    check = session.get(Check, check_id)
    if check is None:
        raise HTTPException(404, "Unknown check id")
    return Verdict.model_validate(check)


async def await_resolution(session: Session, check: Check, budget_ms: int) -> bool:
    """Wait up to the budget for a pending check to resolve. Returns True when the budget ran out."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + budget_ms / 1000
    while check.verdict == "pending":
        remaining = deadline - loop.time()
        if remaining <= 0:
            return True
        await asyncio.sleep(min(0.1, remaining))
        session.refresh(check)
    return False


@v1.post(
    "/batch",
    response_model=BatchResponse,
    description="Check many URLs and return a definite `allow` or `block` for each, never `pending`. "
    "Use `?format=csv` for the same rows as CSV.",
)
async def batch(
    body: BatchRequest,
    session: SessionDep,
    settings: SettingsDep,
    format: Annotated[str, Query(pattern="^(json|csv)$")] = "json",
) -> Response:
    """Skeleton-only: an unknown URL waits for its budget and then answers allow.

    Slice 1 replaces the wait with the fast score.
    """
    slots = asyncio.Semaphore(settings.batch_concurrency)

    async def check_one(url: str) -> BatchResult:
        async with slots:
            check = run_check(session, url, "batch", "deep", settings.data_dir)
            timed_out = False
            if check.verdict == "pending":
                queue.enqueue_deep_check(check.id)
                timed_out = await await_resolution(session, check, settings.batch_url_budget_ms)
            verdict = "block" if check.score >= settings.batch_cutoff else "allow"
            return BatchResult(url=url, check_id=check.id, verdict=verdict, score=check.score, timed_out=timed_out)

    results = await asyncio.gather(*(check_one(url) for url in body.urls))
    if format == "csv":
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(["url", "check_id", "verdict", "score", "timed_out"])
        writer.writerows([r.url, r.check_id, r.verdict, r.score, r.timed_out] for r in results)
        return Response(out.getvalue(), media_type="text/csv")
    return JSONResponse(BatchResponse(cutoff=settings.batch_cutoff, results=results).model_dump())


@v1.post("/report", response_model=ReportResponse, status_code=202)
def report(body: ReportRequest, session: SessionDep, settings: SettingsDep) -> ReportResponse:
    check = run_check(session, body.url, "user_report", "fast", settings.data_dir)
    return ReportResponse(check_id=check.id, status="received")


@v1.get("/blocklist", response_model=BlocklistResponse)
def blocklist(session: SessionDep, since: datetime | None = None) -> BlocklistResponse:
    query = select(Domain).where(Domain.status == "confirmed").order_by(Domain.updated_at)
    if since is not None:
        query = query.where(Domain.updated_at > since)
    rows = session.scalars(query).all()
    return BlocklistResponse(
        domains=[BlocklistEntry(domain=r.domain, brand_id=r.brand_id, updated_at=r.updated_at) for r in rows]
    )


@v1.post("/review/{evidence_id}", response_model=ReviewResponse, dependencies=[Depends(require_write_token)])
def review(evidence_id: str, body: ReviewRequest, session: SessionDep) -> ReviewResponse:
    if session.get(Evidence, evidence_id) is None:
        raise HTTPException(404, "Unknown evidence id")
    row = Review(evidence_id=evidence_id, decision=body.decision, reviewer=body.reviewer)
    session.add(row)
    session.commit()
    session.refresh(row)
    return ReviewResponse(
        evidence_id=evidence_id, decision=row.decision, reviewer=row.reviewer, reviewed_at=row.reviewed_at
    )


app.include_router(v1)
app.include_router(evidence_routes.export_router)
app.include_router(events.ws_router)
app.include_router(admin_router)
