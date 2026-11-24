from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


def now_column() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now())


class Check(Base):
    __tablename__ = "checks"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    url: Mapped[str] = mapped_column(Text)
    final_url: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String)
    mode: Mapped[str] = mapped_column(String)
    verdict: Mapped[str] = mapped_column(String)
    score: Mapped[int] = mapped_column(Integer)
    stage: Mapped[str] = mapped_column(String)
    brand: Mapped[str | None] = mapped_column(String)
    safe_action: Mapped[dict | None] = mapped_column(JSON)
    reasons: Mapped[list] = mapped_column(JSON)
    campaign_id: Mapped[str | None] = mapped_column(String)
    evidence_id: Mapped[str | None] = mapped_column(String)
    internal_requests_blocked: Mapped[int | None] = mapped_column(Integer)
    navigation_blocked: Mapped[bool | None] = mapped_column(Boolean)
    domain: Mapped[str | None] = mapped_column(String, index=True)
    created_at: Mapped[datetime] = now_column()

    @property
    def check_id(self) -> str:
        return self.id


class Domain(Base):
    __tablename__ = "domains"

    domain: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str] = mapped_column(String, index=True)
    brand_id: Mapped[str | None] = mapped_column(String)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    confirmed_by: Mapped[str | None] = mapped_column(String)


class Verdict(Base):
    __tablename__ = "verdicts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    check_id: Mapped[str] = mapped_column(ForeignKey("checks.id"), index=True)
    verdict: Mapped[str] = mapped_column(String)
    score: Mapped[int] = mapped_column(Integer)
    stage: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = now_column()


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    check_id: Mapped[str] = mapped_column(ForeignKey("checks.id"), index=True)
    prev_hash: Mapped[str | None] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64), unique=True)
    payload: Mapped[dict] = mapped_column(JSON)
    seq: Mapped[int] = mapped_column(BigInteger, Identity(), unique=True)
    created_at: Mapped[datetime] = now_column()


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    evidence_id: Mapped[str] = mapped_column(ForeignKey("evidence.id"), index=True)
    sha256: Mapped[str] = mapped_column(String(64))
    path: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = now_column()


class Entity(Base):
    __tablename__ = "entities"
    __table_args__ = (UniqueConstraint("kind", "value"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String)
    value: Mapped[str] = mapped_column(Text)
    domain_count: Mapped[int] = mapped_column(Integer, server_default="0")
    campaign_id: Mapped[str | None] = mapped_column(ForeignKey("campaigns.id"))


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    brand_id: Mapped[str | None] = mapped_column(String)
    first_seen: Mapped[datetime] = now_column()
    name: Mapped[str | None] = mapped_column(String)
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Edge(Base):
    __tablename__ = "edges"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    src_id: Mapped[int] = mapped_column(ForeignKey("entities.id"), index=True)
    dst_id: Mapped[int] = mapped_column(ForeignKey("entities.id"), index=True)
    evidence_id: Mapped[str | None] = mapped_column(ForeignKey("evidence.id"))
    campaign_id: Mapped[str | None] = mapped_column(ForeignKey("campaigns.id"))
    strength: Mapped[str] = mapped_column(String, server_default="weak")


class Watchlist(Base):
    __tablename__ = "watchlist"

    domain: Mapped[str] = mapped_column(String, primary_key=True)
    added_at: Mapped[datetime] = now_column()
    next_check_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    gsb_first_hit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    vt_first_hit_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    gsb_last_clean_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    vt_last_clean_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    vt_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    evidence_id: Mapped[str] = mapped_column(ForeignKey("evidence.id"), index=True)
    decision: Mapped[str] = mapped_column(String)
    reviewer: Mapped[str] = mapped_column(String)
    reviewed_at: Mapped[datetime] = now_column()
    domain: Mapped[str | None] = mapped_column(String, index=True)
    reason: Mapped[str | None] = mapped_column(Text)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    domain: Mapped[str] = mapped_column(String, index=True)
    url: Mapped[str] = mapped_column(Text)
    note: Mapped[str | None] = mapped_column(Text)
    check_id: Mapped[str | None] = mapped_column(ForeignKey("checks.id"))
    created_at: Mapped[datetime] = now_column()


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    actor: Mapped[str] = mapped_column(String)
    action: Mapped[str] = mapped_column(String)
    target: Mapped[str] = mapped_column(String)
    before: Mapped[dict | None] = mapped_column(JSON)
    after: Mapped[dict | None] = mapped_column(JSON)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = now_column()


class TakedownPack(Base):
    __tablename__ = "takedown_packs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    recipient_kind: Mapped[str] = mapped_column(String)
    recipient: Mapped[str] = mapped_column(String)
    sha256: Mapped[str] = mapped_column(String(64))
    zip: Mapped[bytes] = mapped_column(LargeBinary)
    generated_at: Mapped[datetime] = now_column()
    generated_by: Mapped[str] = mapped_column(String)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_by: Mapped[str | None] = mapped_column(String)


class TakedownRequest(Base):
    __tablename__ = "takedown_requests"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    pack_id: Mapped[str] = mapped_column(ForeignKey("takedown_packs.id"), index=True)
    domain: Mapped[str] = mapped_column(String)
    evidence_id: Mapped[str] = mapped_column(ForeignKey("evidence.id"))
