CLOUDFLARE_ABUSE = "https://abuse.cloudflare.com/"


def recipients(infrastructure: dict) -> list[tuple[str, str]]:
    """(kind, recipient) pairs from already fetched RDAP data. Makes no network call."""
    found = []
    registrar = sorted(infrastructure.get("abuse_emails") or [])
    if registrar:
        found.append(("registrar", registrar[0]))
    if infrastructure.get("proxy") == "cloudflare":
        found.append(("cloudflare", CLOUDFLARE_ABUSE))
    else:
        host = sorted(infrastructure.get("ip_abuse_emails") or [])
        if host:
            found.append(("host", host[0]))
    return found
