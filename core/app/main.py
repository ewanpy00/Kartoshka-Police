import logging

from fastapi import APIRouter, FastAPI
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text

from app import queue
from app.api import admin, admin_campaigns, blocklist, check, events, evidence, intel, resident, review
from app.deps import SessionDep
from app.schemas import Health

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

app = FastAPI(
    title="Kartoshka Core",
    version="0.3.0",
    description="Link Intelligence Engine: one verdict format for Gatekeeper, DNS Shield, the hunter, the "
    "officer console, the resident screens and the judges' batch route. Routes that change data or expose "
    "officer views need the write token; resident routes are rate-limited per device.",
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


for module in (check, blocklist, resident, review, evidence, events, intel, admin, admin_campaigns):
    v1.include_router(module.router)
app.include_router(v1)
