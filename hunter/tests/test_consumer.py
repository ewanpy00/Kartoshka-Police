import json
import logging

from app import filters
from app.certstream_consumer import Counters, handle_message
from app.submit import Submitter

PREPARED = filters.prepare([{"id": "tamm", "names": ["TAMM"], "official_domains": ["tamm.abudhabi"]}])


def certificate(all_domains) -> str:
    return json.dumps({"message_type": "certificate_update", "data": {"leaf_cert": {"all_domains": all_domains}}})


def run(raw: str, caplog, submitter=None, counters=None, now=1000.0):
    counters = counters or Counters()
    with caplog.at_level(logging.INFO, logger="hunter"):
        found = handle_message(raw, PREPARED, counters, submitter, now=now)
    assert all("\n" not in record.getMessage() for record in caplog.records)
    return counters, found


def test_matching_certificate_is_queued_once(caplog):
    submitter = Submitter(post=None)
    counters, found = run(certificate(["pay-tamm.com", "*.pay-tamm.com", "www.example.org"]), caplog, submitter)
    assert (counters.certificates, counters.matches) == (1, 1)
    assert [e.url for e in submitter.pending] == ["https://pay-tamm.com/"]
    assert submitter.pending[0].brand_id == "tamm" and submitter.pending[0].source == "ct"
    run(certificate(["pay-tamm.com"]), caplog, submitter)
    assert len(submitter.pending) == 1  # the same host is sent at most once a day


def test_official_names_are_not_candidates(caplog):
    counters, found = run(certificate(["www.tamm.abudhabi"]), caplog)
    assert counters.matches == 0 and found == []


def test_infrastructure_candidates_are_capped(caplog, monkeypatch):
    import app.certstream_consumer as consumer

    monkeypatch.setattr(consumer, "INFRA_PER_MINUTE", 2)
    counters = Counters()
    for n in range(5):
        run(certificate([f"ab{n}c.top"]), caplog, counters=counters, now=2000.0)
    assert counters.infra == 2


def test_other_message_types_are_ignored(caplog):
    counters, _ = run(json.dumps({"message_type": "heartbeat"}), caplog)
    assert counters.certificates == 0


def test_malformed_message_is_skipped(caplog):
    counters, _ = run("not json", caplog)
    assert counters.certificates == 0
    assert any("malformed" in r.getMessage() for r in caplog.records)
