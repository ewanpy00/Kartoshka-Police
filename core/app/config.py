from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://kartoshka:kartoshka_dev@postgres:5432/kartoshka"
    redis_url: str = "redis://redis:6379/0"
    rq_queue: str = "deep"
    sandbox_url: str = "http://sandbox:8001"
    data_dir: str = "/srv/data"
    captures_dir: str = "/captures"
    core_write_token: str = ""

    batch_url_budget_ms: int = 3000
    batch_cutoff: int = 40
    batch_concurrency: int = 20

    # Fast path: network lookups (RDAP, GSB, VirusTotal, DNS, shortener expansion) must answer in this budget.
    fast_lookup_budget_ms: int = 700
    verdict_cache_ttl_s: int = 600
    deep_reuse_hours: int = 6
    preview_rate_per_hour: int = 10

    virustotal_api_key: str = ""
    google_safe_browsing_api_key: str = ""

    ai_provider: str = "anthropic"
    anthropic_api_key: str = ""
    ai_model: str = "claude-opus-5-5"
    ai_timeout_s: float = 60.0

    @property
    def ai_enabled(self) -> bool:
        return self.ai_provider == "anthropic" and bool(self.anthropic_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
