"""Lookups against our own data: decided domains, hunter feeds, CT sightings, campaign infrastructure."""
import asyncio
from datetime import UTC, datetime

import dns.asyncresolver
import dns.exception
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Campaign, Domain, Edge, Entity, FeedEntry
from app.normalize.url import host_and_parents

THREAT_FEEDS = ("openphish", "urlhaus", "phishtank", "phishing_army")


def lookup_domain(session: Session, host: str) -> Domain | None:
    """Official and confirmed entries match the host or a parent; allowlisted and cleared ones only the host or its www form."""
    candidates = host_and_parents(f"http://{host}/")
    exact = candidates[0]
    rows = session.scalars(select(Domain).where(Domain.domain.in_(candidates))).all()
    matches = [
        row for row in rows
        if row.status in ("official", "confirmed") or exact in (row.domain, f"www.{row.domain}")
    ]
    return max(matches, key=lambda row: (row.status == "confirmed", len(row.domain)), default=None)


def feed_hits(session: Session, domain: str, url: str) -> list[FeedEntry]:
    return session.scalars(
        select(FeedEntry)
        .where(FeedEntry.source.in_(THREAT_FEEDS))
        .where((FeedEntry.domain == domain) | (FeedEntry.url == url))
        .limit(5)
    ).all()


def first_sighting(session: Session, domain: str, source: str) -> datetime | None:
    return session.scalar(
        select(FeedEntry.first_seen).where(FeedEntry.source == source, FeedEntry.domain == domain)
        .order_by(FeedEntry.first_seen).limit(1)
    )


def hours_since(when: datetime | None) -> float | None:
    if when is None:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return max(0.0, (datetime.now(UTC) - when).total_seconds() / 3600)


def campaign_links(session: Session, entities: list[tuple[str, str]]) -> list[tuple[str, str, Campaign]]:
    """Which of these (kind, value) nodes already sit on an edge of a campaign with a confirmed scam."""
    if not entities:
        return []
    found = []
    for kind, value in entities:
        row = session.execute(
            select(Entity, Campaign)
            .join(Edge, (Edge.dst_id == Entity.id) | (Edge.src_id == Entity.id))
            .join(Campaign, Campaign.id == Edge.campaign_id)
            .where(Entity.kind == kind, Entity.value == value, Campaign.confirmed_count > 0)
            .limit(1)
        ).first()
        if row:
            found.append((kind, value, row[1]))
    return found


async def resolve_a(host: str, timeout_s: float) -> list[str]:
    resolver = dns.asyncresolver.Resolver()
    resolver.lifetime = timeout_s
    try:
        answer = await resolver.resolve(host, "A")
    except (dns.exception.DNSException, asyncio.TimeoutError):
        return []
    return sorted({rr.address for rr in answer})
