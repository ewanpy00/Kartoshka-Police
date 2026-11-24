"""Campaign graph, storage side (ARCHITECTURE.md 1.6): entities and edges.

Every deep analysis adds an edge from its site to each entity it uses (IP, certificate, kit, favicon,
phone, WhatsApp number, payment endpoint, ASN, registrar, name server). Each edge carries a strength
from `app.graph.rules`; `app.graph.cluster` turns strong edges into campaigns.
"""
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.graph import rules
from app.graph.cluster import GRAPH_LOCK, campaign_of, refresh  # noqa: F401  (re-exported)
from app.models import Edge, Entity

LINKING = rules.LINKING


def entity_id(session: Session, kind: str, value: str) -> int:
    statement = insert(Entity).values(kind=kind, value=value).on_conflict_do_nothing(index_elements=[Entity.kind, Entity.value])
    session.execute(statement)
    return session.scalar(select(Entity.id).where(Entity.kind == kind, Entity.value == value))


def record(session: Session, domain: str, nodes: list[tuple], evidence_id: str | None) -> int:
    """Edges from the site to each node: (kind, value) or (kind, value, strength). Returns the site's entity id.
    A new edge raises the entity's `domain_count`, which the hub rule reads."""
    source = entity_id(session, "domain", domain)
    seen = set()
    for node in nodes:
        kind, value = node[0], str(node[1])[:500] if node[1] else node[1]
        if not value or (kind, value) == ("domain", domain) or (kind, value) in seen:
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
