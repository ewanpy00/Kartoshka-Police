from datetime import UTC, datetime, timedelta

import pytest

from app.brands import load_brands
from app.config import get_settings
from app.deep.score import score

NOW = datetime(2026, 11, 24, tzinfo=UTC)
BRANDS = load_brands(get_settings().data_dir)


def run(host="example.com", text="", registered_at=None, credential_form=False):
    return score(host, text, registered_at, credential_form, BRANDS, NOW)


def codes(result):
    return [reason["code"] for reason in result["reasons"]]


def test_plain_page_is_allowed():
    result = run()
    assert (result["score"], result["verdict"], result["reasons"], result["brand"]) == (0, "allow", [], None)


@pytest.mark.parametrize(
    ("kwargs", "expected_codes", "expected_score", "expected_verdict"),
    [
        ({"host": "tamm-pay.example"}, ["BRAND_LOOKALIKE_DOMAIN"], 40, "warn"),
        ({"credential_form": True}, ["CREDENTIAL_FORM"], 30, "warn"),
        ({"text": "Pay your TAMM fines"}, ["BRAND_IN_PAGE"], 20, "allow"),
        ({"registered_at": (NOW - timedelta(days=5)).isoformat()}, ["NEW_DOMAIN"], 15, "allow"),
        ({"registered_at": (NOW - timedelta(days=30)).isoformat()}, [], 0, "allow"),
        ({"host": "tamm-pay.example", "credential_form": True}, ["BRAND_LOOKALIKE_DOMAIN", "CREDENTIAL_FORM"], 70, "block"),
        ({"host": "uaepass-login.example", "text": "UAE PASS"}, ["BRAND_LOOKALIKE_DOMAIN", "BRAND_IN_PAGE"], 60, "warn"),
        ({"credential_form": True, "text": "tamm", "registered_at": (NOW - timedelta(days=1)).isoformat()}, ["CREDENTIAL_FORM", "BRAND_IN_PAGE", "NEW_DOMAIN"], 65, "warn"),
    ],
)
def test_weights_and_verdicts(kwargs, expected_codes, expected_score, expected_verdict):
    result = run(**kwargs)
    assert codes(result) == expected_codes
    assert (result["score"], result["verdict"]) == (expected_score, expected_verdict)


def test_lookalike_with_credential_form_is_exactly_70_and_blocks():
    result = run(host="tamm-pay.example", credential_form=True)
    assert result["score"] == 70
    assert result["verdict"] == "block"


def test_score_is_capped_at_100():
    result = run(
        host="tamm-pay.example",
        text="TAMM",
        registered_at=(NOW - timedelta(days=2)).isoformat(),
        credential_form=True,
    )
    assert result["score"] == 100
    assert result["brand"]["id"] == "tamm"


def test_official_domain_and_its_subdomains_are_not_lookalikes():
    for host in ("tamm.abudhabi", "www.tamm.abudhabi"):
        assert run(host=host, text="TAMM")["reasons"] == []


def test_short_arabic_brand_name_is_not_matched_in_text():
    assert run(text="تم الدفع")["reasons"] == []


def test_every_reason_carries_both_languages_and_a_source():
    result = run(host="tamm-pay.example", credential_form=True, registered_at=NOW.isoformat())
    for reason in result["reasons"]:
        assert set(reason) == {"code", "weight", "source", "en", "ar"}
        assert reason["source"] in ("sandbox", "rdap")
        assert reason["en"] and reason["ar"]
    assert "TAMM" in result["reasons"][0]["en"]
