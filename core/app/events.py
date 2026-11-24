import json
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app import queue

CHANNEL = "kp:events"

logger = logging.getLogger(__name__)
ws_router = APIRouter(prefix="/v1")


def publish(type: str, data: dict) -> None:
    """Notify console clients. A Redis failure is logged and swallowed so it never fails the caller."""
    message = json.dumps({"type": type, "at": datetime.now(UTC).isoformat(), "data": data})
    try:
        queue.get_redis().publish(CHANNEL, message)
    except Exception:
        logger.exception("Could not publish %s event", type)


@ws_router.websocket("/events")
async def events(websocket: WebSocket) -> None:
    await websocket.accept()
    await websocket.send_json({"type": "hello"})
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        return
