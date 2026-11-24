"""`first_hits`, the one lead-time poller (takedown re-check and watchlist re-check), with the lookups stubbed."""
import logging
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.config import Settings
from app.fast import lookups
from app.models import Domain, Watchlist
from app.takedown import tracker

NOW = datetime(2026, 3, 1, 12, tzinfo=UTC)


class Lookups:
    def __init__(self):
        self.gsb, self.vt = [], []
        self.gsb_hit, self.vt_positives = False, 0

    def gsb_sync(self, url, key, *args, **kwargs):
        self.gsb.append((url, key))
        return {"hit": self.gsb_hit}

    def virustotal_sync(self, url, key, *args, **kwargs):
        self.vt.append((url, key, kwargs))
        return {"known": True, "positives": self.vt_positives, "total": 70}


@pytest.fixture
def calls(monkeypatch):
    stub = Lookups()
    monkeypatch.setattr(lookups, "gsb_sync", stub.gsb_sync)
    monkeypatch.setattr(lookups, "virustotal_sync", stub.virustotal_sync)
    return stub


@pytest.fixture
def keys():
    return Settings(google_safe_browsing_api_key="gsb-key", virustotal_api_key="vt-key")


def setup(session, watched=True, **watch_columns):
    domain = Domain(domain="tamm-pay.xyz", status="confirmed", source="officer", confirmed_by="officer")
    session.add(domain)
    row = None
    if watched:
        row = Watchlist(domain="tamm-pay.xyz", next_check_at=NOW, expires_at=NOW + timedelta(days=1), **watch_columns)
        session.add(row)
    session.flush()
    return domain, row


def test_clean_answers_stamp_the_watchlist_row_and_vt_checked_at(session, keys, calls):
    domain, row = setup(session)
    tracker.first_hits(session, "tamm-pay.xyz", None, keys, NOW)
    assert calls.gsb == [("https://tamm-pay.xyz/", "gsb-key")] and len(calls.vt) == 1
    assert calls.vt[0][2] == {"submit": False}
    assert (row.gsb_last_clean_at, row.vt_last_clean_at, row.vt_checked_at) == (NOW, NOW, NOW)
    assert domain.gsb_first_hit_at is None and domain.vt_first_hit_at is None


def test_hits_stamp_the_domain_once_and_stop_that_service_being_polled(session, keys, calls):
    calls.gsb_hit, calls.vt_positives = True, 3
    domain, row = setup(session)
    tracker.first_hits(session, "tamm-pay.xyz", None, keys, NOW)
    assert domain.gsb_first_hit_at == NOW and domain.vt_first_hit_at == NOW
    assert row.gsb_last_clean_at is None and row.vt_checked_at == NOW
    tracker.first_hits(session, "tamm-pay.xyz", None, keys, NOW + timedelta(days=2))
    assert domain.gsb_first_hit_at == NOW and len(calls.gsb) == 1 and len(calls.vt) == 1


def test_virustotal_is_throttled_to_once_a_day_but_safe_browsing_is_not(session, keys, calls):
    _, row = setup(session)
    tracker.first_hits(session, "tamm-pay.xyz", None, keys, NOW)
    tracker.first_hits(session, "tamm-pay.xyz", None, keys, NOW + timedelta(hours=6))
    assert len(calls.gsb) == 2 and len(calls.vt) == 1
    tracker.first_hits(session, "tamm-pay.xyz", None, keys, NOW + timedelta(hours=25))
    assert len(calls.vt) == 2 and row.vt_checked_at == NOW + timedelta(hours=25)


def test_virustotal_polls_again_when_checked_over_a_day_ago(session, keys, calls):
    setup(session, vt_checked_at=NOW - timedelta(hours=25))
    tracker.first_hits(session, "tamm-pay.xyz", None, keys, NOW)
    assert len(calls.vt) == 1


def test_a_service_without_a_key_is_skipped_and_nothing_is_stamped(session, calls):
    _, row = setup(session)
    tracker.first_hits(session, "tamm-pay.xyz", None, Settings(google_safe_browsing_api_key="", virustotal_api_key=""), NOW)
    assert calls.gsb == [] and calls.vt == []
    assert (row.gsb_last_clean_at, row.vt_last_clean_at, row.vt_checked_at) == (None, None, None)
    tracker.first_hits(session, "tamm-pay.xyz", None, Settings(google_safe_browsing_api_key="", virustotal_api_key="vt-key"), NOW)
    assert calls.gsb == [] and len(calls.vt) == 1 and row.gsb_last_clean_at is None


def test_without_a_watchlist_row_only_the_first_hit_is_recorded(session, keys, calls):
    domain, _ = setup(session, watched=False)
    tracker.first_hits(session, "tamm-pay.xyz", None, keys, NOW)
    assert domain.gsb_first_hit_at is None and session.get(Watchlist, "tamm-pay.xyz") is None
    calls.gsb_hit = True
    tracker.first_hits(session, "tamm-pay.xyz", None, keys, NOW)
    assert domain.gsb_first_hit_at == NOW


def test_failed_polls_change_nothing_and_never_log_the_key(session, keys, monkeypatch, caplog):
    def fail(url, key, *args, **kwargs):
        raise httpx.ConnectTimeout(f"timed out for {url}?key={key}")

    monkeypatch.setattr(lookups, "gsb_sync", fail)
    monkeypatch.setattr(lookups, "virustotal_sync", fail)
    domain, row = setup(session)
    with caplog.at_level(logging.WARNING, logger="app.takedown.tracker"):
        tracker.first_hits(session, "tamm-pay.xyz", None, keys, NOW)
    assert (row.gsb_last_clean_at, row.vt_last_clean_at, row.vt_checked_at, domain.gsb_first_hit_at) == (None,) * 4
    assert "ConnectTimeout" in caplog.text and "gsb-key" not in caplog.text and "vt-key" not in caplog.text


def test_failed_poll_logs_the_status_code(session, keys, monkeypatch, caplog):
    def refuse(url, key, *args, **kwargs):
        raise httpx.HTTPStatusError("403", request=httpx.Request("POST", f"{url}?key={key}"),
                                    response=httpx.Response(403, request=httpx.Request("POST", url)))

    monkeypatch.setattr(lookups, "gsb_sync", refuse)
    setup(session)
    with caplog.at_level(logging.WARNING, logger="app.takedown.tracker"):
        tracker.first_hits(session, "tamm-pay.xyz", None, keys, NOW)
    assert "403" in caplog.text and "gsb-key" not in caplog.text
