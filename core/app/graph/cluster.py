"""Campaign clustering (docs/admin-dashboard.md, "Campaign graph rules", D2).

Clustering follows strong, non-excluded edges only, and skips any entity shared by more than
`GRAPH_HUB_DEGREE` domains (the hub rule). Official and allowlisted sites (which include the Tranco
list) never join. Two or more sites sharing a strong entity form a campaign; with no officer-confirmed
site in it, the campaign is "suspected" (`confirmed_count = 0`). When a component touches several
campaigns they merge into the oldest id, and the merge is written to the audit log.

    python -m app.graph.cluster rebuild    # recompute every campaign from scratch, keeping old ids
"""
import re
import sys
import uuid
from collections import Counter
from datetime import UTC, datetime

from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session

from app import audit
from app.brands import display_name, find_brand, scoring_brands
from app.config import get_settings
from app.graph import rules
from app.models import Campaign, Check, Domain, Edge, Entity

GRAPH_LOCK = 7_301_002
MAX_DOMAINS = 500
PROTECTED = ("official", "allowlisted")
TOKEN = re.compile(r"[a-z0-9]+")


def hub_degree() -> int:
    return get_settings().graph_hub_degree


def protected_ids(session: Session, ids: set[int]) -> set[int]:
    if not ids:
        return set()
    return set(session.scalars(
        select(Entity.id).join(Domain, Domain.domain == Entity.value)
        .where(Entity.id.in_(ids), Entity.kind == "domain", Domain.status.in_(PROTECTED))
    ))


def strong_entities(session: Session, domain_ids: set[int]) -> set[int]:
    if not domain_ids:
        return set()
    return set(session.scalars(
        select(Edge.dst_id).join(Entity, Entity.id == Edge.dst_id).where(
            Edge.src_id.in_(domain_ids), Edge.strength == "strong", Edge.excluded.is_(False),
            Entity.kind.in_(rules.STRONG_KINDS), Entity.domain_count <= hub_degree())
    ))


def component(session: Session, domain_id: int) -> set[int]:
    """Domain entity ids reachable from this one through strong links."""
    if protected_ids(session, {domain_id}):
        return {domain_id}
    domains, frontier = {domain_id}, {domain_id}
    while frontier and len(domains) < MAX_DOMAINS:
        nodes = strong_entities(session, frontier)
        if not nodes:
            break
        reached = set(session.scalars(select(Edge.src_id).where(
            Edge.dst_id.in_(nodes), Edge.strength == "strong", Edge.excluded.is_(False)))) - domains
        reached -= protected_ids(session, reached)
        domains |= reached
        frontier = reached
    return domains


def campaign_of(session: Session, domain: str) -> str | None:
    return session.scalar(
        select(Edge.campaign_id).join(Entity, Entity.id == Edge.src_id)
        .where(Entity.kind == "domain", Entity.value == domain, Edge.campaign_id.is_not(None)).limit(1)
    )


def pattern(names: list[str]) -> str:
    """What the domains have in common: the tokens most of them use, and their most common TLD."""
    if not names:
        return ""
    labels = [name.rsplit(".", 1) for name in names]
    counts = Counter(token for stem, *_ in labels for token in set(TOKEN.findall(stem)) if len(token) > 2)
    common = [token for token, count in counts.most_common(3) if count * 2 >= len(names)]
    tld = Counter(parts[1] for parts in labels if len(parts) == 2).most_common(1)
    stem = "*" + "*".join(common) + "*" if common else "*"
    return stem + (f".{tld[0][0]}" if tld else "")


def describe(session: Session, campaign: Campaign, names: list[str], confirmed: set[str]) -> None:
    in_component = Check.domain.in_(names) | Check.host.in_(names)
    brand_ids = Counter(b for b in session.scalars(select(Check.brand_id).where(in_component)) if b)
    campaign.brand_id = brand_ids.most_common(1)[0][0] if brand_ids else campaign.brand_id
    campaign.domain_count = len(names)
    campaign.confirmed_count = len(confirmed)
    campaign.last_activity_at = session.scalar(select(func.max(Check.created_at)).where(in_component)) or campaign.last_activity_at
    brand = find_brand(scoring_brands(get_settings().data_dir), campaign.brand_id)
    first = campaign.first_seen or datetime.now(UTC)
    campaign.name = f"{display_name(brand) if brand else 'Unbranded'} · {pattern(names)} · since {first:%d %b %Y}"


