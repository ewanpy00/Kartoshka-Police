import json
from pathlib import Path

import httpx
import pytest

from app.config import get_settings
from app.deep import rdap

FIXTURES = Path(__file__).parent / "deep_fixtures"
DOMAIN_DOCUMENT = json.loads((FIXTURES / "rdap_domain.json").read_text())
IP_DOCUMENT = json.loads((FIXTURES / "rdap_ip.json").read_text())


def client_for(routes: dict[str, dict | int]) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        answer = routes.get(request.url.path, 404)
        return httpx.Response(answer) if isinstance(answer, int) else httpx.Response(200, json=answer)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_saved_responses_are_parsed():
    client = client_for({"/domain/tamm-pay.example": DOMAIN_DOCUMENT, "/ip/203.0.113.5": IP_DOCUMENT})
    assert rdap.lookup(client, "tamm-pay.example", "203.0.113.5") == {
        "rdap_status": "ok",
        "registrar": "Example Registrar LLC",
        "registered_at": "2026-11-20T10:00:00Z",
        "abuse_emails": ["abuse@registrar.example"],
        "name_servers": ["ns1.example-dns.net", "ns2.example-dns.net"],
        "ip": "203.0.113.5",
        "ip_network": "EXAMPLE-NET",
        "ip_owner": "Example Hosting BV",
        "ip_country": "NL",
        "ip_abuse_emails": ["abuse@hosting.example"],
        "proxy": None,
    }


def test_failed_lookup_leaves_fields_null_and_never_invents_values():
    result = rdap.lookup(client_for({"/domain/gone.example": 500, "/ip/203.0.113.5": 500}), "gone.example", "203.0.113.5")
    assert result == {**rdap.EMPTY, "ip": "203.0.113.5"}
    assert result["rdap_status"] == "failed"


def test_unreachable_rdap_service_is_a_failed_lookup():
    def refuse(request):
        raise httpx.ConnectError("no route")

    client = httpx.Client(transport=httpx.MockTransport(refuse))
    assert rdap.lookup(client, "tamm-pay.example", None) == rdap.EMPTY


def test_missing_ip_rdap_marks_the_record_failed_but_keeps_domain_fields():
    result = rdap.lookup(client_for({"/domain/tamm-pay.example": DOMAIN_DOCUMENT}), "tamm-pay.example", "203.0.113.5")
    assert result["rdap_status"] == "failed"
    assert result["registrar"] == "Example Registrar LLC"
    assert result["ip_network"] is None


def test_subdomain_retries_the_parent_after_a_404_at_most_three_times():
    asked = []

    def handler(request):
        asked.append(request.url.path)
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert rdap.fetch_domain(client, "a.b.c.d.example") is None
    assert asked == ["/domain/a.b.c.d.example", "/domain/b.c.d.example", "/domain/c.d.example"]


def test_subdomain_uses_the_parent_record():
    client = client_for({"/domain/example.net": DOMAIN_DOCUMENT})
    assert rdap.fetch_domain(client, "login.example.net") == DOMAIN_DOCUMENT


@pytest.mark.parametrize("ip", ["104.16.1.1", "2606:4700::1"])
def test_cloudflare_is_detected_by_address_range(ip):
    result = rdap.lookup(client_for({"/domain/x.example": DOMAIN_DOCUMENT}), "x.example", ip)
    assert result["proxy"] == "cloudflare"


def test_cloudflare_is_detected_by_name_server():
    document = {**DOMAIN_DOCUMENT, "nameservers": [{"ldhName": "ada.ns.cloudflare.com"}]}
    result = rdap.lookup(client_for({"/domain/x.example": document}), "x.example", "203.0.113.5")
    assert result["proxy"] == "cloudflare"


def test_cloudflare_ranges_come_from_the_data_file():
    assert rdap.cloudflare_networks(get_settings().data_dir)
