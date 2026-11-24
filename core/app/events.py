import asyncio
import hmac
import json
import logging
from datetime import UTC, datetime
from typing import Annotated

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from sqlalchemy import event
from sqlalchemy.orm import Session

from app import cache, queue
from app.config import Settings, get_settings
from app.deps import client_ip

CHANNEL = "kp:events"
UNAUTHORISED = 4401
TOO_MANY_ATTEMPTS = 4429
AUTH_FAIL_WINDOW_S = 600
AUTH_TIMEOUT_SECONDS = 5
PENDING = "pending_events"

logger = logging.getLogger(__name__)
ws_router = APIRouter(prefix="/v1")


def publish(type: str, data: dict) -> None:
    """Notify console clients. A Redis failure is logged and swallowed so it never fails the caller."""
    message = json.dumps({"type": type, "at": datetime.now(UTC).isoformat(), "data": data})
    try:
        queue.get_redis().publish(CHANNEL, message)
    except Exception:
        logger.exception("Could not publish %s event", type)


def publish_after_commit(session: Session, type: str, data: dict) -> None:
    """Hold an event until this session commits; a rollback discards it."""
    session.info.setdefault(PENDING, []).append((type, data))


@event.listens_for(Session, "after_commit")
def send_pending(session: Session) -> None:
    for type, data in session.info.pop(PENDING, []):
        publish(type, data)


@event.listens_for(Session, "after_soft_rollback")
def drop_pending(session: Session, previous_transaction) -> None:
    session.info.pop(PENDING, None)


async def forward(websocket: WebSocket, pubsub) -> None:
    async for message in pubsub.listen():
        await websocket.send_text(message["data"].decode())


async def presented_token(websocket: WebSocket) -> str | None:
    """The first message must be {"type": "auth", "token": ...}; the token never travels in the URL."""
    try:
        message = json.loads(await asyncio.wait_for(websocket.receive_text(), AUTH_TIMEOUT_SECONDS))
        token = message["token"]
        return token if message["type"] == "auth" and isinstance(token, str) else None
    except (TimeoutError, ValueError, KeyError, TypeError):
        return None


def refusal_code(token: str | None, expected: str, websocket: WebSocket, settings: Settings) -> int | None:
    """None when the token is right. A wrong token counts against the caller's address, like a wrong bearer."""
    if token is not None and expected and hmac.compare_digest(token.encode(), expected.encode()):
        return None
    if token is not None and limit_reached(websocket, settings):
        return TOO_MANY_ATTEMPTS
    return UNAUTHORISED


def limit_reached(websocket: WebSocket, settings: Settings) -> bool:
    address = client_ip(websocket, settings)
    return cache.rate_limited(f"kp:rate:authfail:{address}", settings.auth_fail_per_10min, AUTH_FAIL_WINDOW_S)


@ws_router.websocket("/events")
async def events(websocket: WebSocket, settings: Annotated[Settings, Depends(get_settings)]) -> None:
    await websocket.accept()
    try:
        refused = refusal_code(await presented_token(websocket), settings.core_write_token, websocket, settings)
        if refused is not None:
            await websocket.close(code=refused)
            return
        client = aioredis.from_url(settings.redis_url)
    except WebSocketDisconnect:
        return
    pubsub = client.pubsub(ignore_subscribe_messages=True)
    await pubsub.subscribe(CHANNEL)
    await websocket.send_json({"type": "hello"})
    forwarder = asyncio.create_task(forward(websocket, pubsub))
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        return
    finally:
        forwarder.cancel()
        await pubsub.aclose()
        await client.aclose()
