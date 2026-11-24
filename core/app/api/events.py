"""Live events for the console: Redis `kp:events` forwarded over a WebSocket (docs/admin-dashboard.md).

Browsers cannot set headers on a WebSocket, so the write token comes as the `token` query parameter.
"""
import asyncio
import hmac

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app import cache
from app.config import get_settings

router = APIRouter()


def token_ok(token: str) -> bool:
    expected = get_settings().core_write_token.encode()
    return bool(expected) and hmac.compare_digest(token.encode(), expected)


@router.websocket("/events")
async def events(websocket: WebSocket, token: str = "") -> None:
    if not token_ok(token):
        await websocket.close(code=1008)
        return
    await websocket.accept()
    pubsub = cache.async_client().pubsub()
    await pubsub.subscribe(cache.EVENTS_CHANNEL)
    await websocket.send_json({"type": "hello"})

    async def forward() -> None:
        async for message in pubsub.listen():
            if message.get("type") == "message":
                await websocket.send_text(message["data"])

    async def drain() -> None:
        while True:
            await websocket.receive_text()

    tasks = [asyncio.create_task(forward()), asyncio.create_task(drain())]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    except WebSocketDisconnect:
        pass
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await pubsub.unsubscribe(cache.EVENTS_CHANNEL)
        await pubsub.aclose()
