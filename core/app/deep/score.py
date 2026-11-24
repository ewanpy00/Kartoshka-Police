from datetime import UTC, datetime, timedelta

NEW_DOMAIN_DAYS = 30
MIN_MATCH_LENGTH = 4
BLOCK_AT = 70
WARN_AT = 30

REASONS = {
    "BRAND_LOOKALIKE_DOMAIN": (
        40,
        "sandbox",
        "The domain uses the name of {brand} but is not one of its official domains",
        "النطاق يستخدم اسم {brand} وليس من نطاقاته الرسمية",
    ),
    "CREDENTIAL_FORM": (
        30,
        "sandbox",
        "The page asks for a password, PIN, one-time code or card details",
        "الصفحة تطلب كلمة مرور أو رمزا سريا أو رمز تحقق أو بيانات بطاقة",
    ),
    "BRAND_IN_PAGE": (
        20,
        "sandbox",
        "The page names {brand} in its title or text",
        "الصفحة تذكر {brand} في عنوانها أو نصها",
    ),
    "PAGE_FACTS_UNAVAILABLE": (
        30,
        "sandbox",
        "The page prevented inspection of its forms and text",
        "الصفحة منعت فحص نماذجها ونصها",
    ),
    "NEW_DOMAIN": (
        15,
        "rdap",
        "The domain was registered less than 30 days ago",
        "تم تسجيل النطاق قبل أقل من 30 يوما",
    ),
}


def reason(code: str, brand: str | None = None) -> dict:
    weight, source, en, ar = REASONS[code]
    return {"code": code, "weight": weight, "source": source, "en": en.format(brand=brand), "ar": ar.format(brand=brand)}


def is_official(host: str, brand: dict) -> bool:
    return any(host == domain or host.endswith(f".{domain}") for domain in brand["official_domains"])


def squash(name: str) -> str:
    return name.lower().replace(" ", "").replace("-", "")


def names_in_domain(brand: dict) -> list[str]:
    return [squash(name) for name in brand["names"] if name.isascii() and len(squash(name)) >= MIN_MATCH_LENGTH]


def names_in_text(brand: dict) -> list[str]:
    return [name.lower() for name in brand["names"] if len(squash(name)) >= MIN_MATCH_LENGTH]


def lookalike_tokens(brand: dict) -> set[str]:
    """Tokens that count as the brand: its name, or its name joined directly to one of its keywords."""
    names = names_in_domain(brand)
    keywords = [keyword.lower() for keyword in brand.get("keywords", [])]
    return set(names) | {joined for name in names for keyword in keywords for joined in (name + keyword, keyword + name)}


def label_candidates(label: str) -> set[str]:
    """Every run of adjacent hyphen-separated tokens in the label, joined without separators."""
    tokens = label.split("-")
    return {"".join(tokens[start:end]) for start in range(len(tokens)) for end in range(start + 1, len(tokens) + 1)}


def lookalike(host: str, brand: dict) -> bool:
    candidates = set().union(*(label_candidates(label) for label in host.split(".")))
    return not is_official(host, brand) and not candidates.isdisjoint(lookalike_tokens(brand))


def mentioned(host: str, text: str, brand: dict) -> bool:
    return not is_official(host, brand) and any(name in text for name in names_in_text(brand))


def is_new(registered_at: str | None, now: datetime) -> bool:
    """An unparseable date counts as unknown; a date without a zone is read as UTC."""
    try:
        registered = datetime.fromisoformat(registered_at or "")
    except ValueError:
        return False
    return now - registered.replace(tzinfo=registered.tzinfo or UTC) < timedelta(days=NEW_DOMAIN_DAYS)


def score(
    host: str,
    page_text: str,
    registered_at: str | None,
    credential_form: bool,
    facts_unavailable: bool,
    brands: list[dict],
    now: datetime,
) -> dict:
    """Score a page. `page_text` is the title and visible text. A lookalike with a credential form is 70 or more."""
    lowered = page_text.lower()
    brand = next((b for b in brands if lookalike(host, b)), None) or next((b for b in brands if mentioned(host, lowered, b)), None)
    found = []
    if brand and lookalike(host, brand):
        found.append(reason("BRAND_LOOKALIKE_DOMAIN", brand["names"][0]))
    if credential_form:
        found.append(reason("CREDENTIAL_FORM"))
    if facts_unavailable:
        found.append(reason("PAGE_FACTS_UNAVAILABLE"))
    if brand and mentioned(host, lowered, brand):
        found.append(reason("BRAND_IN_PAGE", brand["names"][0]))
    if is_new(registered_at, now):
        found.append(reason("NEW_DOMAIN"))
    total = min(100, sum(item["weight"] for item in found))
    verdict = "block" if total >= BLOCK_AT else "warn" if total >= WARN_AT else "allow"
    return {"score": total, "verdict": verdict, "reasons": found, "brand": brand}
