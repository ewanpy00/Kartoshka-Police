from functools import lru_cache

from redis import Redis
from rq import Queue

from app.config import get_settings


@lru_cache
def get_redis() -> Redis:
    return Redis.from_url(get_settings().redis_url, socket_connect_timeout=2)


def enqueue_deep_check(check_id: str) -> None:
    Queue(get_settings().rq_queue, connection=get_redis()).enqueue("app.jobs.deep_check", check_id)
