"""Who receives a takedown request for a domain (docs/admin-dashboard.md, "Takedown").

| Recipient         | Source                                                                               |
|-------------------|--------------------------------------------------------------------------------------|
| registrar         | `abuse_emails` of the domain's RDAP record                                            |
| hosting provider  | RDAP for the IP (IANA IPv4/IPv6 bootstrap), the entity with the `abuse` role           |
| Cloudflare        | instead of the host when the IP is in AS13335 or the name servers are Cloudflare's     |
| aeDA (TDRA)       | `.ae` domains                                                                          |
| Google Safe Browsing | always                                                                              |

A recipient without an email gets a form link instead; the officer submits it by hand. Nothing here
sends anything.
"""
import ipaddress
import re
from dataclasses import dataclass

import httpx

from app import cache
from app.fast import rdap

IP_BOOTSTRAP = {4: "https://data.iana.org/rdap/ipv4.json", 6: "https://data.iana.org/rdap/ipv6.json"}
BOOTSTRAP_TTL_S = 24 * 3600
IP_TTL_S = 7 * 24 * 3600
CLOUDFLARE_ASN = "13335"
CLOUDFLARE_FORM = "https://abuse.cloudflare.com/phishing"
GSB_FORM = "https://safebrowsing.google.com/safebrowsing/report_phish/"
AEDA_FORM = "https://www.aeda.ae/"


ADDRESS = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
MAX_ADDRESS = 254


def valid_addresses(values: list | None) -> list[str]:
    """RDAP data is third-party input: keep only plain single addresses (no whitespace, comma, line break,
    display name or second address), in sorted order so the choice does not depend on the registry's order."""
    return sorted(v for v in values or [] if isinstance(v, str) and len(v) <= MAX_ADDRESS and ADDRESS.fullmatch(v))


@dataclass(frozen=True)
class Recipient:
    kind: str        # registrar | hosting | cloudflare | aeda | gsb
    recipient: str   # an email address, or a form URL
    name: str = ""

    @property
    def is_form(self) -> bool:
        return self.recipient.startswith("https://")


def ip_bootstrap(version: int) -> dict | None:
    key = f"kp:rdap:ipv{version}"
    cached = cache.get_json_sync(key)
    if cached is not None:
        return cached
    try:
        response = httpx.get(IP_BOOTSTRAP[version], timeout=10.0)
        response.raise_for_status()
    except httpx.HTTPError:
        return None
    data = response.json()
    cache.set_json_sync(key, data, BOOTSTRAP_TTL_S)
    return data


def ip_server(bootstrap: dict | None, ip: str) -> str:
    address = ipaddress.ip_address(ip)
    for prefixes, servers in (bootstrap or {}).get("services", []):
        if any(address in ipaddress.ip_network(prefix, strict=False) for prefix in prefixes) and servers:
            return servers[0].rstrip("/") + "/"
    return "https://rdap.org/"


def ip_abuse(ip: str) -> dict | None:
    """{"name", "abuse_emails"} of the network that holds this address, or None when RDAP fails."""
    key = f"kp:rdap:ip:{ip}"
    cached = cache.get_json_sync(key)
    if cached is not None:
        return cached
    version = ipaddress.ip_address(ip).version
    try:
        response = httpx.get(f"{ip_server(ip_bootstrap(version), ip)}ip/{ip}", timeout=10.0, follow_redirects=True,
                             headers={"Accept": "application/rdap+json"})
        response.raise_for_status()
    except httpx.HTTPError:
        return None
    data = response.json()
    parsed = rdap.parse(data)
    result = {"name": data.get("name") or parsed.get("registrar") or "", "abuse_emails": parsed.get("abuse_emails") or []}
    cache.set_json_sync(key, result, IP_TTL_S)
    return result


def behind_cloudflare(infra: dict) -> bool:
    if any(str(info.get("asn")) == CLOUDFLARE_ASN for info in (infra.get("asn") or {}).values()):
        return True
    return any(ns.rstrip(".").endswith(".ns.cloudflare.com") for ns in infra.get("ns") or [])


def recipients(domain: str, infra: dict, ip_lookup=ip_abuse) -> list[Recipient]:
    """One recipient per kind. `infra` is the evidence record's infrastructure block (DNS, ASN, RDAP)."""
    found: list[Recipient] = []
    registration = infra.get("rdap") or {}
    emails = valid_addresses(registration.get("abuse_emails"))
    if emails:  # no valid address means no registrar recipient, not an error
        found.append(Recipient("registrar", emails[0], registration.get("registrar") or ""))
    if behind_cloudflare(infra):
        found.append(Recipient("cloudflare", CLOUDFLARE_FORM, "Cloudflare"))
    else:
        for ip in (infra.get("a") or []) + (infra.get("aaaa") or []):
            network = ip_lookup(ip)
            hosting = valid_addresses(network["abuse_emails"]) if network else []
            if hosting:
                found.append(Recipient("hosting", hosting[0], network["name"]))
                break
    if domain.endswith(".ae"):
        found.append(Recipient("aeda", AEDA_FORM, "aeDA (TDRA)"))
    found.append(Recipient("gsb", GSB_FORM, "Google Safe Browsing"))
    return found
