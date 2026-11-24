import pytest

from app.brands import load_brands
from app.config import get_settings
from app.fast.lexical import lexical
from app.normalize.unshorten import is_shortener
from app.normalize.url import normalize

BRANDS = load_brands(get_settings().data_dir)


def analyse(url):
    reasons, features, brand = lexical(normalize(url), BRANDS)
    return {r["code"] for r in reasons}, features, brand


def test_brand_action_and_risky_tld():
    codes, features, brand = analyse("https://uaepass-verify.top/login")
    assert {"BRAND_IN_DOMAIN", "ACTION_WORDS", "BRAND_ACTION", "RISKY_TLD"} <= codes
    assert brand["id"] == "uaepass"
    assert features["brand_in_domain"] == 1


def test_brand_in_subdomain_of_unrelated_domain():
    codes, _, brand = analyse("https://uaepass.login-secure.com/")
    assert "BRAND_IN_SUBDOMAIN" in codes
    assert brand["id"] == "uaepass"


def test_short_token_needs_a_whole_word():
    assert analyse("https://tammychen.io/")[2] is None
    assert analyse("https://tamm-fines.top/")[2]["id"] == "tamm"
    assert analyse("https://tammpay.com/")[2]["id"] == "tamm"


def test_lookalike_of_official_domain():
    codes, features, brand = analyse("https://uaepas.com/")
    assert "LOOKALIKE" in codes
    assert brand["id"] == "uaepass"
    assert features["lookalike_distance"] == 1


@pytest.mark.parametrize("url", ["https://team.com/", "https://band.com/", "https://dark.net/", "https://news.example/"])
def test_ordinary_words_are_not_lookalikes(url):
    codes, _, brand = analyse(url)
    assert "LOOKALIKE" not in codes and brand is None


def test_cyrillic_homoglyph():
    codes, _, brand = analyse("https://uаepass.com/")
    assert "HOMOGLYPH" in codes or "LOOKALIKE" in codes
    assert brand["id"] == "uaepass"
    assert "MIXED_SCRIPTS" in codes


def test_digit_swap_homoglyph():
    codes, _, brand = analyse("https://dubaip0lice.com/")
    assert brand["id"] == "dubaipolice"
    assert codes & {"HOMOGLYPH", "LOOKALIKE"}


def test_random_generated_name():
    codes, features, _ = analyse("https://dwu6.top/")
    assert "RANDOM_NAME" in codes and "RISKY_TLD" in codes


def test_ip_host_and_userinfo():
    codes, _, _ = analyse("http://user@192.0.2.10/pay")
    assert {"IP_HOST", "USERINFO"} <= codes


def test_free_hosting_with_brand():
    codes, _, brand = analyse("https://uaepass-login.web.app/")
    assert {"FREE_HOSTING", "BRAND_IN_DOMAIN"} <= codes
    assert brand["id"] == "uaepass"


def test_brand_in_path_on_unrelated_site():
    codes, _, brand = analyse("https://compromised-blog.example/wp-content/uaepass/login.php")
    assert "BRAND_IN_PATH" in codes
    assert brand["id"] == "uaepass"


def test_gov_lookalike():
    codes, _, _ = analyse("https://dubai-gov-fines.com/")
    assert "GOV_LOOKALIKE" in codes


def test_arabic_action_word_in_path():
    codes, _, _ = analyse("https://pay-now.example/دفع-مخالفات")
    assert "ACTION_WORDS" in codes


def test_shortener_hosts():
    assert is_shortener("bit.ly") and is_shortener("www.tinyurl.com")
    assert not is_shortener("example.com")


def test_normalize_splits_registrable_domain():
    n = normalize("https://a.b.uaepass-verify.co.uk/x?y=1")
    assert n.domain == "uaepass-verify.co.uk"
    assert n.subdomain == "a.b"
    assert n.tld == "co.uk"
    assert n.domain_label == "uaepass-verify"
    assert n.params == {"y": "1"}


def test_country_domains_only_for_brands_that_declare_them():
    from app.brands import is_official, load_global_brands

    by_id = {b["id"]: b for b in load_global_brands(get_settings().data_dir)}
    assert is_official("google.com.et", by_id["google"])
    assert is_official("www.google.co.ck", by_id["google"])
    assert not is_official("google-login.com.et", by_id["google"])
    assert not is_official("google.secure-login.ru", by_id["google"])
    assert not is_official("roblox.com.et", by_id["roblox"])


def test_brand_spelled_across_hyphens():
    from app.brands import token_in_label

    actions = frozenset({"login", "pay"})
    assert token_in_label("uaepass", "uae-pass-login", actions)
    assert token_in_label("dubaipolice", "dubai-police-gov", actions)
    assert not token_in_label("mashreq", "mashreqia-cafe", actions)
    assert not token_in_label("salik", "salikhan-photography", actions)
    assert not token_in_label("darb", "darbar-indian-cuisine", actions)
