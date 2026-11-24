"""Impact and quality numbers (D6)."""
from datetime import timedelta

from factories import NOW, make_check, with_evidence

from app import review as decisions
from app.admin import stats
from app.models import Domain, FeedEntry

AUTH = {"Authorization": "Bearer test-token"}


def test_lead_time_for_confirmed_ct_domains(session):
    session.add(FeedEntry(source="ct", url="https://lead-a.top/", domain="lead-a.top", brand_id="tamm",
                          first_seen=NOW - timedelta(hours=30)))
    session.add(FeedEntry(source="ct", url="https://lead-b.top/", domain="lead-b.top", first_seen=NOW - timedelta(hours=5)))
    session.add(FeedEntry(source="ct", url="https://lead-open.top/", domain="lead-open.top", first_seen=NOW - timedelta(hours=2)))
    for site in ("lead-a.top", "lead-b.top"):
        check = make_check(session, site, 90)
        decisions.review(session, with_evidence(session, check), "confirm", "Officer K")
    session.get(Domain, "lead-a.top").gsb_first_hit_at = NOW - timedelta(hours=6)
    session.flush()
    rows = {r["domain"]: r for r in stats.lead_times(session, NOW)}
    assert set(rows) == {"lead-a.top", "lead-b.top"}  # lead-open.top was never confirmed
    assert rows["lead-a.top"]["lead_vs_gsb_h"] == 24.0 and not rows["lead-a.top"]["lead_vs_gsb_open"]
    assert rows["lead-b.top"]["lead_vs_gsb_h"] == 5.0 and rows["lead-b.top"]["lead_vs_gsb_open"]
    assert rows["lead-a.top"]["hours_to_confirm"] is not None


def test_quality_compares_the_verdict_before_review_with_the_decision(session):
    good = make_check(session, "qa-block.top", 90)
    decisions.review(session, with_evidence(session, good), "confirm", "Officer L")
    wrong = make_check(session, "qa-false.top", 85)
    decisions.review(session, with_evidence(session, wrong), "reject", "Officer L", "legitimate_site")
    unsure = make_check(session, "qa-warn.top", 50)
    decisions.review(session, with_evidence(session, unsure), "reject", "Officer L", "insufficient_evidence")
    session.flush()
    result = stats.quality(session, NOW + timedelta(minutes=1))
    assert result["by_band"]["block"]["confirmed"] >= 1 and result["by_band"]["block"]["cleared"] >= 1
    assert result["by_band"]["warn"]["other_reject"] >= 1
    assert 0 < result["block_precision"] < 1 and result["false_blocks"] >= 1


def test_stats_route_shapes_the_series(client, session):
    make_check(session, "st-chart.top", 80, hours_ago=2)
    body = client.get("/v1/admin/stats?range=24h", headers=AUTH).json()
    assert len(body["series"]["buckets"]) == len(body["series"]["checks"]) >= 24
    assert sum(body["series"]["checks"]) >= 1 and body["totals"]["block"] >= 1
    assert "quality" in body and "lead_time" in body
    week = client.get("/v1/admin/stats?range=7d", headers=AUTH).json()
    assert 7 <= len(week["series"]["buckets"]) <= 8
    assert client.get("/v1/admin/stats?range=1y", headers=AUTH).status_code == 422
