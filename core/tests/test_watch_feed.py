from datetime import UTC, datetime, timedelta

from admin_factories import AUTH, add_check


def test_feed_lists_only_hunter_checks_newest_first(client, session):
    now = datetime.now(UTC)
    older = add_check(session, "older-tamm.xyz", source="hunter", created_at=now - timedelta(hours=1))
    newer = add_check(session, "newer-tamm.xyz", source="hunter", brand="TAMM")
    add_check(session, "from-api.example", source="api")
    session.commit()
    response = client.get("/v1/admin/feed", headers=AUTH)
    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["check_id"] for item in items] == [newer.id, older.id]
    assert items[0]["brand"] == "TAMM"
    assert set(items[0]) == {"check_id", "domain", "url", "brand", "verdict", "score", "created_at"}


def test_feed_honours_the_limit(client, session):
    for i in range(3):
        add_check(session, f"h{i}.example", source="hunter")
    session.commit()
    assert len(client.get("/v1/admin/feed?limit=2", headers=AUTH).json()["items"]) == 2
