import json
import logging
from datetime import datetime

from app import events, queue


def test_publish_sends_envelope_on_channel():
    pubsub = queue.get_redis().pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(events.CHANNEL)
    pubsub.get_message(timeout=1)
    events.publish("case.reviewed", {"domain": "tamm-pay.xyz", "decision": "confirm", "reviewer": "officer"})
    message = pubsub.get_message(timeout=2)
    pubsub.close()
    envelope = json.loads(message["data"])
    assert envelope["type"] == "case.reviewed"
    assert envelope["data"] == {"domain": "tamm-pay.xyz", "decision": "confirm", "reviewer": "officer"}
    assert datetime.fromisoformat(envelope["at"]).utcoffset().total_seconds() == 0


def test_publish_logs_and_swallows_redis_failure(monkeypatch, caplog):
    def broken():
        raise ConnectionError("redis down")

    monkeypatch.setattr(queue, "get_redis", broken)
    with caplog.at_level(logging.ERROR):
        events.publish("check.completed", {})
    assert "Could not publish check.completed event" in caplog.text


def test_published_fixture_collects_calls(published):
    events.publish("campaign.new_domain", {"campaign_id": "c1", "domain": "a.example"})
    assert published == [("campaign.new_domain", {"campaign_id": "c1", "domain": "a.example"})]


def test_cache_publish_is_a_wrapper_over_events_publish(published):
    import importlib

    from app import cache

    # conftest stubs cache.publish; reload the module to reach the real wrapper
    real = importlib.reload(cache).publish
    real({"type": "hunter.candidate", "domain": "tamm-pay.xyz", "at": "ignored"})
    assert published == [("hunter.candidate", {"domain": "tamm-pay.xyz"})]