def assign(session: Session, ids: set[int], actor: str = "system", prefer: list[Campaign] | None = None) -> Campaign | None:
    """Make `ids` (domain entity ids, two or more) one campaign: reuse the oldest, merge the rest."""
    names = list(session.scalars(select(Entity.value).where(Entity.id.in_(ids))))
    existing = prefer if prefer is not None else list(session.scalars(
        select(Campaign).join(Edge, Edge.campaign_id == Campaign.id).where(Edge.src_id.in_(ids)).distinct()))
    existing = sorted({c.id: c for c in existing}.values(), key=lambda c: c.first_seen)
    campaign = existing[0] if existing else Campaign(id=f"cmp_{uuid.uuid4().hex[:8]}", first_seen=datetime.now(UTC))
    if not existing:
        session.add(campaign)
        session.flush()
    merged = existing[1:]
    for other in merged:
        session.execute(update(Edge).where(Edge.campaign_id == other.id).values(campaign_id=campaign.id))
        session.execute(update(Check).where(Check.campaign_id == other.id).values(campaign_id=campaign.id))
        session.delete(other)
    if merged:
        audit.record(session, actor, "campaign.merge", "campaign", campaign.id,
                     {"campaigns": [c.id for c in existing]}, {"campaign": campaign.id}, "shared strong link")
    session.execute(update(Edge).where(Edge.src_id.in_(ids)).values(campaign_id=campaign.id))
    session.execute(update(Check).where(Check.domain.in_(names) | Check.host.in_(names)).values(campaign_id=campaign.id))
    confirmed = set(session.scalars(select(Domain.domain).where(Domain.domain.in_(names), Domain.status == "confirmed")))
    describe(session, campaign, names, confirmed)
    session.flush()
    return campaign


def detach(session: Session, domain_id: int) -> None:
    """A site that no longer shares a strong link with anyone leaves its campaign."""
    name = session.scalar(select(Entity.value).where(Entity.id == domain_id))
    old = campaign_of(session, name) if name else None
    if old is None:
        return
    session.execute(update(Edge).where(Edge.src_id == domain_id).values(campaign_id=None))
    session.execute(update(Check).where((Check.domain == name) | (Check.host == name), Check.campaign_id == old).values(campaign_id=None))
    rest = set(session.scalars(select(Edge.src_id).where(Edge.campaign_id == old).distinct()))
    campaign = session.get(Campaign, old)
    if len(rest) < 2:
        session.execute(update(Edge).where(Edge.campaign_id == old).values(campaign_id=None))
        session.execute(update(Check).where(Check.campaign_id == old).values(campaign_id=None))
        session.delete(campaign)
    else:
        names = list(session.scalars(select(Entity.value).where(Entity.id.in_(rest))))
        confirmed = set(session.scalars(select(Domain.domain).where(Domain.domain.in_(names), Domain.status == "confirmed")))
        describe(session, campaign, names, confirmed)
    session.flush()


def refresh(session: Session, domain: str, actor: str = "system") -> Campaign | None:
    """Recompute the campaign of the site's component and stamp it on edges and checks. The caller commits."""
    session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": GRAPH_LOCK})
    start = session.scalar(select(Entity.id).where(Entity.kind == "domain", Entity.value == domain))
    if start is None:
        return None
    ids = component(session, start)
    if len(ids) < 2:
        detach(session, start)
        return None
    return assign(session, ids, actor)


def rebuild(session: Session) -> dict:
    """Recompute entity degrees and every campaign from strong edges, keeping the oldest existing ids."""
    session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": GRAPH_LOCK})
    session.execute(update(Edge).where(
        Edge.dst_id.in_(select(Entity.id).where(Entity.kind.in_(rules.LEGACY_WEAK + rules.WEAK_KINDS)))).values(strength="weak"))
    session.execute(text(
        "UPDATE entities SET domain_count = coalesce((SELECT count(DISTINCT src_id) FROM edges WHERE dst_id = entities.id), 0)"))
    previous: dict[int, Campaign] = {}
    for src_id, campaign_id in session.execute(select(Edge.src_id, Edge.campaign_id).where(Edge.campaign_id.is_not(None)).distinct()):
        previous[src_id] = session.get(Campaign, campaign_id)
    session.execute(update(Edge).values(campaign_id=None))
    session.execute(update(Check).values(campaign_id=None))
    done: set[int] = set()
    kept: set[str] = set()
    domains = list(session.scalars(select(Entity.id).where(Entity.kind == "domain").order_by(Entity.id)))
    for domain_id in domains:
        if domain_id in done:
            continue
        ids = component(session, domain_id)
        done |= ids
        if len(ids) < 2:
            continue
        prefer = [previous[i] for i in ids if i in previous and previous[i] is not None and previous[i].id not in kept]
        campaign = assign(session, ids, "rebuild", prefer=prefer[:1])
        kept.add(campaign.id)
    for campaign in session.scalars(select(Campaign)).all():
        if campaign.id not in kept:
            session.delete(campaign)
    session.flush()
    return {"campaigns": len(kept), "domains": len(domains)}


def main(argv: list[str]) -> int:
    from app.db import get_engine

    if argv[:1] != ["rebuild"]:
        print("usage: python -m app.graph.cluster rebuild")
        return 2
    with Session(get_engine()) as session:
        result = rebuild(session)
        session.commit()
    print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
