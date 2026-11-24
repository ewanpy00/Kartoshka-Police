"""Signals read from a sandbox capture: what the page asks for, whose brand it shows, how it pushes the
visitor, where it sends data, whether it is parked, and whether a crawler sees a different page.

The page is written by the attacker. Nothing here executes or trusts it; it is matched as text.
"""
import re
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlsplit

import phonenumbers

from app.brands import arabic_name, display_name, find_brand_in_text, is_official
from app.normalize.url import extractor
from app.verdict.reasons import ASKS_AR, ASKS_EN, CATALOG, reason

# Field hints: matched against name, id, placeholder, label, autocomplete and aria-label of each input.
FIELD_PATTERNS = {
    "otp": re.compile(r"\botp\b|one[\s_-]?time|verif\w*[\s_-]?code|sms[\s_-]?code|passcode|auth[\s_-]?code|رمز\s*(التحقق|التفعيل|التأكيد)|الرمز\s*المرسل|كلمة\s*المرور\s*لمرة"),
    "card": re.compile(r"cc[\s_-]?(number|num)|card[\s_-]?(number|num|no)|cardnumber|\bpan\b|credit[\s_-]?card|debit[\s_-]?card|رقم\s*البطاقة|بطاقة\s*(الائتمان|الخصم)"),
    "cvv": re.compile(r"\bcvv2?\b|\bcvc2?\b|\bcsc\b|cc[\s_-]?csc|security[\s_-]?code|card[\s_-]?code|رمز\s*(الأمان|الامان)|الرقم\s*السري\s*للبطاقة"),
    "emirates_id": re.compile(r"emirates[\s_-]?id|\beid\b|id[\s_-]?number|national[\s_-]?id|رقم\s*الهوية|الهوية\s*الإماراتية|784[\s-]?\d{4}"),
    "iban": re.compile(r"\biban\b|آيبان|ايبان|رقم\s*الحساب"),
    "uaepass": re.compile(r"uae[\s_-]?pass|الهوية\s*الرقمية"),
}
AUTOCOMPLETE = {"one-time-code": "otp", "cc-number": "card", "cc-csc": "cvv", "cc-exp": "card", "cc-name": "card"}
UAEPASS_FIELDS = re.compile(r"user|email|mobile|phone|login|emirates|password|كلمة\s*المرور|الجوال|الهاتف|البريد")

URGENCY = re.compile(
    r"within\s+\d+\s*(hours?|hrs?|minutes?|days?)|immediately|final\s+(notice|warning)|last\s+(chance|warning)|"
    r"(account|card|service|licen[cs]e)\s+(will\s+be\s+)?(suspended|blocked|deactivated|cancelled)|avoid\s+(penalt|legal|additional)|"
    r"خلال\s*\d+\s*(ساعة|ساعات|دقيقة|أيام|يوم)|فور[اًا]|إنذار\s*نهائي|آخر\s*(فرصة|تنبيه)|سيتم\s*(إيقاف|تعليق|حظر|إلغاء)|غرامة\s*إضافية|تجنب\s*(الغرامة|المخالفة)",
    re.IGNORECASE,
)
PARKED = re.compile(
    r"domain\s+(is\s+)?(for\s+sale|parked)|buy\s+this\s+domain|this\s+domain\s+(may\s+be\s+)?for\s+sale|parked\s+(free|by)|"
    r"sedo|afternic|hugedomains|dan\.com|godaddy\s+parked|coming\s+soon|under\s+construction|هذا\s*النطاق\s*للبيع",
    re.IGNORECASE,
)
INJECTION = re.compile(
    r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions|you\s+are\s+(an?\s+)?(ai|language\s+model|assistant)|"
    r"(classify|mark|rate|label)\s+this\s+(page|site|website)\s+as\s+(safe|legitimate|benign)|system\s+prompt|"
    r"تجاهل\s*(جميع\s*)?التعليمات",
    re.IGNORECASE,
)
PHONE = re.compile(r"(?:\+|00)971[\s-]?\d{1,2}[\s-]?\d{3}[\s-]?\d{4}|\b05\d[\s-]?\d{3}[\s-]?\d{4}\b")
WHATSAPP_HOSTS = ("wa.me", "api.whatsapp.com", "chat.whatsapp.com", "whatsapp.com")
CREDENTIALS = ("otp", "card", "cvv", "uaepass")
PAYMENT_DATA = ("card", "cvv", "otp", "iban")

