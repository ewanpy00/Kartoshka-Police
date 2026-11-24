from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import false as sa_false
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def now_column(**kwargs) -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), **kwargs)


class Check(Base):
    __tablename__ = "checks"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    url: Mapped[str] = mapped_column(Text)
    final_url: Mapped[str | None] = mapped_column(Text)
    host: Mapped[str | None] = mapped_column(String, index=True)
    domain: Mapped[str | None] = mapped_column(String, index=True)
    source: Mapped[str] = mapped_column(String)
    mode: Mapped[str] = mapped_column(String)
    verdict: Mapped[str] = mapped_column(String)
    score: Mapped[int] = mapped_column(Integer)
    stage: Mapped[str] = mapped_column(String)
    brand: Mapped[str | None] = mapped_column(String)
    brand_id: Mapped[str | None] = mapped_column(String)
    safe_action: Mapped[dict | None] = mapped_column(JSON)
    reasons: Mapped[list] = mapped_column(JSON)
    sources: Mapped[list | None] = mapped_column(JSON, default=list)
    features: Mapped[dict | None] = mapped_column(JSON, default=dict)
    chain: Mapped[list | None] = mapped_column(JSON, default=list)
    preview: Mapped[dict | None] = mapped_column(JSON)
    deep_status: Mapped[str | None] = mapped_column(String)
    campaign_id: Mapped[str | None] = mapped_column(String, index=True)
    evidence_id: Mapped[str | None] = mapped_column(String)
    internal_requests_blocked: Mapped[int | None] = mapped_column(Integer)
    navigation_blocked: Mapped[bool | None] = mapped_column(Boolean)
    created_at: Mapped[datetime] = now_column(index=True)
    updated_at: Mapped[datetime] = now_column(onupdate=func.now())

    @property
    def check_id(self) -> str:
        return self.id


class Domain(Base):
    """Decided domains. status: official | allowlisted | confirmed | cleared."""

    __tablename__ = "domains"

    domain: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str] = mapped_column(String, index=True)
    brand_id: Mapped[str | None] = mapped_column(String)
    source: Mapped[str] = mapped_column(String, server_default="seed")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    # When GSB or VirusTotal first flagged a domain we already had: the lead-time number.
    gsb_first_hit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    vt_first_hit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Verdict(Base):
    __tablename__ = "verdicts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    check_id: Mapped[str] = mapped_column(ForeignKey("checks.id"), index=True)
    verdict: Mapped[str] = mapped_column(String)
    score: Mapped[int] = mapped_column(Integer)
    stage: Mapped[str] = mapped_column(String)
    reasons: Mapped[list | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = now_column()


class Evidence(Base):
    """Append-only and hash-chained: each row stores the hash of the previous row."""

    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    seq: Mapped[int] = mapped_column(BigInteger, unique=True)
    check_id: Mapped[str] = mapped_column(ForeignKey("checks.id"), index=True)
    domain: Mapped[str | None] = mapped_column(String, index=True)
    prev_hash: Mapped[str | None] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64), unique=True)
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = now_column()


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    evidence_id: Mapped[str] = mapped_column(ForeignKey("evidence.id"), index=True)
    kind: Mapped[str] = mapped_column(String, server_default="file")
    sha256: Mapped[str] = mapped_column(String(64))
    path: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = now_column()


