"""Redis helpers: JSON cache, verdict-cache version, rate limits, events. Sync and async clients."""
import json
from functools import lru_cache

import redis
import redis.asyncio as aredis

from app.config import get_settings

VERSION_KEY = "kp:blocklist_version"
EVENTS_CHANNEL = "kp:events"


@lru_cache
def sync_client() -> redis.Redis:
    return redis.Redis.from_url(get_settings().redis_url, socket_connect_timeout=2, decode_responses=True)


_async_clients: dict[int, aredis.Redis] = {}


def async_client() -> aredis.Redis:
    """One async client per event loop (tests and workers create several loops)."""
    import asyncio

    loop_id = id(asyncio.get_running_loop())
    if loop_id not in _async_clients:
        _async_clients[loop_id] = aredis.Redis.from_url(
            get_settings().redis_url, socket_connect_timeout=2, decode_responses=True
        )
    return _async_clients[loop_id]


async def get_json(key: str):
    try:
        raw = await async_client().get(key)
    except redis.RedisError:
        return None
    return json.loads(raw) if raw else None


async def set_json(key: str, value, ttl_s: int) -> None:
    try:
        await async_client().set(key, json.dumps(value, default=str), ex=ttl_s)
    except redis.RedisError:
        pass


def get_json_sync(key: str):
    try:
        raw = sync_client().get(key)
    except redis.RedisError:
        return None
    return json.loads(raw) if raw else None


def set_json_sync(key: str, value, ttl_s: int) -> None:
    try:
        sync_client().set(key, json.dumps(value, default=str), ex=ttl_s)
    except redis.RedisError:
        pass


def blocklist_version() -> int:
    try:
        return int(sync_client().get(VERSION_KEY) or 0)
    except redis.RedisError:
        return 0


def bump_blocklist_version() -> None:
    try:
        sync_client().incr(VERSION_KEY)
    except redis.RedisError:
        pass


def rate_limited(key: str, limit: int, window_s: int) -> bool:
    """Fixed-window counter. Fails open if redis is down."""
    try:
        client = sync_client()
        count = client.incr(key)
        if count == 1:
            client.expire(key, window_s)
        return count > limit
    except redis.RedisError:
        return False


def publish(event: dict) -> None:
    try:
        sync_client().publish(EVENTS_CHANNEL, json.dumps(event, default=str))
    except redis.RedisError:
        pass


def sync_client_once(key: str, ttl_s: int) -> bool:
    """True the first time `key` is claimed within `ttl_s` (used to announce a brand spike once an hour)."""
    try:
        return bool(sync_client().set(key, "1", nx=True, ex=ttl_s))
    except redis.RedisError:
        return False
