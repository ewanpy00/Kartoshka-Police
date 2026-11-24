import re
from urllib.parse import parse_qs, urlsplit

import phonenumbers

REGION = "AE"
CREDENTIAL_FIELD = re.compile(r"(?<![a-z])(otp|pin|password|cvv|card)", re.IGNORECASE)
WHATSAPP_HOSTS = {"wa.me", "api.whatsapp.com"}


def e164(raw: str) -> str | None:
    try:
        number = phonenumbers.parse(raw, REGION)
    except phonenumbers.NumberParseException:
        return None
    return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164) if phonenumbers.is_valid_number(number) else None


def credential_form(forms: list[dict]) -> bool:
    return any(
        CREDENTIAL_FIELD.search(field["type"]) or CREDENTIAL_FIELD.search(field["name"])
        for form in forms
        for field in form["inputs"]
    )


def phones(text: str, links: list[str]) -> list[str]:
    found = [phonenumbers.format_number(match.number, phonenumbers.PhoneNumberFormat.E164) for match in phonenumbers.PhoneNumberMatcher(text, REGION)]
    found += [e164(link.removeprefix("tel:")) for link in links if link.startswith("tel:")]
    return list(dict.fromkeys(number for number in found if number))


def whatsapp(links: list[str]) -> list[str]:
    found = []
    for link in links:
        parts = urlsplit(link)
        if parts.hostname in WHATSAPP_HOSTS:
            digits = "".join(parse_qs(parts.query).get("phone", [])) or parts.path.strip("/")
            found.append(e164("+" + digits.lstrip("+")))
    return list(dict.fromkeys(number for number in found if number))


def payment_hosts(forms: list[dict], page_host: str) -> list[str]:
    hosts = {urlsplit(form["action"]).hostname for form in forms}
    return sorted(host for host in hosts if host and host != page_host)