class Entity(Base):
    """A node in the campaign graph: domain, ip, asn, ns, registrar, cert, kit_hash, favicon_hash, phone, payment."""

    __tablename__ = "entities"
    __table_args__ = (UniqueConstraint("kind", "value"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String)
    value: Mapped[str] = mapped_column(Text)
    first_seen: Mapped[datetime] = now_column()
    domain_count: Mapped[int] = mapped_column(Integer, server_default="0")


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    brand_id: Mapped[str | None] = mapped_column(String)
    name: Mapped[str | None] = mapped_column(String)
    domain_count: Mapped[int] = mapped_column(Integer, server_default="0")
    confirmed_count: Mapped[int] = mapped_column(Integer, server_default="0")
    summary: Mapped[str | None] = mapped_column(Text)
    first_seen: Mapped[datetime] = now_column()
    updated_at: Mapped[datetime] = now_column(onupdate=func.now())
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Edge(Base):
    __tablename__ = "edges"
    __table_args__ = (UniqueConstraint("src_id", "dst_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    src_id: Mapped[int] = mapped_column(ForeignKey("entities.id"), index=True)
    dst_id: Mapped[int] = mapped_column(ForeignKey("entities.id"), index=True)
    evidence_id: Mapped[str | None] = mapped_column(ForeignKey("evidence.id"))
    campaign_id: Mapped[str | None] = mapped_column(ForeignKey("campaigns.id"))
    strength: Mapped[str] = mapped_column(String, server_default="weak")
    excluded: Mapped[bool] = mapped_column(Boolean, server_default=sa_false())


class Watchlist(Base):
    __tablename__ = "watchlist"

    domain: Mapped[str] = mapped_column(String, primary_key=True)
    url: Mapped[str | None] = mapped_column(Text)
    reason: Mapped[str | None] = mapped_column(String)
    brand_id: Mapped[str | None] = mapped_column(String)
    last_status: Mapped[str | None] = mapped_column(String)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    offline_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    checks_done: Mapped[int] = mapped_column(Integer, server_default="0")
    added_at: Mapped[datetime] = now_column()
    next_check_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    evidence_id: Mapped[str] = mapped_column(ForeignKey("evidence.id"), index=True)
    decision: Mapped[str] = mapped_column(String)
    reviewer: Mapped[str] = mapped_column(String)
    reason: Mapped[str | None] = mapped_column(String)
    note: Mapped[str | None] = mapped_column(Text)
    reviewed_at: Mapped[datetime] = now_column()


class FeedEntry(Base):
    """Intelligence reported by the hunter: threat feeds, CT sightings, newly registered domains, sweeps."""

    __tablename__ = "feed_entries"
    __table_args__ = (UniqueConstraint("source", "url"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String, index=True)
    url: Mapped[str] = mapped_column(Text)
    domain: Mapped[str] = mapped_column(String, index=True)
    brand_id: Mapped[str | None] = mapped_column(String)
    detail: Mapped[str | None] = mapped_column(Text)
    first_seen: Mapped[datetime] = now_column()


class Report(Base):
    """A resident report. Only the token's hash is stored; the device keeps the token."""

    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64))
    check_id: Mapped[str] = mapped_column(ForeignKey("checks.id"), index=True)
    url: Mapped[str] = mapped_column(Text)
    domain: Mapped[str | None] = mapped_column(String, index=True)
    note: Mapped[str | None] = mapped_column(Text)
    push_token: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = now_column()


class Hit(Base):
    """Aggregated block counters per domain and channel. No user or device data."""

    __tablename__ = "hits"
    __table_args__ = (PrimaryKeyConstraint("domain", "channel"),)

    domain: Mapped[str] = mapped_column(String)
    channel: Mapped[str] = mapped_column(String)
    count: Mapped[int] = mapped_column(BigInteger, server_default="0")
    updated_at: Mapped[datetime] = now_column(onupdate=func.now())


class ModelState(Base):
    """Small key-value store for trained model parameters (fusion weights)."""

    __tablename__ = "model_state"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)
    score: Mapped[float | None] = mapped_column(Float)
    updated_at: Mapped[datetime] = now_column(onupdate=func.now())


class TakedownRequest(Base):
    """One request to one recipient (registrar, host, Cloudflare, aeDA, GSB) for one domain."""

    __tablename__ = "takedown_requests"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    domain: Mapped[str] = mapped_column(String, index=True)
    campaign_id: Mapped[str | None] = mapped_column(String)
    recipient_kind: Mapped[str] = mapped_column(String)
    recipient: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, index=True)
    pack_sha256: Mapped[str | None] = mapped_column(String(64))
    generated_at: Mapped[datetime] = now_column()
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_by: Mapped[str | None] = mapped_column(String)
    offline_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    offline_reason: Mapped[str | None] = mapped_column(String)
    checks_offline: Mapped[int] = mapped_column(Integer, server_default="0")
    note: Mapped[str | None] = mapped_column(Text)


class AuditLog(Base):
    """Every officer and system decision. Append-only (trigger in migration 0003)."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    actor: Mapped[str] = mapped_column(String)
    action: Mapped[str] = mapped_column(String, index=True)
    target_kind: Mapped[str] = mapped_column(String)
    target: Mapped[str] = mapped_column(String, index=True)
    before: Mapped[dict | None] = mapped_column(JSON)
    after: Mapped[dict | None] = mapped_column(JSON)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = now_column()
