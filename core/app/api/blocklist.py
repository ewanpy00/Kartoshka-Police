from datetime import UTC, datetime

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy import select

from app import cache
from app.auth import address_limit
from app.deps import SessionDep, SettingsDep
from app.models import Domain
from app.schemas import BlocklistEntry, BlocklistResponse

router = APIRouter()
MINUTE = 60


def entry(row: Domain) -> BlocklistEntry:
    return BlocklistEntry(domain=row.domain, brand_id=row.brand_id, updated_at=row.updated_at)


@router.get(
    "/blocklist",
    response_model=BlocklistResponse,
    description="Confirmed domains only (DNS cannot show warnings). With `since`, only changes after that time: "
    "`domains` were added or re-confirmed, `removed` were cleared by an officer. Clients poll every minute.",
)
def blocklist(request: Request, session: SessionDep, settings: SettingsDep, since: datetime | None = None) -> BlocklistResponse:
    address_limit(request, settings, "blocklist", settings.blocklist_rate_per_min, MINUTE)
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
def blocklist_txt(request: Request, session: SessionDep, settings: SettingsDep) -> str:
    address_limit(request, settings, "blocklist", settings.blocklist_rate_per_min, MINUTE)
    rows = session.scalars(select(Domain.domain).where(Domain.status == "confirmed").order_by(Domain.domain)).all()
    header = [
        "! Title: Kartoshka-Police confirmed scams",
        f"! Updated: {datetime.now(UTC).isoformat(timespec='seconds')}",
        f"! Entries: {len(rows)}",
    ]
    return "\n".join(header + [f"||{domain}^" for domain in rows]) + "\n"
