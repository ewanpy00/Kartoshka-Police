import ipaddress
import socket
from functools import lru_cache
from pathlib import Path

import httpx

from app.config import get_settings

RDAP_URL = "https://rdap.org"
RDAP_TIMEOUT = 5
MAX_DOMAIN_TRIES = 3
CLOUDFLARE_NS_SUFFIX = ".ns.cloudflare.com"

EMPTY = {
    "rdap_status": "failed",
    "registrar": None,
    "registered_at": None,
    "abuse_emails": [],
    "name_servers": [],
    "ip": None,
    "ip_network": None,
    "ip_owner": None,
    "ip_country": None,
    "ip_abuse_emails": [],
    "proxy": None,
}


def make_client() -> httpx.Client:
    return httpx.Client(timeout=RDAP_TIMEOUT, follow_redirects=True)


def resolve(host: str) -> str | None:
    try:
        return socket.getaddrinfo(host, None, family=socket.AF_INET)[0][4][0]
    except OSError:
        return None


@lru_cache
def cloudflare_networks(data_dir: str) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    lines = (Path(data_dir) / "cloudflare_ips.txt").read_text(encoding="utf-8").splitlines()
    return [ipaddress.ip_network(line) for line in lines if line and not line.startswith("#")]


def fetch(client: httpx.Client, url: str) -> dict | None:
    """The RDAP document, or None when the lookup failed for any reason."""
    try:
        response = client.get(url)
        response.raise_for_status()
        return response.json()
    except (httpx.HTTPError, ValueError):
        return None


def fetch_domain(client: httpx.Client, host: str) -> dict | None:
    """Ask for the host, then for its parents while the answer is 404, at most three times."""
    labels = host.split(".")
    for start in range(min(MAX_DOMAIN_TRIES, len(labels) - 1)):
        name = ".".join(labels[start:])
        try:
            response = client.get(f"{RDAP_URL}/domain/{name}")
            if response.status_code == 404:
                continue
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError):
            return None
    return None


def vcard_field(entity: dict, field: str) -> str | None:
    for item in (entity.get("vcardArray") or [None, []])[1]:
        if item[0] == field:
            return item[3]
    return None


def find_entities(document: dict, role: str) -> list[dict]:
    """Entities carrying the role, searched through nested entities as well."""
    found = []
    for entity in document.get("entities", []):
        if role in entity.get("roles", []):
            found.append(entity)
        found.extend(find_entities(entity, role))
    return found


def abuse_emails(document: dict) -> list[str]:
    emails = (vcard_field(entity, "email") for entity in find_entities(document, "abuse"))
    return sorted({email for email in emails if email})


def event_date(document: dict, action: str) -> str | None:
    return next((event["eventDate"] for event in document.get("events", []) if event.get("eventAction") == action), None)


def domain_fields(document: dict) -> dict:
    registrar = next(iter(find_entities(document, "registrar")), None)
    return {
        "registrar": vcard_field(registrar, "fn") if registrar else None,
        "registered_at": event_date(document, "registration"),
        "abuse_emails": abuse_emails(document),
        "name_servers": sorted({ns["ldhName"].lower() for ns in document.get("nameservers", []) if ns.get("ldhName")}),
    }


def ip_fields(document: dict) -> dict:
    owner = next(iter(find_entities(document, "registrant")), None)
    return {
        "ip_network": document.get("name"),
        "ip_owner": vcard_field(owner, "fn") if owner else None,
        "ip_country": document.get("country"),
        "ip_abuse_emails": abuse_emails(document),
    }


def lookup(client: httpx.Client, host: str, ip: str | None) -> dict:
    """The infrastructure block of the evidence payload. Any failed lookup leaves its fields null."""
    result = {**EMPTY, "ip": ip}
    domain_document = fetch_domain(client, host)
    ip_document = fetch(client, f"{RDAP_URL}/ip/{ip}") if ip else None
    if domain_document:
        result.update(domain_fields(domain_document))
    if ip_document:
        result.update(ip_fields(ip_document))
    if domain_document and (ip_document or not ip):
        result["rdap_status"] = "ok"
    behind_cloudflare = bool(ip) and any(
        ipaddress.ip_address(ip) in network for network in cloudflare_networks(get_settings().data_dir)
    )
    if behind_cloudflare or any(ns.endswith(CLOUDFLARE_NS_SUFFIX) for ns in result["name_servers"]):
        result["proxy"] = "cloudflare"
    return result
