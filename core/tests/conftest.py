import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app import queue
from app.config import Settings, get_settings
from app.db import get_engine, get_session
from app.main import app
from app.seed import seed

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
def settings():
    return Settings(data_dir=DATA_DIR, core_write_token="test-token", batch_url_budget_ms=50)


@pytest.fixture
def client(session, settings, enqueued):
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_settings] = lambda: settings
    yield TestClient(app)
    app.dependency_overrides.clear()