# Credential cap. The per-kind ASKS_* reasons stay in the explanation, but together they add at most
# CREDENTIAL_CAP points unless one of CAP_LIFTING_CODES is present: an impersonation signal (brand in the
# domain or subdomain, lookalike, visual match, brand shown on a domain that is not the brand's, a link to a
# confirmed campaign) or a reputation hit (police blocklist, officer confirmation, Safe Browsing, VirusTotal).
# Domain age, TLD risk and registrar reasons are deliberately not in this set.
CREDENTIAL_CAP = 25
CREDENTIAL_CODES = frozenset(code for code in CATALOG if code.startswith("ASKS_"))
CAP_LIFTING_CODES = frozenset({
    "BRAND_IN_DOMAIN", "BRAND_IN_SUBDOMAIN",
    "LOOKALIKE", "HOMOGLYPH", "MIXED_SCRIPTS", "PUNYCODE",
    "VISUAL_MATCH", "BRAND_MISMATCH",
    "CAMPAIGN_LINK",
    "BLOCKLISTED", "OFFICER_CONFIRMED", "GSB_HIT", "VT_HIT",
})


@dataclass
class Signals:
    reasons: list[dict] = field(default_factory=list)
    asks_for: list[str] = field(default_factory=list)
    brand: dict | None = None
    phones: list[str] = field(default_factory=list)
    payment_hosts: list[str] = field(default_factory=list)
    payment_endpoints: list[str] = field(default_factory=list)  # host plus path, for the campaign graph
    whatsapp: list[str] = field(default_factory=list)
    parked: bool = False
    cloaking: dict | None = None
    injection: bool = False
    facts_available: bool = True


def field_text(item: dict) -> str:
    return " ".join(str(item.get(key) or "") for key in ("name", "id", "placeholder", "label", "autocomplete")).lower()


def asks_for(forms: list[dict], brand: dict | None, page_text: str) -> list[str]:
    found: set[str] = set()
    fields = [item for form in forms for item in form.get("fields", []) if item.get("type") not in ("hidden", "submit", "button")]
    for item in fields:
        haystack = field_text(item)
        if item.get("type") == "password":
            found.add("password")
        if item.get("autocomplete") in AUTOCOMPLETE:
            found.add(AUTOCOMPLETE[item["autocomplete"]])
        for kind, pattern in FIELD_PATTERNS.items():
            if kind != "uaepass" and pattern.search(haystack):
                found.add(kind)
    short_code = any((item.get("maxlength") or 99) <= 8 and item.get("inputmode") in ("numeric", "tel", "") for item in fields)
    if short_code and FIELD_PATTERNS["otp"].search(page_text.lower()):
        found.add("otp")
    uaepass_page = (brand and brand["id"] == "uaepass") or FIELD_PATTERNS["uaepass"].search(page_text.lower())
    if uaepass_page and any(UAEPASS_FIELDS.search(field_text(item)) or item.get("type") == "password" for item in fields):
        found.add("uaepass")
    return sorted(found)


def registrable(host: str) -> str:
    return extractor()(host).top_domain_under_public_suffix or host


def words(text: str) -> set[str]:
    return {word for word in re.split(r"\W+", text.lower()) if len(word) > 2}


def cloaking(capture: dict) -> dict | None:
    """The crawler and the phone saw different pages: another site, or little shared text."""
    bot = capture.get("bot_visit") or {}
    if not bot or bot.get("error") or bot.get("navigation_blocked"):
        return None
    phone_host = urlsplit(capture.get("final_url") or "").hostname or ""
    bot_host = urlsplit(bot.get("final_url") or "").hostname or ""
    if phone_host and bot_host and registrable(phone_host) != registrable(bot_host):
        return {"kind": "different_site", "phone": phone_host, "bot": bot_host}
    phone_words, bot_words = words(capture.get("text") or ""), words(bot.get("text") or "")
    if len(phone_words) >= 20:
        shared = len(phone_words & bot_words) / len(phone_words | bot_words)
        if shared < 0.2:
            return {"kind": "different_content", "overlap": round(shared, 2), "bot_title": bot.get("title", "")[:120]}
    return None


def endpoint(url: str) -> str | None:
    parts = urlsplit(url)
    if not parts.hostname:
        return None
    return f"{parts.hostname.lower()}{parts.path or '/'}"[:300]


