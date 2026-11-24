"""Kit fingerprints: the page's DOM skeleton (tag sequence) and favicon, compared with known scam pages.

An exact skeleton hash shared with a confirmed scam is KIT_MATCH; a SimHash of the skeleton within a few
bits of one is KIT_SIMILAR; the same favicon bytes is FAVICON_MATCH. Only confirmed domains count, so a
kit that many legitimate sites share (a CMS theme) does not raise anyone's score until an officer
confirms a scam built on it.
"""
import hashlib

from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from app.models import Domain, Edge, Entity
from app.verdict.reasons import reason

MIN_TAGS = 20
SHINGLE = 4
SIMILAR_BITS = 6


def skeleton_hash(skeleton: str) -> str | None:
    if len(skeleton.split()) < MIN_TAGS:
        return None
    return hashlib.sha256(skeleton.encode()).hexdigest()


def simhash(skeleton: str) -> int | None:
    tags = skeleton.split()
    if len(tags) < MIN_TAGS:
        return None
    counts = [0] * 64
    for start in range(len(tags) - SHINGLE + 1):
        shingle = " ".join(tags[start : start + SHINGLE]).encode()
        value = int.from_bytes(hashlib.blake2b(shingle, digest_size=8).digest(), "big")
        for bit in range(64):
            counts[bit] += 1 if value >> bit & 1 else -1
    return sum(1 << bit for bit in range(64) if counts[bit] > 0)


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def confirmed_owners(session: Session, kind: str, values: list[str] | None = None) -> list[tuple[str, str]]:
    """(value, domain) for entities of `kind` linked to a confirmed domain."""
    domain_entity = aliased(Entity)
    query = (
        select(Entity.value, domain_entity.value)
        .join(Edge, Edge.dst_id == Entity.id)
        .join(domain_entity, domain_entity.id == Edge.src_id)
        .join(Domain, Domain.domain == domain_entity.value)
        .where(Entity.kind == kind, domain_entity.kind == "domain", Domain.status == "confirmed")
    )
    if values is not None:
        query = query.where(Entity.value.in_(values))
    return [tuple(row) for row in session.execute(query.limit(5000)).all()]


def kit_reasons(session: Session, domain: str, kit_hash: str | None, kit_sim: int | None, favicon_sha: str | None) -> list[dict]:
    reasons = []
    if kit_hash:
        owners = [d for _, d in confirmed_owners(session, "kit_hash", [kit_hash]) if d != domain]
        if owners:
            reasons.append(reason("KIT_MATCH", campaign=owners[0]))
    if kit_sim is not None and not reasons:
        best = None
        for value, owner in confirmed_owners(session, "kit_sim"):
            if owner == domain:
                continue
            distance = hamming(kit_sim, int(value, 16))
            if distance <= SIMILAR_BITS and (best is None or distance < best):
                best = distance
        if best is not None:
            reasons.append(reason("KIT_SIMILAR", pct=round(100 * (1 - best / 64))))
    if favicon_sha:
        owners = [d for _, d in confirmed_owners(session, "favicon_hash", [favicon_sha]) if d != domain]
        if owners:
            reasons.append(reason("FAVICON_MATCH"))
    return reasons
