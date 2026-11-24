import time
from datetime import UTC, datetime, timedelta

import pytest

from app.brands import load_brands
from app.config import get_settings
from app.deep.score import score

NOW = datetime(2026, 11, 24, tzinfo=UTC)
BRANDS = load_brands(get_settings().data_dir)


def run(host="example.com", text="", registered_at=None, credential_form=False, facts_unavailable=False):
    return score(host, text, registered_at, credential_form, facts_unavailable, BRANDS, NOW)


def codes(result):
    return [reason["code"] for reason in result["reasons"]]


def test_plain_page_is_allowed():
    result = run()
    assert (result["score"], result["verdict"], result["reasons"], result["brand"]) == (0, "allow", [], None)


@pytest.mark.parametrize(
    ("kwargs", "expected_codes", "expected_score", "expected_verdict"),
    [
        ({"host": "tamm-pay.example"}, ["BRAND_LOOKALIKE_DOMAIN"], 40, "warn"),
        ({"credential_form": True}, ["CREDENTIAL_FORM"], 25, "allow"),
        ({"text": "Pay your TAMM fines"}, ["BRAND_IN_PAGE"], 20, "allow"),
        ({"registered_at": (NOW - timedelta(days=5)).isoformat()}, ["NEW_DOMAIN"], 15, "allow"),
        ({"registered_at": (NOW - timedelta(days=30)).isoformat()}, [], 0, "allow"),
        ({"host": "tamm-pay.example", "credential_form": True}, ["BRAND_LOOKALIKE_DOMAIN", "CREDENTIAL_FORM"], 70, "block"),
        ({"host": "uaepass-login.example", "text": "UAE PASS"}, ["BRAND_LOOKALIKE_DOMAIN", "BRAND_IN_PAGE"], 60, "warn"),
        ({"facts_unavailable": True}, ["PAGE_FACTS_UNAVAILABLE"], 30, "warn"),
        ({"host": "tamm-pay.example", "facts_unavailable": True}, ["BRAND_LOOKALIKE_DOMAIN", "PAGE_FACTS_UNAVAILABLE"], 70, "block"),
        ({"credential_form": True, "text": "tamm", "registered_at": (NOW - timedelta(days=1)).isoformat()}, ["CREDENTIAL_FORM", "BRAND_IN_PAGE", "NEW_DOMAIN"], 60, "warn"),
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


@pytest.mark.parametrize(
    "host",
    ["rustammullagaliev.ru", "tammycarusofineart.com", "janaoseimaisoqueescreveresgotammedetantoblkplease.autos"],
)
def test_brand_inside_an_unrelated_word_is_not_a_lookalike(host):
    assert "BRAND_LOOKALIKE_DOMAIN" not in codes(run(host=host))


@pytest.mark.parametrize(
    ("host", "brand_id"),
    [
        ("tamm-pay.xyz", "tamm"),
        ("pay.tamm-services.com", "tamm"),
        ("uaepass-login.top", "uaepass"),
        ("uaepasslogin.xyz", "uaepass"),
        ("verifyuaepass.xyz", "uaepass"),
        ("secure-uae-pass.top", "uaepass"),
        ("uae-pass-login.com", "uaepass"),
        ("my-uae-pass.xyz", "uaepass"),
    ],
)
def test_brand_token_or_brand_joined_to_its_keyword_is_a_lookalike(host, brand_id):
    result = run(host=host)
    assert "BRAND_LOOKALIKE_DOMAIN" in codes(result)
    assert result["brand"]["id"] == brand_id


def test_brand_joined_to_a_word_that_is_not_its_keyword_is_not_matched():
    assert run(host="tammpay.xyz")["reasons"] == []


@pytest.mark.parametrize("host", ["tamm.abudhabi", "www.tamm.abudhabi", "uaepass.ae", "login.id.uaepass.ae"])
def test_official_domains_never_match(host):
    assert run(host=host)["reasons"] == []


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


@pytest.mark.parametrize("registered_at", ["yesterday", "", None])
def test_unparseable_registration_date_is_unknown(registered_at):
    assert run(registered_at=registered_at)["reasons"] == []


def test_registration_date_without_a_zone_is_read_as_utc():
    assert codes(run(registered_at="2026-11-23T00:00:00")) == ["NEW_DOMAIN"]


def test_very_long_host_of_single_letter_tokens_is_fast_and_does_not_match():
    host = ".".join("-".join("a" * 31) for _ in range(31))
    started = time.perf_counter()
    result = run(host=host)
    assert time.perf_counter() - started < 0.1
    assert result["reasons"] == []


def test_label_longer_than_a_dns_label_is_still_matched():
    host = "x" * 50 + "-uaepass-" + "y" * 11 + ".example"
    assert "BRAND_LOOKALIKE_DOMAIN" in codes(run(host=host))


@pytest.mark.parametrize("text", ["Tammer-Golf admin", "Tammy's shop", "tammy", "retamm"])
def test_brand_inside_a_longer_word_is_not_named_in_the_page(text):
    assert run(text=text)["reasons"] == []


@pytest.mark.parametrize(
    ("text", "brand_id"),
    [("Pay your TAMM fines", "tamm"), ("tamm.", "tamm"), ("UAE PASS login", "uaepass"), ("الهوية الرقمية الجديدة", "uaepass")],
)
def test_brand_named_as_a_whole_word_is_found_in_the_page(text, brand_id):
    result = run(text=text)
    assert codes(result) == ["BRAND_IN_PAGE"]
    assert result["brand"]["id"] == brand_id


def test_credential_form_alone_is_allowed():
    assert (run(credential_form=True)["score"], run(credential_form=True)["verdict"]) == (25, "allow")


def test_lookalike_with_credential_form_is_floored_to_70_and_blocks():
    result = run(host="tamm-pay.example", credential_form=True)
    assert (result["score"], result["verdict"]) == (70, "block")


def test_brand_in_page_with_credential_form_is_a_warning():
    result = run(text="Pay your TAMM fines", credential_form=True)
    assert (result["score"], result["verdict"]) == (45, "warn")


def test_auto_confirm_threshold_is_reachable():
    result = run(host="tamm-pay.example", text="TAMM", credential_form=True, registered_at=(NOW - timedelta(days=1)).isoformat())
    assert result["score"] == 100
