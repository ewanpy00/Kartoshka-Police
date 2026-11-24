"""Campaign graph (ARCHITECTURE.md 1.6).

Every deep analysis adds edges from its domain to the infrastructure it uses. Domains that share a
linking node (a dedicated IP, a custom name server, a certificate, a kit, a favicon, a phone number,
a payment host) form a component; a component of two or more domains with at least one confirmed scam
is a campaign. ASNs, registrars, CDN addresses and big DNS providers are recorded but do not link, and
any node shared by more than MAX_DEGREE domains stops linking: unrelated sites share those all the time.
"""
import uuid
from collections import Counter

from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.brands import display_name, find_brand, load_brands
from app.config import get_settings
from app.models import Campaign, Check, Domain, Edge, Entity

LINKING = ("ip", "ns", "cert", "kit_hash", "favicon_hash", "phone", "payment")
MAX_DEGREE = 50
MAX_DOMAINS = 500
GRAPH_LOCK = 7_301_002


def entity_id(session: Session, kind: str, value: str) -> int:
    statement = insert(Entity).values(kind=kind, value=value).on_conflict_do_nothing(index_elements=[Entity.kind, Entity.value])
    session.execute(statement)
    return session.scalar(select(Entity.id).where(Entity.kind == kind, Entity.value == value))


def record(session: Session, domain: str, nodes: list[tuple[str, str]], evidence_id: str | None) -> int:
    """Edges from the domain to each (kind, value) node. Returns the domain's entity id."""
    source = entity_id(session, "domain", domain)
    for kind, value in dict.fromkeys(nodes):
        if not value or (kind, value) == ("domain", domain):
            continue
        target = entity_id(session, kind, str(value)[:500])
        session.execute(
            insert(Edge).values(src_id=source, dst_id=target, evidence_id=evidence_id)
            .on_conflict_do_nothing(index_elements=[Edge.src_id, Edge.dst_id])
        )
    return source


def linking_neighbours(session: Session, domain_ids: set[int]) -> set[int]:
    if not domain_ids:
        return set()
    candidates = select(Edge.dst_id).join(Entity, Entity.id == Edge.dst_id).where(
        Edge.src_id.in_(domain_ids), Entity.kind.in_(LINKING)
    )
    degree = (
        select(Edge.dst_id)
        .where(Edge.dst_id.in_(candidates))
        .group_by(Edge.dst_id)
        .having(func.count(Edge.src_id) <= MAX_DEGREE)
    )
    return set(session.scalars(degree))


def component(session: Session, domain_id: int) -> set[int]:
    """Domain entity ids reachable through linking nodes."""
    domains, frontier = {domain_id}, {domain_id}
    while frontier and len(domains) < MAX_DOMAINS:
        nodes = linking_neighbours(session, frontier)
        if not nodes:
            break
        reached = set(session.scalars(select(Edge.src_id).where(Edge.dst_id.in_(nodes)))) - domains
        domains |= reached
        frontier = reached
    return domains


def shared_nodes(session: Session, domain_id: int, others: set[int]) -> list[tuple[str, str]]:
    """The linking nodes this domain shares with the rest of its component, for the CAMPAIGN_LINK text."""
    if not others:
        return []
    mine = select(Edge.dst_id).where(Edge.src_id == domain_id)
    theirs = select(Edge.dst_id).where(Edge.src_id.in_(others))
    rows = session.execute(
        select(Entity.kind, Entity.value).where(Entity.id.in_(mine), Entity.id.in_(theirs), Entity.kind.in_(LINKING))
    ).all()
    return [tuple(row) for row in rows]


def campaign_of(session: Session, domain: str) -> str | None:
    return session.scalar(
        select(Edge.campaign_id).join(Entity, Entity.id == Edge.src_id)
        .where(Entity.kind == "domain", Entity.value == domain, Edge.campaign_id.is_not(None)).limit(1)
    )


def refresh(session: Session, domain: str) -> Campaign | None:
    """Recompute the campaign of the domain's component and stamp it on edges and checks. The caller commits."""
    session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": GRAPH_LOCK})
    start = session.scalar(select(Entity.id).where(Entity.kind == "domain", Entity.value == domain))
    if start is None:
        return None
    ids = component(session, start)
    names = list(session.scalars(select(Entity.value).where(Entity.id.in_(ids))))
    confirmed = set(session.scalars(select(Domain.domain).where(Domain.domain.in_(names), Domain.status == "confirmed")))
    existing = list(session.scalars(
        select(Campaign).join(Edge, Edge.campaign_id == Campaign.id).where(Edge.src_id.in_(ids)).distinct()
    ))
    if len(ids) < 2 or (not confirmed and not existing):
        return None

    existing.sort(key=lambda c: c.first_seen)
    campaign = existing[0] if existing else Campaign(id=f"cmp_{uuid.uuid4().hex[:8]}")
    if not existing:
        session.add(campaign)
        session.flush()
    for merged in existing[1:]:
        session.execute(update(Edge).where(Edge.campaign_id == merged.id).values(campaign_id=campaign.id))
        session.execute(update(Check).where(Check.campaign_id == merged.id).values(campaign_id=campaign.id))
        session.delete(merged)

    session.execute(update(Edge).where(Edge.src_id.in_(ids)).values(campaign_id=campaign.id))
    in_component = Check.domain.in_(names) | Check.host.in_(names)
    session.execute(update(Check).where(in_component).values(campaign_id=campaign.id))
    brand_ids = Counter(b for b in session.scalars(select(Check.brand_id).where(in_component)) if b)
    campaign.brand_id = brand_ids.most_common(1)[0][0] if brand_ids else campaign.brand_id
    campaign.domain_count = len(ids)
    campaign.confirmed_count = len(confirmed)
    brand = find_brand(load_brands(get_settings().data_dir), campaign.brand_id)
    lead = sorted(confirmed)[0] if confirmed else sorted(names)[0]
    label = display_name(brand) if brand else "Scam"
    campaign.name = f"{label}: {lead}" + (f" and {len(ids) - 1} more" if len(ids) > 1 else "")
    session.flush()
    return campaign
