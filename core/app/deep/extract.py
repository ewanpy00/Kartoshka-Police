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


def valid_forms(forms: list) -> list[dict]:
    """The forms whose action and inputs have the expected shape; anything else is skipped."""
    return [
        {"action": form["action"], "inputs": [field for field in form["inputs"] if is_field(field)]}
        for form in forms
        if isinstance(form, dict) and isinstance(form.get("action"), str) and isinstance(form.get("inputs"), list)
    ]


def is_field(field: object) -> bool:
    return isinstance(field, dict) and isinstance(field.get("type"), str) and isinstance(field.get("name"), str)


def credential_form(forms: list) -> bool:
    return any(
        CREDENTIAL_FIELD.search(field["type"]) or CREDENTIAL_FIELD.search(field["name"])
        for form in valid_forms(forms)
        for field in form["inputs"]
    )


def phones(text: str, links: list) -> list[str]:
    found = [phonenumbers.format_number(match.number, phonenumbers.PhoneNumberFormat.E164) for match in phonenumbers.PhoneNumberMatcher(text, REGION)]
    found += [e164(link.removeprefix("tel:")) for link in links if isinstance(link, str) and link.startswith("tel:")]
    return list(dict.fromkeys(number for number in found if number))


def split(url: str):
    try:
        return urlsplit(url)
    except ValueError:
        return urlsplit("")


def whatsapp(links: list) -> list[str]:
    found = []
    for link in (link for link in links if isinstance(link, str)):
        parts = split(link)
        if parts.hostname in WHATSAPP_HOSTS:
            digits = "".join(parse_qs(parts.query).get("phone", [])) or parts.path.strip("/")
            found.append(e164("+" + digits.lstrip("+")))
    return list(dict.fromkeys(number for number in found if number))


def payment_hosts(forms: list, page_host: str) -> list[str]:
    hosts = {split(form["action"]).hostname for form in valid_forms(forms)}
    return sorted(host for host in hosts if host and host != page_host)
