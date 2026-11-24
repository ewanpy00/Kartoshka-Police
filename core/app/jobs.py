import httpx
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.db import get_engine
from app.models import Check


def deep_check(check_id: str) -> None:
    settings = get_settings()
    with sessionmaker(get_engine())() as session:
        check = session.get(Check, check_id)
        response = httpx.post(f"{settings.sandbox_url}/capture", json={"url": check.url}, timeout=30)
        response.raise_for_status()
        capture = response.json()
        check.internal_requests_blocked = capture["internal_requests_blocked"]
        check.navigation_blocked = capture["navigation_blocked"]
        if not capture["navigation_blocked"]:
            check.final_url = capture["final_url"]
        session.commit()
