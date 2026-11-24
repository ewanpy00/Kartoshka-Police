import asyncio
import hmac
import json
import logging
from datetime import UTC, datetime
from typing import Annotated

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from app import queue
from app.config import Settings, get_settings

CHANNEL = "kp:events"
UNAUTHORISED = 4401

logger = logging.getLogger(__name__)
ws_router = APIRouter(prefix="/v1")


def publish(type: str, data: dict) -> None:
    """Notify console clients. A Redis failure is logged and swallowed so it never fails the caller."""
    message = json.dumps({"type": type, "at": datetime.now(UTC).isoformat(), "data": data})
    try:
        queue.get_redis().publish(CHANNEL, message)
    except Exception:
        logger.exception("Could not publish %s event", type)


async def forward(websocket: WebSocket, pubsub) -> None:
    async for message in pubsub.listen():
        await websocket.send_text(message["data"].decode())


@ws_router.websocket("/events")
async def events(websocket: WebSocket, settings: Annotated[Settings, Depends(get_settings)], token: str = "") -> None:
    expected = settings.core_write_token
    if not expected or not hmac.compare_digest(token.encode(), expected.encode()):
        await websocket.close(code=UNAUTHORISED)
        return
    await websocket.accept()
    client = aioredis.from_url(settings.redis_url)
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
