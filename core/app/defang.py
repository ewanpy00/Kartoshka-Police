"""Defanged display values: attacker domains and URLs are shown, never linked (tamm-pay[.]xyz)."""


def defang(value: str | None) -> str | None:
    if value is None:
        return None
    return value.replace("https://", "hxxps://").replace("http://", "hxxp://").replace(".", "[.]")


def domain_view(domain: str | None) -> dict:
    return {"domain": domain, "display": defang(domain)}
