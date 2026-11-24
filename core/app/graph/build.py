"""Campaign graph, storage side (ARCHITECTURE.md 1.6): entities and edges.

Every deep analysis adds an edge from its site to each entity it uses (IP, certificate, kit, favicon,
phone, WhatsApp number, payment endpoint, ASN, registrar, name server). Each edge carries a strength
from `app.graph.rules`; `app.graph.cluster` turns strong edges into campaigns.
"""
from collections.abc import Callable

import phonenumbers
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.brands import load_brands
from app.config import get_settings
from app.graph import rules
from app.graph.cluster import GRAPH_LOCK, PROTECTED, campaign_of, refresh  # noqa: F401  (re-exported)
from app.models import Domain, Edge, Entity

LINKING = rules.LINKING
# Display-only facts that are never nodes. A country says nothing about who runs a site.
NOT_ENTITIES = ("country",)


def e164(raw: str) -> str:
    try:
        return phonenumbers.format_number(phonenumbers.parse(raw, "AE"), phonenumbers.PhoneNumberFormat.E164)
    except phonenumbers.NumberParseException:
        return raw


def official_phones() -> frozenset[str]:
    """E.164 numbers the brands publish. A missing `app.brands.official_phones` counts as none."""
    try:
        from app.brands import official_phones as published
    except ImportError:
        return frozenset()
    return frozenset(published())


def official_contact(session: Session) -> Callable[[str, str], bool]:
    """True for a brand's real phone number or WhatsApp number, and for a payment endpoint on an official or
    allowlisted host. Those are printed on scam pages too and must never link unrelated sites."""
    phones = official_phones()
    hosts = {d for brand in load_brands(get_settings().data_dir) for d in brand.get("official_domains", [])}
    hosts |= set(session.scalars(select(Domain.domain).where(Domain.status.in_(PROTECTED))))

    def is_official(kind: str, value: str) -> bool:
        if kind in ("phone", "whatsapp"):
            return e164(value) in phones
        if kind == "payment":
            host = value.split("/", 1)[0].lower()
            return any(host == h or host.endswith(f".{h}") for h in hosts)
        return False

    return is_official


def entity_id(session: Session, kind: str, value: str) -> int:
    statement = insert(Entity).values(kind=kind, value=value).on_conflict_do_nothing(index_elements=[Entity.kind, Entity.value])
    session.execute(statement)
    return session.scalar(select(Entity.id).where(Entity.kind == kind, Entity.value == value))


def record(session: Session, domain: str, nodes: list[tuple], evidence_id: str | None) -> int:
    """Edges from the site to each node: (kind, value) or (kind, value, strength). Returns the site's entity id.
    A new edge raises the entity's `domain_count`, which the hub rule reads."""
    source = entity_id(session, "domain", domain)
    official = official_contact(session)
    seen = set()
    for node in nodes:
        kind, value = node[0], str(node[1])[:500] if node[1] else node[1]
        if not value or kind in NOT_ENTITIES or (kind, value) == ("domain", domain) or (kind, value) in seen:
            continue
        if official(kind, value):
            continue
        seen.add((kind, value))
        strength = node[2] if len(node) > 2 else rules.strength(kind, value)
        target = entity_id(session, kind, value)
        created = session.execute(
            insert(Edge).values(src_id=source, dst_id=target, evidence_id=evidence_id, strength=strength)
            .on_conflict_do_nothing(index_elements=[Edge.src_id, Edge.dst_id]).returning(Edge.id)
        ).first()
        if created is not None:
            session.execute(update(Entity).where(Entity.id == target).values(domain_count=Entity.domain_count + 1))
    return source
