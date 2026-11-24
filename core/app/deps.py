from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_session

SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def client_key(request: Request) -> str:
    """Rate-limit key: the device header the apps send (random, not an identity), else the client address."""
    device = request.headers.get("x-device-id", "")[:64]
    if device:
        return f"d:{device}"
    return f"ip:{request.client.host if request.client else 'unknown'}"
