from app.matcher import match_domains

BRANDS = [
    {
        "id": "uaepass",
        "names": ["UAE PASS", "الهوية الرقمية", "uaepass", "uae-pass"],
        "official_domains": ["uaepass.ae"],
    },
    {"id": "tamm", "names": ["TAMM", "تم", "tamm"], "official_domains": ["tamm.abudhabi"]},
    {"id": "arabiconly", "names": ["بنك"], "official_domains": []},
]


def test_brand_name_inside_domain_matches():
    assert match_domains(["uaepass-login.example.com"], BRANDS) == [
        ("uaepass", "uaepass-login.example.com")
    ]


def test_spaced_name_is_joined_and_hyphenated_name_kept():
    assert match_domains(["secure-uae-pass.top"], BRANDS) == [
        ("uaepass", "secure-uae-pass.top")
    ]


def test_official_domain_and_subdomain_do_not_match():
    assert match_domains(["uaepass.ae", "login.uaepass.ae"], BRANDS) == []


def test_lookalike_of_official_domain_matches():
    assert match_domains(["notuaepass.ae"], BRANDS) == [("uaepass", "notuaepass.ae")]


def test_wildcard_prefix_is_stripped():
    assert match_domains(["*.tamm-fines.com"], BRANDS) == [("tamm", "tamm-fines.com")]


def test_wildcard_of_official_domain_does_not_match():
    assert match_domains(["*.tamm.abudhabi"], BRANDS) == []


def test_unrelated_domain_does_not_match():
    assert match_domains(["example.org", "shop.example.com"], BRANDS) == []


def test_arabic_names_are_skipped_without_error():
    assert match_domains(["بنك.example.com", "example.com"], BRANDS) == []


def test_brand_with_only_id_still_matches():
    brands = [{"id": "dewa", "names": ["هيئة"], "official_domains": ["dewa.gov.ae"]}]
    assert match_domains(["dewa-pay.com"], brands) == [("dewa", "dewa-pay.com")]
