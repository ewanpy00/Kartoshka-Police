from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://kartoshka:kartoshka_dev@postgres:5432/kartoshka"
    redis_url: str = "redis://redis:6379/0"
    rq_queue: str = "deep"
    sandbox_url: str = "http://sandbox:8001"
    data_dir: str = "/srv/data"
    core_write_token: str = ""
    batch_url_budget_ms: int = 3000
    batch_cutoff: int = 70
    batch_concurrency: int = 20


@lru_cache
def get_settings() -> Settings:
    return Settings()
