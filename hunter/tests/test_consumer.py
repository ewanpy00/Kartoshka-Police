import json
import logging

import pytest

from app.certstream_consumer import Counters, handle_message

BRANDS = [{"id": "tamm", "names": ["TAMM"], "official_domains": ["tamm.abudhabi"]}]


def certificate(all_domains) -> str:
    return json.dumps(
        {
            "message_type": "certificate_update",
            "data": {"leaf_cert": {"all_domains": all_domains}},
        }
    )


def run(raw: str, caplog) -> Counters:
    counters = Counters()
    with caplog.at_level(logging.INFO, logger="hunter"):
        handle_message(raw, BRANDS, counters)
    assert all("\n" not in record.getMessage() for record in caplog.records)
    return counters


def test_matching_certificate_is_logged_and_counted(caplog):
    counters = run(certificate(["pay-tamm.com"]), caplog)
    assert (counters.certificates, counters.matches) == (1, 1)
    assert "match brand=tamm domain=pay-tamm.com" in caplog.text


def test_all_domains_not_a_list_is_skipped_with_warning(caplog):
    counters = run(certificate("tamm.example.com"), caplog)
    assert counters.certificates == 0
    assert caplog.records[0].levelno == logging.WARNING


def test_non_string_entry_is_ignored(caplog):
    counters = run(certificate([None, 5, "tamm-fines.com"]), caplog)
    assert (counters.certificates, counters.matches) == (1, 1)


def test_domain_with_newline_is_dropped(caplog):
    counters = run(certificate(["a.com\\nINFO forged tamm", "x\ntamm.com"]), caplog)
    assert counters.matches == 0
    assert "forged" not in caplog.text


@pytest.mark.parametrize("raw", ["not json", "[]", '{"message_type": "certificate_update"}'])
def test_malformed_message_is_skipped_with_warning(raw, caplog):
    counters = run(raw, caplog)
    assert counters.certificates == 0
    assert caplog.records[0].levelno == logging.WARNING


def test_other_message_types_are_ignored_silently(caplog):
    counters = run(json.dumps({"message_type": "heartbeat"}), caplog)
    assert counters.certificates == 0
    assert not caplog.records
