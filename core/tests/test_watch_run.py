from datetime import UTC, datetime, timedelta

import httpx
import pytest
from admin_factories import AUTH

from app import watch
from app.models import Check, Watchlist


class Calls:
    def __init__(self, gsb_hit=False, vt_malicious=0):
        self.gsb = []
        self.vt = []
        self.gsb_hit = gsb_hit
        self.vt_malicious = vt_malicious

    def post(self, url, **kwargs):
        self.gsb.append((url, kwargs))
        body = {"matches": [{"threatType": "SOCIAL_ENGINEERING"}]} if self.gsb_hit else {}
        return httpx.Response(200, json=body, request=httpx.Request("POST", url))

    def get(self, url, **kwargs):
        self.vt.append((url, kwargs))
        body = {"data": {"attributes": {"last_analysis_stats": {"malicious": self.vt_malicious}}}}
        return httpx.Response(200, json=body, request=httpx.Request("GET", url))


@pytest.fixture
def calls(monkeypatch):
    recorded = Calls()
    monkeypatch.setattr(watch.httpx, "post", recorded.post)
    monkeypatch.setattr(watch.httpx, "get", recorded.get)
    return recorded


@pytest.fixture
def keys(settings):
    settings.google_safe_browsing_api_key = "gsb-key"
    settings.virustotal_api_key = "vt-key"


def add_watch(session, domain="tamm-pay.xyz", due=True, expired=False, **columns):
    now = datetime.now(UTC)
    row = Watchlist(
        domain=domain,
        next_check_at=now - timedelta(minutes=1) if due else now + timedelta(hours=1),
        expires_at=now - timedelta(days=1) if expired else now + timedelta(days=1),
        **columns,
    )
    session.add(row)
    session.commit()
    return row


def run(client):
    response = client.post("/v1/admin/watchlist/run", headers=AUTH)
    assert response.status_code == 202
    return response.json()["queued"]


def test_run_queues_a_deep_check_and_polls_each_service_once(client, session, keys, calls, enqueued):
    row = add_watch(session)
    assert run(client) == 1
    check = session.query(Check).filter_by(source="watchlist").one()
    assert (check.domain, check.mode) == ("tamm-pay.xyz", "deep")
    assert enqueued == [check.id]
    assert len(calls.gsb) == 1
    assert calls.gsb[0][1]["params"] == {"key": "gsb-key"}
    assert calls.vt[0][0].endswith("/domains/tamm-pay.xyz")
    assert calls.vt[0][1]["headers"] == {"x-apikey": "vt-key"}
    assert len(calls.vt) == 1
    assert row.gsb_last_clean_at and row.vt_last_clean_at and row.vt_checked_at
    assert row.gsb_first_hit_at is None and row.vt_first_hit_at is None
    assert row.next_check_at > datetime.now(UTC) + timedelta(hours=5)


def test_second_run_within_a_day_skips_virustotal(client, session, keys, calls):
    row = add_watch(session)
    run(client)
    row.next_check_at = datetime.now(UTC) - timedelta(minutes=1)
    session.commit()
    run(client)
    assert len(calls.gsb) == 2
    assert len(calls.vt) == 1


def test_virustotal_is_polled_again_after_a_day(client, session, keys, calls):
    add_watch(session, vt_checked_at=datetime.now(UTC) - timedelta(hours=25))
    run(client)
    assert len(calls.vt) == 1


def test_empty_keys_call_nothing_and_change_no_column(client, session, calls):
    row = add_watch(session)
    assert run(client) == 1
    assert calls.gsb == [] and calls.vt == []
    assert (row.gsb_last_clean_at, row.vt_last_clean_at, row.vt_checked_at) == (None, None, None)


def test_hits_set_first_hit_once(client, session, keys, calls):
    calls.gsb_hit, calls.vt_malicious = True, 3
    row = add_watch(session)
    run(client)
    first = row.gsb_first_hit_at
    assert first and row.vt_first_hit_at and row.vt_checked_at
    row.next_check_at = datetime.now(UTC) - timedelta(minutes=1)
    session.commit()
    run(client)
    assert row.gsb_first_hit_at == first


def test_failed_poll_leaves_columns_unchanged(client, session, keys, monkeypatch):
    def fail(url, **kwargs):
        raise httpx.ConnectTimeout("slow")

    monkeypatch.setattr(watch.httpx, "post", fail)
    monkeypatch.setattr(watch.httpx, "get", fail)
    row = add_watch(session)
    assert run(client) == 1
    assert (row.gsb_last_clean_at, row.vt_last_clean_at, row.vt_checked_at) == (None, None, None)


def test_rows_not_due_or_expired_are_left_alone(client, session, keys, calls):
    add_watch(session, "later.example", due=False)
    add_watch(session, "gone.example", expired=True)
    assert run(client) == 0
    assert calls.gsb == [] and calls.vt == []
    assert session.query(Check).filter_by(source="watchlist").count() == 0


def test_failed_poll_logs_neither_the_key_nor_a_query_string(monkeypatch, caplog):
    def fail(url, **kwargs):
        raise httpx.ConnectTimeout(f"timed out for {url}?key=gsb-key")

    monkeypatch.setattr(watch.httpx, "post", fail)
    with caplog.at_level("WARNING", logger="app.watch"):
        assert watch.poll_safe_browsing("gsb-key", "tamm-pay.xyz") is None
    assert "tamm-pay.xyz" in caplog.text and "ConnectTimeout" in caplog.text
    assert "gsb-key" not in caplog.text and "key=" not in caplog.text
    assert all(record.exc_info is None for record in caplog.records)


def test_failed_poll_logs_the_status_code(monkeypatch, caplog):
    def refuse(url, **kwargs):
        return httpx.Response(403, request=httpx.Request("POST", f"{url}?key=gsb-key"))

    monkeypatch.setattr(watch.httpx, "post", refuse)
    with caplog.at_level("WARNING", logger="app.watch"):
        assert watch.poll_safe_browsing("gsb-key", "tamm-pay.xyz") is None
    assert "403" in caplog.text and "gsb-key" not in caplog.text
