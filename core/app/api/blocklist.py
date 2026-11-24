from datetime import UTC, datetime

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from sqlalchemy import select

from app import cache
from app.deps import SessionDep
from app.models import Domain
from app.schemas import BlocklistEntry, BlocklistResponse

router = APIRouter()


def entry(row: Domain) -> BlocklistEntry:
    return BlocklistEntry(domain=row.domain, brand_id=row.brand_id, updated_at=row.updated_at)


@router.get(
    "/blocklist",
    response_model=BlocklistResponse,
    description="Confirmed domains only (DNS cannot show warnings). With `since`, only changes after that time: "
    "`domains` were added or re-confirmed, `removed` were cleared by an officer. Clients poll every minute.",
)
def blocklist(session: SessionDep, since: datetime | None = None) -> BlocklistResponse:
    confirmed = select(Domain).where(Domain.status == "confirmed").order_by(Domain.updated_at)
    removed = select(Domain).where(Domain.status == "cleared").order_by(Domain.updated_at)
    if since is not None:
        confirmed = confirmed.where(Domain.updated_at > since)
        removed = removed.where(Domain.updated_at > since)
    return BlocklistResponse(
        domains=[entry(r) for r in session.scalars(confirmed)],
        removed=[entry(r) for r in session.scalars(removed)] if since is not None else [],
        version=cache.blocklist_version(),
        generated_at=datetime.now(UTC),
    )


@router.get(
    "/blocklist.txt",
    response_class=PlainTextResponse,
    description="The confirmed blocklist in adblock syntax (`||domain^`), for AdGuard Home filter subscriptions.",
)
def blocklist_txt(session: SessionDep) -> str:
    rows = session.scalars(select(Domain.domain).where(Domain.status == "confirmed").order_by(Domain.domain)).all()
    header = [
        "! Title: Kartoshka-Police confirmed scams",
        f"! Updated: {datetime.now(UTC).isoformat(timespec='seconds')}",
        f"! Entries: {len(rows)}",
    ]
    return "\n".join(header + [f"||{domain}^" for domain in rows]) + "\n"
