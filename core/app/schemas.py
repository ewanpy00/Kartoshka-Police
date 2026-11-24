from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.normalize.url import clean

MAX_URL = 4096


def require_http_url(value: str) -> str:
    """Accept absolute http(s) URLs and bare hosts (a bare host gets http://, as a browser would)."""
    if len(value) > MAX_URL:
        raise ValueError("URL is too long")
    stripped = value.strip()
    if "://" not in stripped and stripped.split(":", 1)[0].lower() in ("javascript", "data", "file", "mailto", "tel"):
        raise ValueError("must be an absolute http(s) URL")
    parsed = urlsplit(clean(stripped))
    if parsed.scheme not in ("http", "https") or not parsed.hostname or "." not in parsed.hostname.strip("."):
        raise ValueError("must be an absolute http(s) URL")
    return stripped


class Reason(BaseModel):
    code: str
    weight: int | None = Field(description="Points this reason adds. Hidden (null) in resident views.")
    source: str
    en: str
    ar: str


class Source(BaseModel):
    id: str
    status: Literal["hit", "clean", "unknown", "skipped"]
    detail: str | None = None


class SafeAction(BaseModel):
    label_en: str
    label_ar: str
    url: str


class Preview(BaseModel):
    screenshot: str | None = None
    asks_for: list[str] = []
    title: str | None = None


class CheckRequest(BaseModel):
    url: str
    source: str = "api"
    mode: Literal["fast", "deep"] = "fast"
    text: str = Field("", max_length=4000, description="Pasted SMS text around the link; used to pick the safe action")

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
    sources: list[Source] = []
    preview: Preview | None = None
    deep_status: str | None = None
    campaign_id: str | None
    evidence_id: str | None

    @field_validator("sources", mode="before")
    @classmethod
    def none_is_empty(cls, value):
        return value or []


def for_resident(verdict: Verdict) -> dict:
    """Residents see reasons and the verdict, never the per-reason weights."""
    body = verdict.model_dump()
    for item in body["reasons"]:
        item["weight"] = None
    return body


class BatchRequest(BaseModel):
    urls: list[str] = Field(max_length=5000)

    _urls = field_validator("urls")(lambda urls: [require_http_url(url) for url in urls])


class BatchResult(BaseModel):
    url: str
    check_id: str
    verdict: Literal["allow", "block"]
    score: int
    timed_out: bool
    band: Literal["allow", "warn", "block"] | None = None
    brand: str | None = None
    reasons: list[Reason] | None = None


class BatchResponse(BaseModel):
    cutoff: int
    results: list[BatchResult]


class ReportRequest(BaseModel):
    url: str
    note: str = Field("", max_length=2000)
    push_token: str | None = Field(None, max_length=512)

    _url = field_validator("url")(require_http_url)


class ReportResponse(BaseModel):
    check_id: str
    status: Literal["received"]
    report_id: str | None = None
    token: str | None = None


class ReviewRequest(BaseModel):
    decision: Literal["confirm", "reject"]
    reviewer: str = Field("Demo Officer", max_length=200)
    note: str = Field("", max_length=2000)


class ReviewResponse(BaseModel):
    evidence_id: str
    decision: str
    reviewer: str
    reviewed_at: datetime
    domain: str | None = None
    blocklist_version: int | None = None


class BlocklistEntry(BaseModel):
    domain: str
    brand_id: str | None
    updated_at: datetime


class BlocklistResponse(BaseModel):
    domains: list[BlocklistEntry]
    removed: list[BlocklistEntry] = []
    version: int = 0
    generated_at: datetime | None = None


class EvidenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    seq: int | None = None
    check_id: str
    prev_hash: str | None
    hash: str
    payload: dict
    created_at: datetime


class Health(BaseModel):
    status: str
    db: str
    redis: str
