from datetime import datetime
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, field_validator


def require_http_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise ValueError("must be an absolute http(s) URL")
    return value


class Reason(BaseModel):
    code: str
    weight: int
    source: str
    en: str
    ar: str


class SafeAction(BaseModel):
    label_en: str
    label_ar: str
    url: str


class CheckRequest(BaseModel):
    url: str
    source: str = "api"
    mode: Literal["fast", "deep"] = "fast"

    _url = field_validator("url")(require_http_url)


class Verdict(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    check_id: str
    url: str
    final_url: str | None
    verdict: Literal["allow", "warn", "block", "pending"]
    score: int
    stage: Literal["fast", "deep", "officer"]
    brand: str | None
    safe_action: SafeAction | None
    reasons: list[Reason]
    campaign_id: str | None
    evidence_id: str | None


class BatchRequest(BaseModel):
    urls: list[str]

    _urls = field_validator("urls")(lambda urls: [require_http_url(url) for url in urls])


class BatchResult(BaseModel):
    url: str
    check_id: str
    verdict: Literal["allow", "block"]
    score: int
    timed_out: bool


class BatchResponse(BaseModel):
    cutoff: int
    results: list[BatchResult]


class ReportRequest(BaseModel):
    url: str
    note: str = ""

    _url = field_validator("url")(require_http_url)


class ReportResponse(BaseModel):
    check_id: str
    status: Literal["received"]


class ReviewRequest(BaseModel):
    decision: Literal["confirm", "reject"]
    reason: str | None = None
    reviewer: str = "Demo Officer"


class ReviewResponse(BaseModel):
    evidence_id: str
    decision: str
    reviewer: str
    reviewed_at: datetime


class BlocklistEntry(BaseModel):
    domain: str
    brand_id: str | None
    updated_at: datetime


class BlocklistResponse(BaseModel):
    domains: list[BlocklistEntry]


class EvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    check_id: str
    prev_hash: str | None
    hash: str
    payload: dict
    created_at: datetime


class Health(BaseModel):
    status: str
    db: str
    redis: str


CaseState = Literal["open", "auto_confirmed", "confirmed", "rejected"]


class CaseSummary(BaseModel):
    domain: str
    state: CaseState
    score: int
    verdict: str
    brand: str | None
    sources: list[str]
    reports: int
    hits: int
    first_seen: datetime
    last_seen: datetime
    evidence_id: str | None
    campaign_id: str | None
    rank: float


class QueueResponse(BaseModel):
    cases: list[CaseSummary]


class CaseCheck(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    check_id: str
    url: str
    source: str
    verdict: str
    score: int
    created_at: datetime


class CaseReview(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    evidence_id: str
    decision: str
    reason: str | None
    reviewer: str
    reviewed_at: datetime


class ReportNote(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    note: str
    created_at: datetime


class CaseDetail(CaseSummary):
    url: str
    final_url: str | None
    title: str | None
    reasons: list[dict]
    infrastructure: dict
    location: dict | None
    lead_time: dict | None
    report_notes: list[ReportNote]
    checks: list[CaseCheck]
    reviews: list[CaseReview]
    has_screenshot: bool


class OfficerAction(BaseModel):
    reviewer: str = "Demo Officer"


class RecheckResponse(BaseModel):
    check_id: str


class WatchResponse(BaseModel):
    domain: str
    next_check_at: datetime
    expires_at: datetime


class UndoResponse(BaseModel):
    domain: str
    state: CaseState


class AuditEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor: str
    action: str
    target: str
    before: dict | None
    after: dict | None
    reason: str | None
    created_at: datetime


class AuditResponse(BaseModel):
    entries: list[AuditEntry]


class FeedItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    check_id: str
    domain: str | None
    url: str
    brand: str | None
    verdict: str
    score: int
    created_at: datetime


class FeedResponse(BaseModel):
    items: list[FeedItem]


class WatchRunResponse(BaseModel):
    queued: int
