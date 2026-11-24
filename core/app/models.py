from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
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


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    brand_id: Mapped[str | None] = mapped_column(String)
    first_seen: Mapped[datetime] = now_column()


class Edge(Base):
    __tablename__ = "edges"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    src_id: Mapped[int] = mapped_column(ForeignKey("entities.id"), index=True)
    dst_id: Mapped[int] = mapped_column(ForeignKey("entities.id"), index=True)
    evidence_id: Mapped[str | None] = mapped_column(ForeignKey("evidence.id"))
    campaign_id: Mapped[str | None] = mapped_column(ForeignKey("campaigns.id"))


class Watchlist(Base):
    __tablename__ = "watchlist"

    domain: Mapped[str] = mapped_column(String, primary_key=True)
    added_at: Mapped[datetime] = now_column()
    next_check_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    evidence_id: Mapped[str] = mapped_column(ForeignKey("evidence.id"), index=True)
    decision: Mapped[str] = mapped_column(String)
    reviewer: Mapped[str] = mapped_column(String)
    reviewed_at: Mapped[datetime] = now_column()
