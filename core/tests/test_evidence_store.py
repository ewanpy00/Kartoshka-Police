"""Evidence chain: append under the advisory lock, first broken row named, append-only trigger, screenshot reads."""
import pytest
from factories import make_check
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from app.config import Settings
from app.evidence import store
from app.models import Artifact, Evidence

PNG = store.PNG_SIGNATURE + b"\x00" * 16


def add(session, name: str, **payload):
    check = make_check(session, f"{name}.example", 90)
    return store.append(session, check.id, check.domain, {"url": check.url, "domain": check.domain, "score": 90, **payload})


def tamper(session, sql: str, **params):
    """The database refuses UPDATE on evidence; switch the trigger off inside this rolled-back test transaction."""
    session.execute(text("ALTER TABLE evidence DISABLE TRIGGER evidence_no_update"))
    session.execute(text(sql), params)
    session.expire_all()


def test_records_form_an_intact_chain(session):
    first, second, third = (add(session, f"chain{i}") for i in range(3))
    assert second.prev_hash == first.hash and third.prev_hash == second.hash
    assert first.seq < second.seq < third.seq
    result = store.verify(session)
    assert result["ok"] and result["first_broken"] is None and result["head"] == third.hash


def test_append_takes_the_chain_lock_and_assigns_seq_either_way(session):
    evidence = add(session, "locked")
    held = session.scalar(text("SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' AND objid = :key AND granted"),
                          {"key": store.CHAIN_LOCK})
    assert held >= 1 and evidence.seq is not None  # code-assigned or database-generated: set after append


def test_altered_payload_is_named_with_id_and_seq(session):
    add(session, "p0")
    middle = add(session, "p1")
    add(session, "p2")
    tamper(session, "UPDATE evidence SET payload = CAST(:p AS json) WHERE id = :id", p='{"score": 1}', id=middle.id)
    broken = store.verify(session)["first_broken"]
    assert broken == {"id": middle.id, "seq": middle.seq, "reason": "payload_hash_mismatch"}


def test_altered_prev_hash_is_named(session):
    add(session, "q0")
    second = add(session, "q1")
    tamper(session, "UPDATE evidence SET prev_hash = :h WHERE id = :id", h="f" * 64, id=second.id)
    broken = store.verify(session)["first_broken"]
    assert broken["id"] == second.id and broken["reason"] == "prev_hash_mismatch"


def test_database_refuses_update_and_delete(session):
    evidence = add(session, "frozen")
    for sql in ("UPDATE evidence SET domain = 'x.example' WHERE id = :id", "DELETE FROM evidence WHERE id = :id"):
        with pytest.raises(DBAPIError):
            with session.begin_nested():
                session.execute(text(sql), {"id": evidence.id})


@pytest.fixture
def captures(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "get_settings", lambda: Settings(captures_dir=str(tmp_path)))
    return tmp_path


def with_shot(session, path, name="shot"):
    evidence = add(session, name)
    session.add(Artifact(evidence_id=evidence.id, kind="screenshot", sha256="0" * 64, path=str(path)))
    session.flush()
    return evidence


def test_screenshot_is_served_only_when_png_inside_captures(session, captures, tmp_path_factory):
    (captures / "ok.png").write_bytes(PNG)
    assert store.screenshot_png(session, with_shot(session, captures / "ok.png", "s1").id) == PNG
    (captures / "fake.png").write_text("<html>not a png</html>")
    assert store.screenshot_png(session, with_shot(session, captures / "fake.png", "s2").id) is None
    outside = tmp_path_factory.mktemp("outside") / "secret.png"
    outside.write_bytes(PNG)
    assert store.screenshot_png(session, with_shot(session, outside, "s3").id) is None
    assert store.screenshot_png(session, with_shot(session, captures / ".." / outside.name, "s4").id) is None
    assert store.screenshot_png(session, with_shot(session, captures / "missing.png", "s5").id) is None
    assert store.screenshot_png(session, add(session, "none").id) is None
    assert session.scalar(select(Evidence.id).limit(1))
