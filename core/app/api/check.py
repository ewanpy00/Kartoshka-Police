import asyncio
import csv
import io
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials

from app.auth import bearer, require_write_token
from app.csvsafe import cell
from app.deps import SessionDep, SettingsDep
from app.models import Check
from app.schemas import BatchRequest, BatchResponse, BatchResult, CheckRequest, Verdict, for_resident
from app.verdict.service import run_check

router = APIRouter()

RESIDENT_SOURCES = ("browser", "gatekeeper", "share", "resident", "sms")
# Sources the core itself assigns to privileged traffic. A caller cannot claim one without the write token,
# so a forged `source` cannot pass a resident's check off as a hunter find, an officer run or a batch row.
RESERVED_SOURCES = ("hunter", "watchlist", "user_report", "officer", "batch")

CHECK_NOTE = (
    "Runs the fast score (lists, verdict cache, lexical and domain features, lookups inside "
    "`FAST_LOOKUP_BUDGET_MS`) and returns `allow`, `warn` or `block`. A warn or block verdict, `mode: deep`, a "
    "hunter candidate and a user report also queue a deep analysis: `deep_status` is `queued` and the `sandbox` "
    "and `ai` sources say `running` until it finishes. Poll `GET /v1/check/{id}` for the deep result. "
    "`pending` is kept for older clients: it means no verdict yet, never safe; Gatekeeper treats it like the "
    "timeout branch of ARCHITECTURE.md section 3. Resident sources (browser, gatekeeper, share, resident, sms) "
    "get reasons without their weights. The sources hunter, watchlist, user_report, officer and batch are "
    "reserved and need the write token."
)


def shape(check: Check, resident: bool) -> dict | Verdict:
    verdict = Verdict.model_validate(check)
    return for_resident(verdict) if resident else verdict


@router.post("/check", response_model=Verdict, description=CHECK_NOTE)
async def create_check(
    body: CheckRequest,
    session: SessionDep,
    settings: SettingsDep,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)] = None,
):
    if body.source in RESERVED_SOURCES:
        require_write_token(credentials, settings)
    check = await run_check(session, body.url, body.source, body.mode, settings, text=body.text)
    return shape(check, body.source in RESIDENT_SOURCES)


@router.get("/check/{check_id}", response_model=Verdict, description="Fetch a stored check, including its deep result once ready.")
def get_check(check_id: str, session: SessionDep, view: Annotated[str, Query(pattern="^(full|resident)$")] = "full"):
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
    body: BatchRequest,
    session: SessionDep,
    settings: SettingsDep,
    format: Annotated[str, Query(pattern="^(json|csv)$")] = "json",
    explain: bool = False,
    deep: bool = False,
) -> Response:
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
