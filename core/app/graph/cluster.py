import uuid
from datetime import UTC, datetime

import phonenumbers
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app import events
from app.admin import audit
from app.admin.review import PROTECTED, resolve_brand_id
from app.brands import load_brands
from app.config import get_settings
from app.graph.entities import edge_strength, entities_of
from app.models import Campaign, Check, Domain, Edge, Entity, Evidence


def e164(raw: str) -> str:
    try:
        return phonenumbers.format_number(phonenumbers.parse(raw, "AE"), phonenumbers.PhoneNumberFormat.E164)
    except phonenumbers.NumberParseException:
        return raw


def official_contact(session: Session):
    """A predicate for brand hotlines and for payment hosts that are official or allowlisted."""
    brands = load_brands(get_settings().data_dir)
    phones = {e164(phone) for brand in brands for phone in brand.get("official_phones", [])}
    hosts = {host for brand in brands for host in brand["official_domains"]}
    hosts |= set(session.scalars(select(Domain.domain).where(Domain.status.in_(PROTECTED))))

    def is_official(kind: str, value: str) -> bool:
        if kind in ("phone", "whatsapp"):
            return e164(value) in phones
        return kind == "payment" and any(value == host or value.endswith(f".{host}") for host in hosts)

    return is_official


def upsert_entity(session: Session, kind: str, value: str) -> Entity:
    entity = session.scalars(select(Entity).where(Entity.kind == kind, Entity.value == value)).first()
    if entity is None:
        entity = Entity(kind=kind, value=value, domain_count=0)
        session.add(entity)
        session.flush()
    return entity


def link(session: Session, domain: Entity, other: Entity, evidence_id: str, strength: str, hub_threshold: int) -> None:
    """Add the edge if missing, then recount the entity's domains and weaken all its edges if it became a hub."""
    exists = session.scalars(select(Edge.id).where(Edge.src_id == domain.id, Edge.dst_id == other.id)).first()
    if exists is None:
        session.add(Edge(src_id=domain.id, dst_id=other.id, evidence_id=evidence_id, strength=strength))
        session.flush()
    other.domain_count = session.scalar(select(func.count(func.distinct(Edge.src_id))).where(Edge.dst_id == other.id))
    if other.domain_count > hub_threshold:
        session.execute(update(Edge).where(Edge.dst_id == other.id).values(strength="weak"))


def linked_domains(session: Session, domain: Entity) -> list[Entity]:
    """Other domain entities that share a strong, non-hub entity with this one."""
    shared = select(Edge.dst_id).where(Edge.src_id == domain.id, Edge.strength == "strong")
    sources = select(Edge.src_id).where(Edge.dst_id.in_(shared), Edge.strength == "strong", Edge.src_id != domain.id)
    return list(session.scalars(select(Entity).where(Entity.id.in_(sources)).order_by(Entity.id)))


def campaign_name(brand: str | None, first_domain: str, now: datetime) -> str:
    return " · ".join([*([brand.upper()] if brand else []), first_domain, f"{now.day} {now:%B}"])


def merge(session: Session, campaign_ids: set[str]) -> Campaign:
    """Fold the given campaigns into the oldest one and audit it."""
    campaigns = list(session.scalars(select(Campaign).where(Campaign.id.in_(campaign_ids)).order_by(Campaign.first_seen, Campaign.id)))
    winner, losers = campaigns[0], [c.id for c in campaigns[1:]]
    if losers:
        for model in (Entity, Edge, Check):
            session.execute(update(model).where(model.campaign_id.in_(losers)).values(campaign_id=winner.id))
        session.flush()
        for campaign in campaigns[1:]:
            session.delete(campaign)
        audit.record(session, "system", "campaign.merge", winner.id, before={"campaigns": [winner.id, *losers]}, after={"campaign": winner.id})
    return winner


def ingest_evidence(session: Session, evidence_id: str, hub_threshold: int | None = None) -> None:
    """Add the entities and edges of one evidence record and cluster its domain. The caller commits."""
    hub_threshold = get_settings().hub_threshold if hub_threshold is None else hub_threshold
    payload = session.get(Evidence, evidence_id).payload
    domain = None
    for kind, value in entities_of(payload, official_contact(session)):
        entity = upsert_entity(session, kind, value)
        if kind == "domain":
            domain = entity
        else:
            link(session, domain, entity, evidence_id, edge_strength(kind, payload), hub_threshold)
    others = linked_domains(session, domain)
    campaign_ids = {e.campaign_id for e in [domain, *others] if e.campaign_id}
    if not others and not campaign_ids:
        return
    now = datetime.now(UTC)
    brand_name = payload["scam"].get("brand")
    brand_id = resolve_brand_id(brand_name)
    if campaign_ids:
        campaign = merge(session, campaign_ids)
    else:
        campaign = Campaign(id=f"cmp_{uuid.uuid4().hex}", name=campaign_name(brand_name, others[0].value, now), first_seen=now)
        session.add(campaign)
        session.flush()
    campaign.brand_id = campaign.brand_id or brand_id
    campaign.last_activity_at = now
    members = [domain, *others]
    for member in members:
        member.campaign_id = campaign.id
    session.flush()
    session.execute(update(Edge).where(Edge.src_id.in_([m.id for m in members])).values(campaign_id=campaign.id))
    session.execute(update(Check).where(Check.domain.in_([m.value for m in members])).values(campaign_id=campaign.id))
    events.publish_after_commit(session, "campaign.new_domain", {"campaign_id": campaign.id, "domain": domain.value})
