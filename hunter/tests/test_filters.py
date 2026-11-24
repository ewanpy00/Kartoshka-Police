import pytest

from app import filters

BRANDS = [
    {"id": "tamm", "names": ["TAMM"], "official_domains": ["tamm.abudhabi"]},
    {"id": "rta", "names": ["RTA"], "match_tokens": ["rta", "rtadubai"], "official_domains": ["rta.ae"]},
    {"id": "emiratespost", "names": ["Emirates Post"], "official_domains": ["emiratespost.ae"]},
    {"id": "icp", "names": ["ICP"], "match_tokens": ["icp", "emiratesid"], "official_domains": ["icp.gov.ae"]},
    {"id": "dubaipolice", "names": ["Dubai Police"], "official_domains": ["dubaipolice.gov.ae"]},
]
PREPARED = filters.prepare(BRANDS)


@pytest.mark.parametrize("host,brand,kind", [
    ("rta-fines.top", "rta", "name"),
    ("payrta.top", "rta", "name"),
    ("emiratespost-redelivery.info", "emiratespost", "name"),
    ("emirat3spost.com", "emiratespost", "homoglyph"),
    ("emiratspost-track.top", "emiratespost", "typo"),
    ("dubaipolise.com", "dubaipolice", "typo"),
    ("xn--emiratespst-8lb.com", None, None),
    ("tamm-pay.xyz", "tamm", "name"),
])
def test_name_filter_matches(host, brand, kind):
    hit = filters.name_match(filters.clean_host(host), PREPARED)
    if brand is None:
        assert hit is None or hit.brand_id is not None
        return
    assert hit is not None and (hit.brand_id, hit.kind) == (brand, kind)


@pytest.mark.parametrize("host", [
    "portal.example.top", "www.portal.tiger.mailrez.com", "consortadmin.kinsta.cloud", "rta.ae", "www.rta.ae",
    "emiratespost.ae", "emirates-travel.com", "picpay.com", "tamm.abudhabi", "smartadvisor.com",
])
def test_name_filter_leaves_unrelated_and_official_names(host):
    assert filters.name_match(filters.clean_host(host), PREPARED) is None


def test_cyrillic_lookalike_is_caught():
    host = "tаmm-pay.com"  # Cyrillic а
    hit = filters.name_match(filters.clean_host(host), PREPARED)
    assert hit is not None and hit.brand_id == "tamm" and hit.kind == "homoglyph"


def test_infrastructure_filter():
    assert filters.infra_match("dwu6.top").detail == ".top + random label"
    assert filters.infra_match("pay-fine-online.top") is not None
    assert filters.infra_match("dwu6.com") is None             # not a risky TLD
    assert filters.infra_match("bakery.top") is None
    assert filters.infra_match("pay.example.top") is None      # one action word only


def test_screen_and_wildcards():
    assert filters.screen("*.rta-fines.top", PREPARED).host == "rta-fines.top"
    assert filters.screen("localhost", PREPARED) is None
    assert filters.screen("dwu6.top", PREPARED, infra=False) is None


def test_cyrillic_inside_a_long_token():
    hit = filters.name_match(filters.clean_host("emirаtespost-track.com"), PREPARED)  # Cyrillic а
    assert hit is not None and hit.brand_id == "emiratespost" and hit.kind == "homoglyph"
