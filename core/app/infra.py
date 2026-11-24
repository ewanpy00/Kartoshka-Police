def location(infrastructure: dict) -> dict:
    """Where a site lives, for display only. Behind a proxy the address seen is the proxy's, so the host is unknown."""
    behind_proxy = bool(infrastructure.get("proxy"))
    return {
        "hosted_in": None if behind_proxy else infrastructure.get("ip_country"),
        "registered_through": infrastructure.get("registrar"),
        "network_owner": None if behind_proxy else infrastructure.get("ip_owner") or infrastructure.get("ip_network"),
        "behind_proxy": behind_proxy,
    }