def e164(raw: str) -> str | None:
    """E.164 for a number as written on a page: a valid number through phonenumbers (default region AE),
    else the digits with the UAE national prefix mapped, so a malformed number is still comparable."""
    text = raw.strip()
    digits = re.sub(r"\D", "", text)
    if digits.startswith("00"):
        digits = digits[2:]
        text = "+" + digits
    if not text.startswith("+") and digits.startswith("971") and len(digits) >= 11:
        text = "+" + digits
    try:
        number = phonenumbers.parse(text if text.startswith("+") else digits, "AE")
        if phonenumbers.is_valid_number(number):
            return phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)
    except phonenumbers.NumberParseException:
        pass
    if digits.startswith("05"):
        digits = "971" + digits[1:]
    return f"+{digits}" if len(digits) >= 9 else None


def wa_digits(parts) -> str:
    """The number in a wa.me/<number> or api.whatsapp.com/send?phone=<number> link."""
    phone = "".join(parse_qs(parts.query).get("phone", []))
    return re.sub(r"\D", "", phone) or re.sub(r"\D", "", parts.path)


def whatsapp(capture: dict) -> list[str]:
    found = []
    for link in capture.get("links") or []:
        parts = urlsplit(link)
        if (parts.hostname or "") in WHATSAPP_HOSTS:
            digits = wa_digits(parts)
            number = e164("+" + digits) if digits else None
            if number and number not in found:
                found.append(number)
    return found[:10]


def contacts(capture: dict) -> list[str]:
    found = []
    for link in capture.get("links") or []:
        parts = urlsplit(link)
        if parts.scheme == "tel":
            found.append(re.sub(r"[^\d+]", "", parts.path))
        elif (parts.hostname or "") in WHATSAPP_HOSTS:
            digits = wa_digits(parts)
            if digits:
                found.append("+" + digits)
    for match in PHONE.findall(capture.get("text") or ""):
        found.append(re.sub(r"[^\d+]", "", match))
    normalized = []
    for number in found:
        value = e164(number)
        if value and value not in normalized:
            normalized.append(value)
    return normalized[:10]


def page_brand(capture: dict, host: str, claimed: dict | None, brands: list[dict]) -> dict | None:
    """A brand the page presents itself as: in the title or a logo, or in the text of a page that asks for data."""
    if claimed is not None:
        return claimed
    title = capture.get("title") or ""
    logos = " ".join(f"{image.get('alt', '')} {urlsplit(image.get('src', '')).path}" for image in capture.get("images") or [])
    hit = find_brand_in_text(f"{title} {logos}", brands)
    if hit is None and asks_for(capture.get("forms") or [], None, capture.get("text") or ""):
        hit = find_brand_in_text((capture.get("text") or "")[:3000], brands)
    if hit is None or is_official(host, hit.brand):
        return None
    return hit.brand


def analyse(capture: dict, host: str, claimed_brand: dict | None, brands: list[dict]) -> Signals:
    result = Signals()
    result.facts_available = capture.get("facts_available", True) is not False  # a missing key means true
    if not result.facts_available:
        result.reasons.append(reason("PAGE_FACTS_UNAVAILABLE"))
    text = capture.get("text") or ""
    forms = capture.get("forms") or []
    brand = page_brand(capture, host, claimed_brand, brands)
    result.brand = brand
    result.asks_for = asks_for(forms, brand, f"{capture.get('title') or ''} {text}")

    for kind, code in (("otp", "ASKS_OTP"), ("card", "ASKS_CARD"), ("cvv", "ASKS_CVV"), ("emirates_id", "ASKS_EMIRATES_ID"),
                       ("uaepass", "ASKS_UAEPASS"), ("password", "ASKS_PASSWORD"), ("iban", "ASKS_IBAN")):
        if kind in result.asks_for:
            result.reasons.append(reason(code))

    if brand is not None and claimed_brand is None:
        result.reasons.append(reason("BRAND_MISMATCH", brand=display_name(brand), brand_ar=arabic_name(brand)))

    if URGENCY.search(text) and (brand is not None or result.asks_for):
        result.reasons.append(reason("URGENCY"))

    result.phones = contacts(capture)
    if result.phones and brand is not None:
        result.reasons.append(reason("OFF_PLATFORM_CONTACT", contact=result.phones[0]))

    page_host = urlsplit(capture.get("final_url") or "").hostname or host
    page_domain = registrable(page_host)
    targets = [urlsplit(form.get("action") or "").hostname for form in forms if form.get("method") == "post"]
    targets += capture.get("post_hosts") or []
    result.payment_hosts = sorted({t for t in targets if t and registrable(t) != page_domain})
    endpoints = [endpoint(form.get("action") or "") for form in forms if form.get("method") == "post"]
    endpoints += [f"{h}/" for h in capture.get("post_hosts") or []]
    result.payment_endpoints = sorted({e for e in endpoints if e and registrable(e.split("/")[0]) != page_domain})[:10]
    result.whatsapp = whatsapp(capture)
    if result.payment_hosts and set(result.asks_for) & set(PAYMENT_DATA):
        result.reasons.append(reason("PAYMENT_ENDPOINT", host=result.payment_hosts[0]))

    no_inputs = not any(form.get("fields") for form in forms)
    if result.facts_available and no_inputs and (len(text.strip()) < 80 or PARKED.search(text[:2000])):
        result.parked = True
        result.reasons.append(reason("PARKED"))

    result.cloaking = cloaking(capture)
    if result.cloaking:
        result.reasons.append(reason("CLOAKING"))

    if INJECTION.search(text):
        result.injection = True
        result.reasons.append(reason("INJECTION_ATTEMPT"))
    return result


