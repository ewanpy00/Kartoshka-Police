"""Daily spend caps for the two paid paths: AI calls and deep checks. Redis counters per UTC day.

A cap that is unset means no cap and no Redis access. A cap that is set fails closed: a counter that cannot
be read counts as reached."""
from datetime import UTC, datetime

import redis

from app import cache
from app.config import Settings

EXPIRY_S = 48 * 3600


def key(name: str) -> str:
    return f"kp:budget:{name}:{datetime.now(UTC):%Y%m%d}"


def reserve(name: str, cap: int | None) -> bool:
    """Take one unit of today's budget; False when it is spent or cannot be read."""
    if cap is None:
        return True
    try:
        client = cache.sync_client()
        count = client.incr(key(name))
        client.expire(key(name), EXPIRY_S, nx=True)
        if count > cap:
            client.decr(key(name))
        return count <= cap
    except redis.RedisError:
        return False


def used(name: str) -> int | None:
    try:
        return int(cache.sync_client().get(key(name)) or 0)
    except redis.RedisError:
        return None


def entry(name: str, cap: int | None) -> dict:
    if cap is None:
        return {"used": 0, "limit": None, "reached": False}
    count = used(name)
    return {"used": count or 0, "limit": cap, "reached": count is None or count >= cap}


def status(settings: Settings) -> dict:
    return {"ai": entry("ai", settings.ai_daily_calls), "deep": entry("deep", settings.deep_daily_checks)}
