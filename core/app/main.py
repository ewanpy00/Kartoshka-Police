import logging

from fastapi import APIRouter, Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text

from app import queue
from app.api import blocklist, check
from app.auth import require_write_token
from app.deps import SessionDep, SettingsDep
from app.models import Evidence, Review
from app.schemas import EvidenceResponse, Health, ReportRequest, ReportResponse, ReviewRequest, ReviewResponse
from app.verdict.service import run_check

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

app = FastAPI(
    title="Kartoshka Core",
    version="0.2.0",
    description="Link Intelligence Engine: one verdict format for Gatekeeper, DNS Shield, the hunter, the "
    "officer console, the resident screens and the judges' batch route.",
)
v1 = APIRouter(prefix="/v1")


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


@v1.post("/report", response_model=ReportResponse, status_code=202)
async def report(body: ReportRequest, session: SessionDep, settings: SettingsDep) -> ReportResponse:
    check_row = await run_check(session, body.url, "user_report", "deep", settings)
    return ReportResponse(check_id=check_row.id, status="received")


@v1.post("/review/{evidence_id}", response_model=ReviewResponse, dependencies=[Depends(require_write_token)])
def review(evidence_id: str, body: ReviewRequest, session: SessionDep) -> ReviewResponse:
    if session.get(Evidence, evidence_id) is None:
        raise HTTPException(404, "Unknown evidence id")
    row = Review(evidence_id=evidence_id, decision=body.decision, reviewer=body.reviewer)
    session.add(row)
    session.commit()
    session.refresh(row)
    return ReviewResponse(evidence_id=evidence_id, decision=row.decision, reviewer=row.reviewer, reviewed_at=row.reviewed_at)


@v1.get("/evidence/{evidence_id}.json", response_model=EvidenceResponse)
def evidence_json(evidence_id: str, session: SessionDep) -> Evidence:
    evidence = session.get(Evidence, evidence_id)
    if evidence is None:
        raise HTTPException(404, "Unknown evidence id")
    return evidence


@v1.websocket("/events")
async def events(websocket: WebSocket) -> None:
    await websocket.accept()
    await websocket.send_json({"type": "hello"})
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        return


v1.include_router(check.router)
v1.include_router(blocklist.router)
app.include_router(v1)
