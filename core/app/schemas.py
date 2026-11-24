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
