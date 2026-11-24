from datetime import UTC, datetime, timedelta

from app.models import Watchlist
from app.watch import lead_time

FIRST_SEEN = datetime(2026, 1, 1, tzinfo=UTC)


def row(**columns):
    return Watchlist(domain="x.example", next_check_at=FIRST_SEEN, expires_at=FIRST_SEEN, **columns)


def test_unpolled_domain_has_no_hours():
    assert lead_time(FIRST_SEEN, row()) == {
        "gsb": {"state": "not_polled", "at_least_hours": None},
        "vt": {"state": "not_polled", "at_least_hours": None},
    }


def test_clean_polls_count_whole_hours_to_the_last_one():
    clean = FIRST_SEEN + timedelta(hours=30, minutes=59)
    result = lead_time(FIRST_SEEN, row(gsb_last_clean_at=clean))
    assert result["gsb"] == {"state": "ahead", "at_least_hours": 30}
    assert result["vt"]["state"] == "not_polled"


def test_first_poll_already_a_hit_is_zero_hours():
    result = lead_time(FIRST_SEEN, row(vt_first_hit_at=FIRST_SEEN + timedelta(hours=2)))
    assert result["vt"] == {"state": "hit", "at_least_hours": 0}


def test_hit_after_clean_polls_keeps_the_lead():
    result = lead_time(
        FIRST_SEEN,
        row(gsb_last_clean_at=FIRST_SEEN + timedelta(hours=12), gsb_first_hit_at=FIRST_SEEN + timedelta(hours=18)),
    )
    assert result["gsb"] == {"state": "hit", "at_least_hours": 12}
