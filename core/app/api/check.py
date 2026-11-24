import asyncio
import csv
import io
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials

from app.auth import address_limit, bearer, require_write_token
from app.csvsafe import cell
from app.deps import HOUR, SessionDep, SettingsDep
from app.models import Check
from app.schemas import BatchRequest, BatchResponse, BatchResult, CheckRequest, Verdict, for_resident
from app.verdict.service import run_check

router = APIRouter()

MINUTE = 60
RESIDENT_SOURCES = ("browser", "gatekeeper", "share", "resident", "sms")
# The only sources an open caller may claim. Every other value (hunter, watchlist, user_report, officer, batch,
# preview, pivot, or any made-up name) is assigned by internal code and needs the write token, so a forged
# `source` cannot pass a check off as something it is not or force a deep run.
OPEN_SOURCES = (*RESIDENT_SOURCES, "api")

CHECK_NOTE = (
    "Runs the fast score (lists, verdict cache, lexical and domain features, lookups inside "
    "`FAST_LOOKUP_BUDGET_MS`) and returns `allow`, `warn` or `block`. A warn or block verdict, `mode: deep`, a "
    "hunter candidate and a user report also queue a deep analysis: `deep_status` is `queued` and the `sandbox` "
    "and `ai` sources say `running` until it finishes. Poll `GET /v1/check/{id}` for the deep result. "
    "`pending` is kept for older clients: it means no verdict yet, never safe; Gatekeeper treats it like the "
    "timeout branch of ARCHITECTURE.md section 3. Resident sources (browser, gatekeeper, share, resident, sms) "
    "get reasons without their weights. Any other source "
    "(hunter, watchlist, user_report, officer, batch, preview, pivot, ...) needs the write token."
)


def shape(check: Check, resident: bool) -> dict | Verdict:
    verdict = Verdict.model_validate(check)
    return for_resident(verdict) if resident else verdict


@router.post("/check", response_model=Verdict, description=CHECK_NOTE)
async def create_check(
    request: Request,
    body: CheckRequest,
    session: SessionDep,
    settings: SettingsDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)] = None,
):
    address_limit(request, settings, "check", settings.check_rate_per_min, MINUTE)
    if body.source not in OPEN_SOURCES:
        require_write_token(request, credentials, settings)
    check = await run_check(session, body.url, body.source, body.mode, settings, text=body.text)
    return shape(check, body.source in RESIDENT_SOURCES)


@router.get("/check/{check_id}", response_model=Verdict, description="Fetch a stored check, including its deep result once ready.")
def get_check(check_id: str, request: Request, session: SessionDep, settings: SettingsDep,
              view: Annotated[str, Query(pattern="^(full|resident)$")] = "full"):
    address_limit(request, settings, "read", settings.read_rate_per_min, MINUTE)
    check = session.get(Check, check_id)
    if check is None:
        raise HTTPException(404, "Unknown check id")
    return shape(check, view == "resident")


@router.post(
    "/batch",
    response_model=BatchResponse,
    description="Check many URLs on the fast score and return a definite `allow` or `block` for each "
    "(`block` when the score is at or above `BATCH_CUTOFF`). `timed_out` is true when a lookup missed the "
    "per-URL budget. `explain=true` adds the band, brand and reasons. Use `?format=csv` for CSV.",
)
async def batch(
    request: Request,
    body: BatchRequest,
    session: SessionDep,
    settings: SettingsDep,
    format: Annotated[str, Query(pattern="^(json|csv)$")] = "json",
    explain: bool = False,
    deep: bool = False,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)] = None,
) -> Response:
    if deep:
        require_write_token(request, credentials, settings)
    if len(body.urls) > settings.batch_max_urls:
        raise HTTPException(422, f"At most {settings.batch_max_urls} URLs per batch")
    address_limit(request, settings, "batch", settings.batch_rate_per_hour, HOUR)
    slots = asyncio.Semaphore(settings.batch_concurrency)

    async def check_one(url: str) -> BatchResult:
        async with slots:
            check = await run_check(session, url, "batch", "deep" if deep else "fast", settings,
                                    budget_ms=settings.batch_url_budget_ms, enqueue=deep)
            timed_out = any(s.get("detail") == "timeout" for s in check.sources or [])
            return BatchResult(
                url=url,
                check_id=check.id,
                verdict="block" if check.score >= settings.batch_cutoff else "allow",
                score=check.score,
                timed_out=timed_out,
                band=check.verdict if explain and check.verdict != "pending" else None,
                brand=check.brand if explain else None,
                reasons=check.reasons if explain else None,
            )

    results = await asyncio.gather(*(check_one(url) for url in body.urls))
    if format == "csv":
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(["url", "check_id", "verdict", "score", "timed_out"])
        writer.writerows(
            [cell(v) for v in (r.url, r.check_id, r.verdict, r.score, str(r.timed_out).lower())] for r in results
        )
        return Response(out.getvalue(), media_type="text/csv")
    return JSONResponse(BatchResponse(cutoff=settings.batch_cutoff, results=results).model_dump(exclude_none=not explain))
