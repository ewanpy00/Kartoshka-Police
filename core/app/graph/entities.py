from collections.abc import Callable

STRONG_KINDS = ("phone", "whatsapp", "payment")


def entities_of(payload: dict, is_official: Callable[[str, str], bool]) -> list[tuple[str, str]]:
    """The (kind, value) pairs a schema-1 evidence payload links to its domain, minus official contacts.

    Country is display-only and never an entity."""
    infrastructure = payload.get("infrastructure", {})
    scam = payload.get("scam", {})
    pairs = [("domain", payload["identity"]["domain"])]
    pairs += [("ip", infrastructure["ip"])] if infrastructure.get("ip") else []
    pairs += [("ns", name.lower()) for name in infrastructure.get("name_servers", [])]
    pairs += [("registrar", infrastructure["registrar"])] if infrastructure.get("registrar") else []
    pairs += [("phone", phone) for phone in scam.get("phones", [])]
    pairs += [("whatsapp", number) for number in scam.get("whatsapp", [])]
    pairs += [("payment", host) for host in scam.get("payment_hosts", [])]
    return list(dict.fromkeys(pair for pair in pairs if not is_official(*pair)))


def edge_strength(kind: str, payload: dict) -> str:
    """Phones, WhatsApp numbers and payment hosts are strong; an address is strong only when not proxied."""
    if kind in STRONG_KINDS:
        return "strong"
    if kind == "ip" and payload.get("infrastructure", {}).get("proxy") is None:
        return "strong"
    return "weak"
