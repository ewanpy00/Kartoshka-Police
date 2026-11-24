import os

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from app import events, queue
from app.config import Settings, get_settings

MIGRATION_LOCK = 7_261_001


def use_test_database() -> None:
    """Point the app at `<dev database>_test`, creating it and migrating it to head.

    The advisory lock keeps concurrent pytest runs from creating or migrating it twice.
    """
    dev_url = make_url(get_settings().database_url)
    test_url = dev_url.set(database=f"{dev_url.database}_test")
    admin = create_engine(dev_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text("SELECT pg_advisory_lock(:key)"), {"key": MIGRATION_LOCK})
        exists = connection.scalar(text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": test_url.database})
        if not exists:
            connection.execute(text(f'CREATE DATABASE "{test_url.database}"'))
        os.environ["DATABASE_URL"] = test_url.render_as_string(hide_password=False)
        get_settings.cache_clear()
        command.upgrade(Config("alembic.ini"), "head")
        connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": MIGRATION_LOCK})
    admin.dispose()


use_test_database()

from app.db import get_engine, get_session  # noqa: E402
from app.main import app  # noqa: E402
from app.seed import seed  # noqa: E402

DATA_DIR = get_settings().data_dir


@pytest.fixture
def session():
    with get_engine().connect() as connection:
        outer = connection.begin()
        with Session(connection, join_transaction_mode="create_savepoint") as db:
            seed(db, DATA_DIR)
            yield db
        outer.rollback()


@pytest.fixture
def enqueued(monkeypatch):
    jobs = []
    monkeypatch.setattr(queue, "enqueue_deep_check", jobs.append)
    return jobs


@pytest.fixture
def published(monkeypatch):
    messages = []
    monkeypatch.setattr(events, "publish", lambda type, data: messages.append((type, data)))
    return messages


@pytest.fixture
def settings():
    return Settings(data_dir=DATA_DIR, core_write_token="test-token", batch_url_budget_ms=50)


@pytest.fixture
def client(session, settings, enqueued):
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_settings] = lambda: settings
    yield TestClient(app)
    app.dependency_overrides.clear()
