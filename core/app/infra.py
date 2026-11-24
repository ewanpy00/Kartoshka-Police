"""Where a site lives, for the case card. Display only: it never feeds a score or a link between sites."""
# Reverse proxies and CDNs that answer for the site: the address seen is theirs, not the host's.
PROXY_ASNS = {"13335", "209242", "54113", "20940", "16625", "21342", "60068"}  # Cloudflare, Fastly, Akamai, CDN77


def first_asn(infrastructure: dict) -> dict:
    """The AS record of the first address the evidence lists (`asn` maps address to {asn, prefix, country, name})."""
    known = infrastructure.get("asn") or {}
    for ip in [*(infrastructure.get("a") or []), *known]:
        if known.get(ip):
            return known[ip]
    return {}


def behind_proxy(infrastructure: dict) -> bool:
    if infrastructure.get("proxy"):
        return True
    if any(str(info.get("asn")) in PROXY_ASNS for info in (infrastructure.get("asn") or {}).values()):
        return True
    return any(ns.rstrip(".").endswith(".ns.cloudflare.com") for ns in infrastructure.get("ns") or [])


def location(infrastructure: dict) -> dict:
    """Behind a proxy the address seen is the proxy's, so the host's country and owner are unknown and not shown.

    Reads the deep job's `infra` block (`asn` per address, `rdap.registrar`, `ns`); the flat keys
    `ip_country`, `ip_owner`, `ip_network`, `registrar` and `proxy` take precedence when present.
    """
    infrastructure = infrastructure or {}
    proxied = behind_proxy(infrastructure)
    asn = first_asn(infrastructure)
    return {
        "hosted_in": None if proxied else infrastructure.get("ip_country") or asn.get("country") or None,
        "registered_through": infrastructure.get("registrar") or (infrastructure.get("rdap") or {}).get("registrar") or None,
        "network_owner": None if proxied else (infrastructure.get("ip_owner") or infrastructure.get("ip_network")
                                               or asn.get("name") or asn.get("prefix") or None),
        "behind_proxy": proxied,
    }