def cap_credentials(reasons: list[dict]) -> list[dict]:
    """Apply the credential cap to a merged reason list and return the list to score.

    The per-kind ASKS_* reasons stay in the list. When they add more than CREDENTIAL_CAP points and no
    CAP_LIFTING_CODES reason is present, their weights are scaled down (largest remainder, so the integers
    sum to exactly CREDENTIAL_CAP) and each scaled reason records `weight_full` and `capped`. The reasons'
    weights then still sum to the score, which `verdict.bands.total` relies on.
    """
    asks = [item for item in reasons if item["code"] in CREDENTIAL_CODES and (item["weight"] or 0) > 0]
    full = sum(item["weight"] for item in asks)
    if full <= CREDENTIAL_CAP or any(item["code"] in CAP_LIFTING_CODES for item in reasons):
        return reasons
    shares = [item["weight"] * CREDENTIAL_CAP / full for item in asks]
    scaled = [int(share) for share in shares]
    by_remainder = sorted(range(len(asks)), key=lambda i: shares[i] - scaled[i], reverse=True)
    for i in by_remainder[: CREDENTIAL_CAP - sum(scaled)]:
        scaled[i] += 1
    capped = {id(item): {**item, "weight": weight, "weight_full": item["weight"], "capped": True} for item, weight in zip(asks, scaled)}
    return [capped.get(id(item), item) for item in reasons]


# Impersonation signals only (no reputation hits): a page that hides its facts while one of these is present
# is scored as if it had shown its credential form.
IMPERSONATION_CODES = frozenset({
    "BRAND_IN_DOMAIN", "BRAND_IN_SUBDOMAIN", "LOOKALIKE", "HOMOGLYPH", "MIXED_SCRIPTS", "PUNYCODE",
    "VISUAL_MATCH", "BRAND_MISMATCH",
})


def hidden_facts_floor(reasons: list[dict], signals: "Signals", floor: int = 75) -> dict | None:
    """Hiding the page's facts must not be cheaper than showing its credential form."""
    if signals.facts_available or not any(item["code"] in IMPERSONATION_CODES for item in reasons):
        return None
    current = max(0, min(100, sum(r["weight"] or 0 for r in reasons)))
    brand = signals.brand
    return reason("BRAND_FACTS_HIDDEN", weight=max(0, floor - current),
                  brand=display_name(brand) if brand else "a brand", brand_ar=arabic_name(brand) if brand else "جهة")


def credential_floor(reasons: list[dict], signals: Signals, host: str, floor: int = 75) -> dict | None:
    """A page that is not the brand's and asks for a code, a card or UAE PASS credentials scores at least `floor`."""
    brand = signals.brand
    asked = [kind for kind in CREDENTIALS if kind in signals.asks_for]
    if brand is None or not asked or is_official(host, brand):
        return None
    current = max(0, min(100, sum(r["weight"] or 0 for r in reasons)))
    return reason(
        "BRAND_CREDENTIALS",
        weight=max(0, floor - current),
        brand=display_name(brand),
        brand_ar=arabic_name(brand),
        asks=", ".join(ASKS_EN[k] for k in asked),
        asks_ar="، ".join(ASKS_AR[k] for k in asked),
    )
