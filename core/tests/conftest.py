import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import cache, queue
from app.ai import url_model
from app.config import Settings, get_settings
from app.db import get_engine, get_session
from app.fast import intel, rdap
from app.main import app
from app.seed import seed

DATA_DIR = get_settings().data_dir


@pytest.fixture(scope="session", autouse=True)
def seeded():
    """The seed is idempotent and core runs it on start; run it once per test session, committed."""
    with Session(get_engine()) as db:
        seed(db, DATA_DIR)
        db.commit()


@pytest.fixture
def session():
    with get_engine().connect() as connection:
        outer = connection.begin()
        with Session(connection, join_transaction_mode="create_savepoint") as db:
            yield db
        outer.rollback()


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    """No network in tests: RDAP finds nothing, DNS resolves nothing, the verdict cache is empty, and the
    URL model is off (the trained one lives in the shared database and would make scores drift)."""
    registered: dict[str, dict] = {}

    async def fake_rdap(domain, timeout_s=8.0):
        return registered.get(domain, {"found": False})

    async def fake_resolve(host, timeout_s):
        return []

    async def no_cache(key):
        return None

    async def drop(key, value, ttl_s):
        return None

    monkeypatch.setattr(rdap, "lookup", fake_rdap)
    monkeypatch.setattr(intel, "resolve_a", fake_resolve)
    monkeypatch.setattr(cache, "get_json", no_cache)
    monkeypatch.setattr(cache, "set_json", drop)
    monkeypatch.setattr(cache, "publish", lambda event: None)
    monkeypatch.setattr(queue, "claim_deep", lambda host: True)
    monkeypatch.setattr(url_model, "predict", lambda features: None)
    return registered


@pytest.fixture
def enqueued(monkeypatch):
    jobs = []
    monkeypatch.setattr(queue, "enqueue_deep_check", jobs.append)
    return jobs


@pytest.fixture
def settings():
    return Settings(data_dir=DATA_DIR, core_write_token="test-token", batch_url_budget_ms=50, fast_lookup_budget_ms=50)


@pytest.fixture
def client(session, settings, enqueued):
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_settings] = lambda: settings
    yield TestClient(app)
    app.dependency_overrides.clear()
