from functools import lru_cache

from redis import Redis
from rq import Queue, Retry

from app.config import get_settings

DEEP_LOCK_S = 600


@lru_cache
def get_redis() -> Redis:
    return Redis.from_url(get_settings().redis_url, socket_connect_timeout=2)


def get_queue() -> Queue:
    return Queue(get_settings().rq_queue, connection=get_redis())


def enqueue_deep_check(check_id: str) -> None:
    get_queue().enqueue("app.deep.job.deep_check", check_id, job_timeout=180, retry=Retry(max=1, interval=10))


def claim_deep(host: str) -> bool:
    """One deep analysis per host at a time. Later checks of the host join the running one."""
    try:
        return bool(get_redis().set(f"kp:deep:{host}", "1", nx=True, ex=DEEP_LOCK_S))
    except Exception:
        return True


def release_deep(host: str) -> None:
    try:
        get_redis().delete(f"kp:deep:{host}")
    except Exception:
        pass


def enqueue(name: str, *args, timeout: int = 300) -> None:
    get_queue().enqueue(name, *args, job_timeout=timeout)
