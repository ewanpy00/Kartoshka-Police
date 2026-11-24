from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://kartoshka:kartoshka_dev@postgres:5432/kartoshka"
    redis_url: str = "redis://redis:6379/0"
    rq_queue: str = "deep"
    sandbox_url: str = "http://sandbox:8001"
    data_dir: str = "/srv/data"
    captures_dir: str = "/captures"
    core_write_token: str = ""
    static_dir: str = ""  # a folder holding `resident/` and `console/` builds; empty means core serves no static files
    trust_proxy: bool = False  # read the client address from X-Real-IP (set only behind a proxy that overwrites it)

    # Daily spend caps (UTC day). Unset means no cap.
    ai_daily_calls: int | None = None
    deep_daily_checks: int | None = None
    batch_max_urls: int = 5000  # can be lowered; the request schema still rejects more than 5000

    # Per-address limits on the public routes; a request with the write token skips them.
    check_rate_per_min: int = 120
    read_rate_per_min: int = 300
    blocklist_rate_per_min: int = 60
    report_ip_rate_per_hour: int = 60
    preview_ip_rate_per_hour: int = 30
    sms_ip_rate_per_hour: int = 120
    batch_rate_per_hour: int = 20
    auth_fail_per_10min: int = 10

    batch_url_budget_ms: int = 3000
    batch_cutoff: int = 40
    batch_concurrency: int = 20

    # Fast path: network lookups (RDAP, GSB, VirusTotal, DNS, shortener expansion) must answer in this budget.
    fast_lookup_budget_ms: int = 700
    verdict_cache_ttl_s: int = 600
    deep_reuse_hours: int = 6
    preview_rate_per_hour: int = 10

    # Admin dashboard (docs/admin-dashboard.md)
    takedown_sla_h: int = 48
    takedown_recheck_min: int = 60
    takedown_offline_checks: int = 2
    graph_hub_degree: int = 50
    brand_spike_per_hour: int = 10
    report_rate_per_hour: int = 20

    virustotal_api_key: str = ""
    google_safe_browsing_api_key: str = ""

    ai_provider: str = "anthropic"
    anthropic_api_key: str = ""
    ai_model: str = "claude-opus-5-5"
    ai_timeout_s: float = 60.0
    ai_effort: str = "low"  # output_config.effort for page understanding: low | medium | high
    ai_sms_timeout_s: float = 20.0  # the resident waits for the SMS answer; the rules reading is the fallback

    @field_validator("ai_daily_calls", "deep_daily_checks", mode="before")
    @classmethod
    def empty_is_unset(cls, value):
        return None if value == "" else value

    @field_validator("database_url")
    @classmethod
    def psycopg_scheme(cls, value: str) -> str:
        for plain in ("postgres://", "postgresql://"):
            if value.startswith(plain):
                return "postgresql+psycopg://" + value.removeprefix(plain)
        return value

    @property
    def ai_enabled(self) -> bool:
        return self.ai_provider == "anthropic" and bool(self.anthropic_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
