"""The lead-time shape served on the case card: first hits from `domains`, clean polls from `watchlist`."""
from datetime import UTC, datetime, timedelta

from app.models import Domain, Watchlist
from app.takedown.tracker import lead_time

FIRST_SEEN = datetime(2026, 1, 1, tzinfo=UTC)


def watch(**columns):
    return Watchlist(domain="x.example", next_check_at=FIRST_SEEN, expires_at=FIRST_SEEN, **columns)


def hit(**columns):
    return Domain(domain="x.example", status="confirmed", **columns)


def test_unpolled_domain_has_no_hours():
    assert lead_time(FIRST_SEEN, None, None) == {
        "gsb": {"state": "not_polled", "at_least_hours": None},
        "vt": {"state": "not_polled", "at_least_hours": None},
    }


def test_clean_polls_count_whole_hours_to_the_last_one():
    clean = FIRST_SEEN + timedelta(hours=30, minutes=59)
    result = lead_time(FIRST_SEEN, hit(), watch(gsb_last_clean_at=clean))
    assert result["gsb"] == {"state": "ahead", "at_least_hours": 30}
    assert result["vt"]["state"] == "not_polled"


def test_first_poll_already_a_hit_is_zero_hours():
    result = lead_time(FIRST_SEEN, hit(vt_first_hit_at=FIRST_SEEN + timedelta(hours=2)), watch())
    assert result["vt"] == {"state": "hit", "at_least_hours": 0}


def test_hit_after_clean_polls_keeps_the_lead():
    result = lead_time(FIRST_SEEN, hit(gsb_first_hit_at=FIRST_SEEN + timedelta(hours=18)),
                       watch(gsb_last_clean_at=FIRST_SEEN + timedelta(hours=12)))
    assert result["gsb"] == {"state": "hit", "at_least_hours": 12}


def test_a_hit_without_a_watchlist_row_is_still_reported():
    result = lead_time(FIRST_SEEN, hit(gsb_first_hit_at=FIRST_SEEN + timedelta(hours=3)), None)
    assert result["gsb"] == {"state": "hit", "at_least_hours": 0}


def test_a_clean_poll_after_the_hit_does_not_count():
    result = lead_time(FIRST_SEEN, hit(gsb_first_hit_at=FIRST_SEEN + timedelta(hours=5)),
                       watch(gsb_last_clean_at=FIRST_SEEN + timedelta(hours=40)))
    assert result["gsb"] == {"state": "hit", "at_least_hours": 0}
