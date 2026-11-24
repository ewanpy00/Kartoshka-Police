"""Reason codes with their default weights and Arabic and English templates.

Every point in a score comes from one of these. Templates take named parameters; Arabic text is
written for residents first.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Template:
    weight: int
    source: str
    en: str
    ar: str


CATALOG: dict[str, Template] = {
    # Lists and officer decisions
    "ALLOWLISTED": Template(0, "kartoshka", "Official or allowlisted domain", "نطاق رسمي أو مدرج في قائمة النطاقات الموثوقة"),
    "BLOCKLISTED": Template(100, "kartoshka", "Domain is on the confirmed blocklist", "النطاق مدرج في قائمة الحظر المؤكدة"),
    "OFFICER_CONFIRMED": Template(100, "officer", "Confirmed as a scam by a police officer", "أكّد ضابط شرطة أن هذا الموقع احتيالي"),
    "OFFICER_CLEARED": Template(0, "officer", "Reviewed by a police officer: looks legitimate", "راجعه ضابط شرطة: يبدو موقعًا شرعيًا"),
    # Lexical
    "BRAND_IN_DOMAIN": Template(
        40, "kartoshka",
        "Domain uses '{token}' but is not an official {brand} domain",
        "النطاق يستخدم اسم '{token}' لكنه ليس نطاقًا رسميًا لـ{brand_ar}",
    ),
    "BRAND_IN_SUBDOMAIN": Template(
        35, "kartoshka",
        "Address puts '{token}' in front of an unrelated domain ({domain})",
        "العنوان يضع '{token}' أمام نطاق لا علاقة له بالجهة ({domain})",
    ),
    "BRAND_IN_PATH": Template(
        10, "kartoshka",
        "Link mentions {brand} on an unrelated site",
        "الرابط يذكر {brand_ar} على موقع لا علاقة له بها",
    ),
    "BRAND_ACTION": Template(
        15, "kartoshka",
        "A {brand} name is combined with a payment or login word",
        "اسم {brand_ar} مقرون بكلمة دفع أو تسجيل دخول",
    ),
    "LOOKALIKE": Template(
        35, "kartoshka",
        "Domain looks like {official} but differs by {distance} character(s)",
        "النطاق يشبه {official} لكنه يختلف بـ{distance} حرف",
    ),
    "HOMOGLYPH": Template(
        35, "kartoshka",
        "Domain uses look-alike characters to imitate '{target}'",
        "النطاق يستخدم أحرفًا متشابهة لتقليد '{target}'",
    ),
    "MIXED_SCRIPTS": Template(
        20, "kartoshka", "Domain mixes alphabets ({scripts})", "النطاق يخلط بين أبجديات مختلفة ({scripts})"
    ),
    "PUNYCODE": Template(
        10, "kartoshka", "Domain is written in encoded international characters", "النطاق مكتوب بأحرف دولية مشفّرة"
    ),
    "ACTION_WORDS": Template(
        10, "kartoshka", "Address contains pressure words: {words}", "العنوان يحتوي على كلمات ضغط: {words}"
    ),
    "RISKY_TLD": Template(
        15, "kartoshka", "The .{tld} ending is common on scam sites", "النهاية ‎.{tld}‎ شائعة في مواقع الاحتيال"
    ),
    "GOV_LOOKALIKE": Template(
        20, "kartoshka",
        "Domain imitates a government or police address but is not under .gov.ae",
        "النطاق يقلّد عنوانًا حكوميًا أو شرطيًا لكنه ليس تحت ‎.gov.ae‎",
    ),
    "IP_HOST": Template(
        25, "kartoshka", "Link points to a bare IP address instead of a name", "الرابط يشير إلى عنوان IP مباشر بدلًا من اسم"
    ),
    "USERINFO": Template(
        15, "kartoshka", "Link hides its real destination after an @ sign", "الرابط يخفي وجهته الحقيقية بعد علامة @"
    ),
    "SHORTENER": Template(
        10, "kartoshka", "Link uses a URL shortener that could not be expanded", "الرابط يستخدم خدمة تقصير يتعذر فتحها"
    ),
    "REDIRECT_CHAIN": Template(
        5, "kartoshka", "Link redirects {hops} times before the final page", "الرابط يعيد التوجيه {hops} مرات قبل الصفحة النهائية"
    ),
    "FREE_HOSTING": Template(
        20, "kartoshka", "Page is on a free hosting service ({suffix})", "الصفحة على خدمة استضافة مجانية ({suffix})"
    ),
    "LONG_HOST": Template(5, "kartoshka", "Unusually long address", "عنوان طويل بشكل غير معتاد"),
    "MANY_SUBDOMAINS": Template(10, "kartoshka", "Address has many nested subdomains", "العنوان يحتوي على نطاقات فرعية متداخلة كثيرة"),
    "MANY_HYPHENS": Template(5, "kartoshka", "Domain is built from many hyphenated words", "النطاق مكوّن من كلمات كثيرة مفصولة بشرطات"),
    "RANDOM_NAME": Template(10, "kartoshka", "Domain name looks randomly generated", "اسم النطاق يبدو مولّدًا عشوائيًا"),
    "NON_STANDARD_PORT": Template(10, "kartoshka", "Link uses an unusual port ({port})", "الرابط يستخدم منفذًا غير معتاد ({port})"),
    "NO_HTTPS": Template(5, "kartoshka", "Connection is not encrypted (http)", "الاتصال غير مشفّر (http)"),
    # Domain and infrastructure
    "DOMAIN_AGE": Template(25, "rdap", "Registered {age}", "تم تسجيله {age_ar}"),
    "FRESH_CERT": Template(10, "ct", "First TLS certificate issued {age}", "صدرت أول شهادة أمان {age_ar}"),
    "CAMPAIGN_LINK": Template(
        30, "campaign",
        "Shares {kind} {value} with a known scam campaign ({campaign})",
        "يشترك في {kind_ar} {value} مع حملة احتيال معروفة ({campaign})",
    ),
    # Lookups
    "GSB_HIT": Template(60, "gsb", "Google Safe Browsing lists this link as {threat}", "يصنّف Google Safe Browsing هذا الرابط: {threat}"),
    "VT_HIT": Template(
        40, "virustotal", "{positives} of {total} security engines flag this link", "{positives} من أصل {total} محرك أمان تصنّف هذا الرابط خطرًا"
    ),
    "FEED_HIT": Template(50, "feeds", "Listed in the {feed} phishing feed", "مدرج في قائمة التصيّد {feed}"),
    "URL_MODEL": Template(
        25, "model", "URL model rates this link {pct}% likely phishing", "نموذج الروابط يقدّر احتمال التصيّد بنسبة {pct}٪"
    ),
    # Deep analysis
    "ASKS_OTP": Template(35, "sandbox", "Page asks for a one-time code (OTP)", "الصفحة تطلب رمز التحقق لمرة واحدة (OTP)"),
    "ASKS_CARD": Template(35, "sandbox", "Page asks for a card number", "الصفحة تطلب رقم البطاقة"),
    "ASKS_CVV": Template(30, "sandbox", "Page asks for the card security code (CVV)", "الصفحة تطلب رمز أمان البطاقة (CVV)"),
    "ASKS_EMIRATES_ID": Template(25, "sandbox", "Page asks for your Emirates ID number", "الصفحة تطلب رقم الهوية الإماراتية"),
    "ASKS_UAEPASS": Template(35, "sandbox", "Page asks for UAE PASS credentials", "الصفحة تطلب بيانات دخول الهوية الرقمية"),
    "ASKS_PASSWORD": Template(15, "sandbox", "Page asks for a password", "الصفحة تطلب كلمة مرور"),
    "ASKS_IBAN": Template(20, "sandbox", "Page asks for a bank account (IBAN)", "الصفحة تطلب رقم الحساب البنكي (IBAN)"),
    "BRAND_MISMATCH": Template(
        30, "sandbox", "Page shows {brand} branding on a domain that is not {brand}'s", "الصفحة تعرض علامة {brand_ar} على نطاق لا يتبع لها"
    ),
    "VISUAL_MATCH": Template(
        35, "sandbox", "Page looks {pct}% like the official {brand} page", "الصفحة تشبه صفحة {brand_ar} الرسمية بنسبة {pct}٪"
    ),
    "KIT_MATCH": Template(
        40, "sandbox", "Page structure matches a known scam kit ({campaign})", "بنية الصفحة تطابق أداة احتيال معروفة ({campaign})"
    ),
    "KIT_SIMILAR": Template(
        25, "sandbox", "Page structure is {pct}% similar to a known scam kit", "بنية الصفحة مشابهة بنسبة {pct}٪ لأداة احتيال معروفة"
    ),
    "FAVICON_MATCH": Template(20, "sandbox", "Page icon matches a known scam site", "أيقونة الصفحة تطابق موقع احتيال معروف"),
    "CLOAKING": Template(
        20, "sandbox", "Page shows different content to a phone than to a bot", "الصفحة تعرض محتوى للهاتف يختلف عمّا تعرضه للروبوت"
    ),
    "PARKED": Template(5, "sandbox", "Page is parked or empty; kept on the watchlist", "الصفحة متوقفة أو فارغة؛ وُضعت تحت المراقبة"),
    "UNREACHABLE": Template(0, "sandbox", "Page could not be loaded; kept on the watchlist", "تعذر تحميل الصفحة؛ وُضعت تحت المراقبة"),
    "PAYMENT_ENDPOINT": Template(10, "sandbox", "Page sends payment data to {host}", "الصفحة ترسل بيانات الدفع إلى {host}"),
    "OFF_PLATFORM_CONTACT": Template(
        10, "sandbox", "Page pushes you to WhatsApp or a phone number ({contact})", "الصفحة تدفعك للتواصل عبر واتساب أو رقم هاتف ({contact})"
    ),
    "URGENCY": Template(10, "sandbox", "Page pressures you with deadlines or threats", "الصفحة تضغط عليك بمهل أو تهديدات"),
    "INJECTION_ATTEMPT": Template(
        15, "ai", "Page contains text that tries to instruct an AI to call it safe", "الصفحة تحتوي على نص يحاول توجيه الذكاء الاصطناعي لتصنيفها آمنة"
    ),
    "AI_ASSESSMENT": Template(0, "ai", "AI review: {text_en}", "مراجعة الذكاء الاصطناعي: {text_ar}"),
    # SMS
    "SMS_SCAM_TEXT": Template(
        20, "ai", "The message reads like a {category} scam", "الرسالة تشبه احتيال {category_ar}"
    ),
}


class _Defaults(dict):
    def __missing__(self, key: str) -> str:
        return ""


def reason(code: str, weight: int | None = None, **params) -> dict:
    template = CATALOG[code]
    values = _Defaults(params)
    return {
        "code": code,
        "weight": template.weight if weight is None else weight,
        "source": template.source,
        "en": template.en.format_map(values),
        "ar": template.ar.format_map(values),
    }


def ago_en(hours: float) -> str:
    if hours < 1:
        return "less than an hour ago"
    if hours < 48:
        return f"{int(hours)} h ago"
    return f"{int(hours // 24)} days ago"


def ago_ar(hours: float) -> str:
    if hours < 1:
        return "قبل أقل من ساعة"
    if hours < 48:
        return f"قبل {int(hours)} ساعة"
    return f"قبل {int(hours // 24)} يومًا"
