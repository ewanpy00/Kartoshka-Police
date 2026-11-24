import pytest
from sqlalchemy import select

from app.evidence.store import GENESIS_HASH, append_evidence, screenshot_path, verify_chain
from app.models import Artifact
from evidence_helpers import add_record, make_payload, png_bytes


def test_three_records_form_an_intact_chain(session):
    records = [add_record(session, f"c{i}") for i in range(3)]
    assert records[0].prev_hash == GENESIS_HASH
    assert records[1].prev_hash == records[0].hash
    result = verify_chain(session)
    assert result["intact"] and result["first_broken"] is None
    assert result["count"] >= 3


def test_altered_payload_is_named(session):
    add_record(session, "c0")
    middle = add_record(session, "c1")
    add_record(session, "c2")
    middle.payload = {**middle.payload, "risk": {**middle.payload["risk"], "score": 1}}
    session.flush()
    broken = verify_chain(session)["first_broken"]
    assert broken["id"] == middle.id
    assert broken["reason"] == "payload_hash_mismatch"


def test_altered_prev_hash_is_named(session):
    add_record(session, "c0")
    second = add_record(session, "c1")
    second.prev_hash = "f" * 64
    session.flush()
    broken = verify_chain(session)["first_broken"]
    assert broken["id"] == second.id
    assert broken["reason"] == "prev_hash_mismatch"


def test_floats_are_rejected(session):
    payload = make_payload()
    payload["risk"]["score"] = 85.5
    with pytest.raises(ValueError):
        add_record(session, "c0", payload)


def test_screenshot_is_hashed_and_stored_as_artifact(session, tmp_path):
    (tmp_path / "shot.png").write_bytes(png_bytes())
    evidence = add_record(session, "c0", screenshot_file="shot.png", captures_dir=tmp_path)
    screenshot = evidence.payload["capture"]["screenshot"]
    assert screenshot["file"] == "shot.png" and len(screenshot["sha256"]) == 64
    artifact = session.scalar(select(Artifact).where(Artifact.evidence_id == evidence.id))
    assert artifact.sha256 == screenshot["sha256"]
    assert screenshot_path(evidence, captures_dir=tmp_path) == (tmp_path / "shot.png").resolve()


def test_screenshot_is_none_without_a_file(session, tmp_path):
    evidence = add_record(session, "c0")
    assert evidence.payload["capture"]["screenshot"] is None
    assert screenshot_path(evidence, captures_dir=tmp_path) is None


@pytest.mark.parametrize("name", ["../../etc/passwd", "a/b.png", "..", "missing.png"])
def test_unsafe_or_missing_screenshot_names_resolve_to_none(session, tmp_path, name):
    evidence = add_record(session, "c0")
    evidence.payload = {**evidence.payload, "capture": {"screenshot": {"file": name, "sha256": "0" * 64}}}
    assert screenshot_path(evidence, captures_dir=tmp_path) is None
