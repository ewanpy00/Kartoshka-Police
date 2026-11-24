from app import events


def test_event_is_published_only_after_commit(session, published):
    events.publish_after_commit(session, "case.reviewed", {"domain": "a.example"})
    assert published == []
    session.commit()
    assert published == [("case.reviewed", {"domain": "a.example"})]


def test_nothing_is_published_after_a_rollback(session, published):
    events.publish_after_commit(session, "case.reviewed", {"domain": "a.example"})
    session.rollback()
    session.commit()
    assert published == []


def test_queued_events_arrive_in_order_and_only_once(session, published):
    events.publish_after_commit(session, "case.reviewed", {"n": 1})
    events.publish_after_commit(session, "campaign.new_domain", {"n": 2})
    session.commit()
    session.commit()
    assert published == [("case.reviewed", {"n": 1}), ("campaign.new_domain", {"n": 2})]
