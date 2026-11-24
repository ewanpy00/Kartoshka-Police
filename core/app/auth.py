import hmac
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings, get_settings

bearer = HTTPBearer(auto_error=False)


def require_write_token(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    """Gate for every route that changes the blocklist. An unset token rejects all writes."""
    expected = settings.core_write_token.encode()
    given = credentials.credentials.encode() if credentials else b""
    if not expected or not hmac.compare_digest(given, expected):
        raise HTTPException(401, "Missing or invalid write token", headers={"WWW-Authenticate": "Bearer"})
