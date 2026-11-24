import ipaddress
import socket
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import httpx

from app.config import get_settings

RDAP_URL = "https://rdap.org"
RDAP_TIMEOUT = 5
MAX_DOMAIN_TRIES = 3
FIELD_LIMIT = 500
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
    """The RDAP document, or None when the lookup failed or did not return a JSON object."""
    try:
        response = client.get(url)
        response.raise_for_status()
        document = response.json()
    except (httpx.HTTPError, ValueError, RecursionError):
        return None
    return document if isinstance(document, dict) else None


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
            document = response.json()
        except (httpx.HTTPError, ValueError, RecursionError):
            return None
        return document if isinstance(document, dict) else None
    return None


def text(value: object) -> str | None:
    """Registry data is untrusted: only strings are kept, and only up to a sane length."""
    return value[:FIELD_LIMIT] if isinstance(value, str) and value else None


def dicts(value: object) -> list[dict]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def vcard_field(entity: dict, field: str) -> str | None:
    vcard = entity.get("vcardArray")
    items = vcard[1] if isinstance(vcard, list) and len(vcard) > 1 and isinstance(vcard[1], list) else []
    for item in items:
        if isinstance(item, list) and len(item) > 3 and item[0] == field:
            return text(item[3])
    return None


def find_entities(document: dict, role: str) -> list[dict]:
    """Entities carrying the role, searched through nested entities as well."""
    found = []
    for entity in dicts(document.get("entities")):
        if role in (entity.get("roles") if isinstance(entity.get("roles"), list) else []):
            found.append(entity)
        found.extend(find_entities(entity, role))
    return found


def abuse_emails(document: dict) -> list[str]:
    emails = (vcard_field(entity, "email") for entity in find_entities(document, "abuse"))
    return sorted({email for email in emails if email})


def event_date(document: dict, action: str) -> str | None:
    """The date of the event when it is ISO 8601; an unparseable date is unknown."""
    for event in dicts(document.get("events")):
        if event.get("eventAction") == action:
            date = text(event.get("eventDate"))
            try:
                datetime.fromisoformat(date or "")
            except ValueError:
                return None
            return date
    return None


def domain_fields(document: dict) -> dict:
    registrar = next(iter(find_entities(document, "registrar")), None)
    servers = (text(ns.get("ldhName")) for ns in dicts(document.get("nameservers")))
    return {
        "registrar": vcard_field(registrar, "fn") if registrar else None,
        "registered_at": event_date(document, "registration"),
        "abuse_emails": abuse_emails(document),
        "name_servers": sorted({server.lower() for server in servers if server}),
    }


def ip_fields(document: dict) -> dict:
    owner = next(iter(find_entities(document, "registrant")), None)
    return {
        "ip_network": text(document.get("name")),
        "ip_owner": vcard_field(owner, "fn") if owner else None,
        "ip_country": text(document.get("country")),
        "ip_abuse_emails": abuse_emails(document),
    }


def parsed(extract_fields, document: dict | None) -> dict | None:
    """The extracted fields, or None when the document is missing or too deeply nested to read."""
    try:
        return extract_fields(document) if document else None
    except RecursionError:
        return None


def lookup(client: httpx.Client, host: str, ip: str | None) -> dict:
    """The infrastructure block of the evidence payload. Any failed lookup leaves its fields null."""
    result = {**EMPTY, "ip": ip}
    domain_data = parsed(domain_fields, fetch_domain(client, host))
    ip_data = parsed(ip_fields, fetch(client, f"{RDAP_URL}/ip/{ip}") if ip else None)
    result.update(domain_data or {})
    result.update(ip_data or {})
    if domain_data and (ip_data or not ip):
        result["rdap_status"] = "ok"
    behind_cloudflare = bool(ip) and any(
        ipaddress.ip_address(ip) in network for network in cloudflare_networks(get_settings().data_dir)
    )
    if behind_cloudflare or any(ns.endswith(CLOUDFLARE_NS_SUFFIX) for ns in result["name_servers"]):
        result["proxy"] = "cloudflare"
    return result
