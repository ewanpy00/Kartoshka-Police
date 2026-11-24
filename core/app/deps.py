from typing import Annotated

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session
from starlette.requests import HTTPConnection

from app import cache
from app.config import Settings, get_settings
from app.db import get_session

SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
HOUR = 3600


def client_ip(request: HTTPConnection, settings: Settings) -> str:
    """The caller's address. `X-Real-IP` only when the deployment says a proxy sets it; `X-Forwarded-For` is never read."""
    real = request.headers.get("x-real-ip", "").strip()
    if settings.trust_proxy and real:
        return real
    return request.client.host if request.client else "unknown"


def client_key(request: HTTPConnection) -> str:
    """Rate-limit key: the device header the apps send (random, not an identity), else the client address."""
    device = request.headers.get("x-device-id", "")[:64]
    if device:
        return f"d:{device}"
    return f"ip:{client_ip(request, get_settings())}"


def too_many(name: str, key: str, window_s: int) -> HTTPException:
    return HTTPException(429, f"Too many {name} requests; try again later",
                         headers={"Retry-After": str(cache.rate_ttl(key, window_s))})


def limit(request: HTTPConnection, name: str, per: int, window_s: int = HOUR, who: str | None = None) -> None:
    """Count one request in a fixed window; 429 with `Retry-After` once over. `who` defaults to the device key."""
    key = f"kp:rate:{name}:{who or client_key(request)}"
    if cache.rate_limited(key, per, window_s):
        raise too_many(name, key, window_s)
