"""Infrastructure of a domain for the evidence record and the campaign graph: DNS, ASN, CT history, RDAP.

Every lookup is optional: a failure leaves its field empty. No key is needed for any of them.
"""
import ipaddress
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import dns.exception
import dns.resolver
import httpx

from app import cache
from app.fast import rdap

log = logging.getLogger("core.infra")

CRTSH_URL = "https://crt.sh/"
DNS_LIFETIME_S = 3.0
# Big CDNs and clouds: thousands of unrelated sites share their addresses, so their IPs are not campaign links.
SHARED_ASNS = {
    "13335", "209242",          # Cloudflare
    "16509", "14618",           # Amazon
    "15169", "396982", "19527", # Google
    "8075",                     # Microsoft
    "54113",                    # Fastly
    "20940", "16625", "21342",  # Akamai
    "32934",                    # Meta
    "60068",                    # CDN77
    "13238",                    # Yandex
}


def resolve(name: str, rtype: str) -> list[str]:
    resolver = dns.resolver.Resolver()
    resolver.lifetime = DNS_LIFETIME_S
    try:
        answer = resolver.resolve(name, rtype)
    except (dns.exception.DNSException, OSError):
        return []
    values = []
    for record in answer:
        if rtype == "MX":
            values.append(str(record.exchange).rstrip(".").lower())
        elif rtype == "TXT":
            values.append(b"".join(record.strings).decode(errors="replace"))
        elif rtype in ("NS", "CNAME"):
            values.append(str(record.target).rstrip(".").lower())
        else:
            values.append(record.address)
    return sorted(set(values))


def asn(ip: str) -> dict | None:
    """Origin AS of an IPv4 address from Team Cymru's DNS service."""
    key = f"kp:asn:{ip}"
    cached = cache.get_json_sync(key)
    if cached is not None:
        return cached or None
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return None
    if address.version != 4 or not address.is_global:
        return None
    origin = resolve(".".join(reversed(ip.split("."))) + ".origin.asn.cymru.com", "TXT")
    info: dict = {}
    if origin:
        fields = [part.strip() for part in origin[0].split("|")]
        number = fields[0].split()[0] if fields and fields[0] else ""
        info = {"asn": number, "prefix": fields[1] if len(fields) > 1 else "", "country": fields[2] if len(fields) > 2 else ""}
        described = resolve(f"AS{number}.asn.cymru.com", "TXT") if number else []
        if described:
            info["name"] = described[0].split("|")[-1].strip()
    cache.set_json_sync(key, info, 7 * 24 * 3600 if info else 3600)
    return info or None


def crtsh(domain: str, timeout_s: float = 15.0) -> dict | None:
    """First certificate ever logged for the domain and its subdomains, from crt.sh."""
    key = f"kp:crtsh:{domain}"
    cached = cache.get_json_sync(key)
    if cached is not None:
        return cached or None
    try:
        response = httpx.get(CRTSH_URL, params={"q": f"%.{domain}", "output": "json"}, timeout=timeout_s)
        response.raise_for_status()
        entries = response.json()
    except (httpx.HTTPError, ValueError) as error:
        log.info("crt.sh failed for %s: %r", domain, error)
        return None
    dates = sorted(entry["not_before"] for entry in entries if entry.get("not_before"))
    info = {"first_seen": dates[0] + "Z" if dates else None, "certificates": len(entries)}
    cache.set_json_sync(key, info, 24 * 3600)
    return info


def hours_since_iso(value: str | None) -> float | None:
    if not value:
        return None
    try:
        when = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return max(0.0, (datetime.now(UTC) - when).total_seconds() / 3600)


def safe_rdap(domain: str) -> dict | None:
    try:
        return rdap.lookup_sync(domain)
    except Exception as error:
        log.info("rdap failed for %s: %r", domain, error)
        return None


def collect(host: str, domain: str) -> dict:
    with ThreadPoolExecutor(max_workers=6) as pool:
        a = pool.submit(resolve, host, "A")
        aaaa = pool.submit(resolve, host, "AAAA")
        ns = pool.submit(resolve, domain, "NS")
        mx = pool.submit(resolve, domain, "MX")
        ct = pool.submit(crtsh, domain)
        registration = pool.submit(safe_rdap, domain)
        result = {"a": a.result(), "aaaa": aaaa.result(), "ns": ns.result(), "mx": mx.result()}
        result["ct"] = ct.result()
        result["rdap"] = registration.result()
    result["asn"] = {ip: info for ip in result["a"][:4] if (info := asn(ip))}
    return result


def shared_ip(ip: str, infra: dict) -> bool:
    """On a CDN or big cloud. When any address of the host is, all of them count as shared: CDNs answer
    with a set of anycast addresses and a missed ASN lookup must not turn one of them into a link."""
    known = infra.get("asn") or {}
    if any(info.get("asn") in SHARED_ASNS for info in known.values()):
        return True
    info = known.get(ip) or asn(ip) or {}
    return info.get("asn") in SHARED_ASNS
