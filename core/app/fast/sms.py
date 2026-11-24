"""Pasted SMS: pull out the links and read the text for the usual UAE scam stories.

Rules first (A4 baseline); the AI layer can add its own reading in slice 4. The text is the attacker's;
it only adds a reason, it never makes a link safe.
"""
import re

from app.deep.signals import URGENCY
from app.normalize.url import extractor

MAX_LINKS = 5
LINK = re.compile(r"(?:https?://)?(?:[a-z0-9؀-ۿ-]+\.)+[a-z؀-ۿ]{2,}(?::\d+)?(?:/[^\s<>\"'،]*)?", re.IGNORECASE)
CATEGORIES = {
    "fine": ("traffic fine", "المخالفات المرورية",
             r"\bfines?\b|violation|penalt|traffic|salik|\btoll|parking|darb|مخالف|غرام|مرور|سالك|مواقف|درب"),
    "delivery": ("parcel delivery", "توصيل الطرود",
                 r"parcel|package|deliver|shipment|customs|courier|tracking|address|شحن|طرد|توصيل|جمارك|عنوان"),
    "bank": ("bank account", "الحسابات البنكية",
             r"\baccount|\bcard\b|blocked|suspend|\botp\b|verify your|update your|حساب|بطاق|إيقاف|ايقاف|تحديث|تجميد"),
    "prize": ("prize", "الجوائز",
              r"\bwon\b|winner|prize|reward|points|gift|claim|cashback|ربحت|فزت|جائزة|نقاط|هدية|مكافأة"),
    "government": ("government service", "الخدمات الحكومية",
                   r"uae ?pass|emirates ?id|\bvisa\b|residen|\bicp\b|ministry|الهوية|الإقامة|الاقامة|التأشيرة|وزارة"),
}


def links(text: str) -> list[str]:
    found = []
    for match in LINK.findall(text):
        candidate = match.rstrip(".,;:!?)]}")
        host = re.sub(r"^https?://", "", candidate, flags=re.IGNORECASE).split("/")[0].split(":")[0]
        if not extractor()(host).suffix:
            continue
        url = candidate if re.match(r"https?://", candidate, re.IGNORECASE) else f"https://{candidate}"
        if url not in found:
            found.append(url)
    return found[:MAX_LINKS]


def classify(text: str) -> dict:
    lowered = text.lower()
    scores = {name: len(re.findall(pattern, lowered)) for name, (_, _, pattern) in CATEGORIES.items()}
    category = max(scores, key=scores.get) if any(scores.values()) else None
    return {
        "category": category,
        "category_en": CATEGORIES[category][0] if category else None,
        "category_ar": CATEGORIES[category][1] if category else None,
        "urgent": bool(URGENCY.search(text)),
        "links": links(text),
    }
