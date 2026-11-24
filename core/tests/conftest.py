import os

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app import cache, events, queue
from app.ai import url_model
from app.config import Settings, get_settings
from app.fast import intel, rdap

MIGRATION_LOCK = 7_261_001

# Tests never call an external service: blank every credential before the app reads its settings, so keys in
# a developer's .env cannot leak in. A test that needs one sets it itself (settings fixture or monkeypatch).
EXTERNAL_KEYS = (
    "GOOGLE_SAFE_BROWSING_API_KEY",
    "VIRUSTOTAL_API_KEY",
    "ANTHROPIC_API_KEY",
    "SEARCH_API_KEY",
    "URLHAUS_AUTH_KEY",
)
for _key in EXTERNAL_KEYS:
    os.environ[_key] = ""
get_settings.cache_clear()


def use_test_database() -> None:
    """Point the app at `<dev database>_test`, creating it and migrating it to head.

    Nothing a test does may reach the dev database. The advisory lock keeps concurrent pytest runs from
    creating or migrating the test database twice; every test then runs in its own rolled-back transaction.
    """
    dev_url = make_url(get_settings().database_url)
    if dev_url.database.endswith("_test"):
        return
    test_url = dev_url.set(database=f"{dev_url.database}_test")
    admin = create_engine(dev_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": MIGRATION_LOCK})
        try:
            exists = connection.scalar(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": test_url.database}
            )
            if not exists:
                connection.execute(text(f'CREATE DATABASE "{test_url.database}"'))
            os.environ["DATABASE_URL"] = test_url.render_as_string(hide_password=False)
            get_settings.cache_clear()
            command.upgrade(Config("alembic.ini"), "head")
        finally:
            connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": MIGRATION_LOCK})
    admin.dispose()


use_test_database()

from app.db import get_engine, get_session  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import seed  # noqa: E402

DATA_DIR = get_settings().data_dir


def seed_test_database() -> None:
    """Seed the test database once, committed, under the same advisory lock. Per-test seeding inside each
    rolled-back transaction would make concurrent pytest runs queue on each other's uncommitted rows."""
    with get_engine().connect() as connection:
        connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": MIGRATION_LOCK})
        try:
            with Session(connection) as db:
                seed(db, DATA_DIR)
                db.commit()
        finally:
            connection.commit()
            connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": MIGRATION_LOCK})
            connection.commit()


seed_test_database()


@pytest.fixture
def session():
    """A session in a transaction that is always rolled back; the seed is already committed in the test database (a repeat seed is a no-op)."""
    with get_engine().connect() as connection:
        outer = connection.begin()
        with Session(connection, join_transaction_mode="create_savepoint") as db:
            seed(db, DATA_DIR)
            yield db
        outer.rollback()


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    """No network in tests: RDAP finds nothing, DNS resolves nothing, the verdict cache is empty, and the
    URL model is off (the trained one would make scores drift)."""
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
    monkeypatch.setattr(cache, "publish", lambda event: None, raising=False)
    monkeypatch.setattr(queue, "claim_deep", lambda host: True)
    monkeypatch.setattr(url_model, "predict", lambda features: None)
    return registered


@pytest.fixture
def enqueued(monkeypatch):
    jobs = []
    monkeypatch.setattr(queue, "enqueue_deep_check", jobs.append)
    return jobs


@pytest.fixture
def published(monkeypatch):
    """(type, data) pairs sent through app.events.publish. Events held by publish_after_commit arrive here
    when the session commits."""
    messages = []
    monkeypatch.setattr(events, "publish", lambda type, data: messages.append((type, data)), raising=False)
    return messages


@pytest.fixture
def settings():
    return Settings(
        data_dir=DATA_DIR, core_write_token="test-token", batch_url_budget_ms=50, fast_lookup_budget_ms=50,
        google_safe_browsing_api_key="", virustotal_api_key="", anthropic_api_key="",
    )


@pytest.fixture
def client(session, settings, enqueued):
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_settings] = lambda: settings
    yield TestClient(app)
    app.dependency_overrides.clear()
