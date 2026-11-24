from app.infra import location

HOSTED = {"registrar": "NameCheap", "ip_country": "NL", "ip_owner": "Hoster BV", "ip_network": "203.0.113.0/24", "proxy": None}


def test_direct_host_reports_country_registrar_and_owner():
    assert location(HOSTED) == {
        "hosted_in": "NL", "registered_through": "NameCheap", "network_owner": "Hoster BV", "behind_proxy": False,
    }


def test_proxy_hides_the_true_host_but_keeps_the_registrar():
    assert location({**HOSTED, "proxy": "cloudflare"}) == {
        "hosted_in": None, "registered_through": "NameCheap", "network_owner": None, "behind_proxy": True,
    }


def test_network_is_used_when_the_owner_is_unknown():
    assert location({**HOSTED, "ip_owner": None})["network_owner"] == "203.0.113.0/24"


def test_missing_fields_are_none():
    assert location({}) == {"hosted_in": None, "registered_through": None, "network_owner": None, "behind_proxy": False}
