import hmac
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app import cache
from app.config import Settings, get_settings
from app.deps import client_ip, limit, too_many

bearer = HTTPBearer(auto_error=False)
AUTH_FAIL_WINDOW_S = 600


def valid_token(given: str, settings: Settings) -> bool:
    expected = settings.core_write_token.encode()
    return bool(expected) and hmac.compare_digest(given.encode(), expected)


def accepts(request: Request, given: str | None, settings: Settings) -> bool:
    """True for the right write token, always. A wrong one is counted per address and gets 429 once over the limit."""
    if given is None:
        return False
    if valid_token(given, settings):
        return True
    key = f"kp:rate:authfail:{client_ip(request, settings)}"
    if cache.rate_limited(key, settings.auth_fail_per_10min, AUTH_FAIL_WINDOW_S):
        raise too_many("sign-in", key, AUTH_FAIL_WINDOW_S)
    return False


def require_write_token(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """Gate for every route that changes the blocklist. An unset token rejects all writes."""
    if not accepts(request, credentials.credentials if credentials else None, settings):
        raise HTTPException(401, "Missing or invalid write token", headers={"WWW-Authenticate": "Bearer"})


def address_limit(request: Request, settings: Settings, name: str, per: int, window_s: int) -> None:
    """Per-address cap for a public route. The right write token skips it; a wrong one is counted as a failed sign-in."""
    scheme, _, given = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() == "bearer" and given.strip() and accepts(request, given.strip(), settings):
        return
    limit(request, name, per, window_s, who=client_ip(request, settings))
