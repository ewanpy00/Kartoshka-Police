import asyncio

from app import submit
from app.submit import Entry, Submitter


def entry(n: int, deep: bool = False) -> Entry:
    return Entry("ct", f"https://a{n}-tamm.top/", "tamm", "name", deep)


def test_a_failed_post_is_kept_and_sent_by_the_next_flush():
    bodies, up = [], []

    async def post(body):
        if not up:
            raise OSError("core restarting")
        bodies.append(body)

    submitter = Submitter(post=post)
    for n in range(3):
        submitter.add(entry(n))
    assert asyncio.run(submitter.flush()) == 0
    assert len(submitter.pending) == 3 and bodies == []
    up.append(True)
    assert asyncio.run(submitter.flush()) == 3
    assert submitter.pending == [] and len(bodies[0]["entries"]) == 3


def test_a_failure_after_the_first_group_keeps_only_the_unsent_group():
    calls = []

    async def post(body):
        calls.append(body["check_mode"])
        if len(calls) == 2:
            raise OSError("down")

    submitter = Submitter(post=post)
    submitter.add(entry(1, deep=True))
    submitter.add(entry(2))
    assert asyncio.run(submitter.flush()) == 1
    assert [e.url for e in submitter.pending] == ["https://a2-tamm.top/"]


def test_a_host_is_queued_once_a_day_per_source():
    submitter = Submitter(post=None)
    assert submitter.add(entry(1), now=0.0) is True
    assert submitter.add(entry(1), now=60.0) is False
    assert submitter.add(entry(1), now=submit.SEEN_FOR_S + 1) is True


def test_the_pending_queue_is_capped(monkeypatch):
    monkeypatch.setattr(submit, "MAX_PENDING", 2)
    submitter = Submitter(post=None)
    results = [submitter.add(entry(n)) for n in range(4)]
    assert results == [True, True, False, False]
    assert submitter.dropped == 2


def test_a_flush_sends_at_most_one_batch_per_group_chunk(monkeypatch):
    monkeypatch.setattr(submit, "BATCH", 2)
    sizes = []

    async def post(body):
        sizes.append(len(body["entries"]))

    submitter = Submitter(post=post)
    for n in range(5):
        submitter.add(entry(n))
    assert asyncio.run(submitter.flush()) == 5
    assert sizes == [2, 2, 1]


def test_an_empty_write_token_is_warned_about(monkeypatch, caplog):
    import logging

    monkeypatch.setattr(submit, "TOKEN", "")
    with caplog.at_level(logging.WARNING, logger="hunter"):
        Submitter()
    assert "CORE_WRITE_TOKEN is empty" in caplog.text


def test_the_per_minute_cap_keeps_the_rest_pending_until_the_minute_passes(monkeypatch):
    monkeypatch.setattr(submit, "SUBMIT_PER_MINUTE", 2)
    bodies = []

    async def post(body):
        bodies.append(body)

    submitter = Submitter(post=post)
    for n in range(5):
        submitter.add(entry(n))
    assert asyncio.run(submitter.flush()) == 2
    assert asyncio.run(submitter.flush()) == 0
    assert len(submitter.pending) == 3
    submitter._window_start -= 61
    assert asyncio.run(submitter.flush()) == 2
    assert len(submitter.pending) == 1
