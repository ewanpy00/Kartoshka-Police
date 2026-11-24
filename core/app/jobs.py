"""Background jobs that are not the deep check (that one is app.deep.job.deep_check). Run by the worker."""
from sqlalchemy.orm import Session

from app.db import get_engine


def takedown_recheck(domain: str) -> dict:
    """Probe a domain with an open takedown (both sandbox profiles, DNS and RDAP) and move its requests."""
    from app.takedown import tracker

    with Session(get_engine()) as session:
        result = tracker.recheck(session, domain)
        session.commit()
        tracker.publish(result.get("events") or [], session)
    return result
