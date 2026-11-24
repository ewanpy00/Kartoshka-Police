import re

CLOUDFLARE_ABUSE = "https://abuse.cloudflare.com/"
ADDRESS = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}")
MAX_ADDRESS = 254


def valid_addresses(values: list | None) -> list[str]:
    """RDAP data is third-party input: keep only plain single addresses."""
    return sorted(v for v in values or [] if isinstance(v, str) and len(v) <= MAX_ADDRESS and ADDRESS.fullmatch(v))


def recipients(infrastructure: dict) -> list[tuple[str, str]]:
    """(kind, recipient) pairs from already fetched RDAP data. Makes no network call."""
    found = []
    registrar = valid_addresses(infrastructure.get("abuse_emails"))
    if registrar:
        found.append(("registrar", registrar[0]))
    if infrastructure.get("proxy") == "cloudflare":
        found.append(("cloudflare", CLOUDFLARE_ABUSE))
    else:
        host = valid_addresses(infrastructure.get("ip_abuse_emails"))
        if host:
            found.append(("host", host[0]))
    return found
