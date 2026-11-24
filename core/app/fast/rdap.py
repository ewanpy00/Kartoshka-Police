"""Domain registration data over RDAP (no key). Cached in redis; the fast path waits only inside its budget."""
import logging
from datetime import UTC, datetime

import httpx

from app import cache

log = logging.getLogger("core.rdap")

RDAP_URL = "https://rdap.org/domain/{domain}"
BOOTSTRAP_URL = "https://data.iana.org/rdap/dns.json"
BOOTSTRAP_KEY = "kp:rdap:bootstrap"
FOUND_TTL = 24 * 3600
MISSING_TTL = 6 * 3600


def server_for(bootstrap: dict | None, domain: str) -> str:
    """The registry's own RDAP URL from the IANA bootstrap, else the rdap.org redirector."""
    tld = domain.rsplit(".", 1)[-1].lower()
    for tlds, urls in (bootstrap or {}).get("services", []):
        if tld in tlds and urls:
            base = next((u for u in urls if u.startswith("https://")), urls[0])
            return base.rstrip("/") + f"/domain/{domain}"
    return RDAP_URL.format(domain=domain)


async def bootstrap_async() -> dict | None:
    cached = await cache.get_json(BOOTSTRAP_KEY)
    if cached is not None:
        return cached
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(BOOTSTRAP_URL)
        response.raise_for_status()
        data = {"services": response.json()["services"]}
    except (httpx.HTTPError, ValueError, KeyError):
        return None
    await cache.set_json(BOOTSTRAP_KEY, data, 24 * 3600)
    return data


def bootstrap_sync() -> dict | None:
    cached = cache.get_json_sync(BOOTSTRAP_KEY)
    if cached is not None:
        return cached
    try:
        response = httpx.get(BOOTSTRAP_URL, timeout=10)
        response.raise_for_status()
        data = {"services": response.json()["services"]}
    except (httpx.HTTPError, ValueError, KeyError):
        return None
    cache.set_json_sync(BOOTSTRAP_KEY, data, 24 * 3600)
    return data


def parse(data: dict) -> dict:
    registered = None
    for event in data.get("events", []):
        if event.get("eventAction") == "registration" and event.get("eventDate"):
            registered = event["eventDate"]
    registrar, abuse = None, []

    def walk(entities: list[dict]) -> None:
        nonlocal registrar
        for entity in entities:
            roles = entity.get("roles", [])
            vcard = entity.get("vcardArray", [None, []])[1] if entity.get("vcardArray") else []
            name = next((item[3] for item in vcard if item[0] == "fn"), None)
            emails = [item[3] for item in vcard if item[0] == "email"]
            if "registrar" in roles and name:
                registrar = name
            if "abuse" in roles:
                abuse.extend(emails)
            walk(entity.get("entities", []))

    walk(data.get("entities", []))
    nameservers = [ns.get("ldhName", "").lower() for ns in data.get("nameservers", []) if ns.get("ldhName")]
    return {
        "found": True,
        "registered": registered,
        "registrar": registrar,
        "abuse_emails": sorted(set(abuse)),
        "nameservers": nameservers,
        "status": data.get("status", []),
    }


def age_hours(info: dict | None) -> float | None:
    if not info or not info.get("registered"):
        return None
    try:
        when = datetime.fromisoformat(info["registered"].replace("Z", "+00:00"))
    except ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return max(0.0, (datetime.now(UTC) - when).total_seconds() / 3600)


async def lookup(domain: str, timeout_s: float = 8.0) -> dict:
    key = f"kp:rdap:{domain}"
    cached = await cache.get_json(key)
    if cached is not None:
        return cached
    url = server_for(await bootstrap_async(), domain)
    async with httpx.AsyncClient(timeout=timeout_s, follow_redirects=True, headers={"Accept": "application/rdap+json"}) as client:
        response = await client.get(url)
    if response.status_code == 404:
        info = {"found": False}
        await cache.set_json(key, info, MISSING_TTL)
        return info
    response.raise_for_status()
    info = parse(response.json())
    await cache.set_json(key, info, FOUND_TTL)
    return info


def lookup_sync(domain: str, timeout_s: float = 10.0) -> dict:
    key = f"kp:rdap:{domain}"
    cached = cache.get_json_sync(key)
    if cached is not None:
        return cached
    response = httpx.get(server_for(bootstrap_sync(), domain), timeout=timeout_s, follow_redirects=True,
                         headers={"Accept": "application/rdap+json"})
    if response.status_code == 404:
        info = {"found": False}
        cache.set_json_sync(key, info, MISSING_TTL)
        return info
    response.raise_for_status()
    info = parse(response.json())
    cache.set_json_sync(key, info, FOUND_TTL)
    return info
