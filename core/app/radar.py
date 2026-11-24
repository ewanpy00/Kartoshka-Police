"""Scam radar (ARCHITECTURE.md 3.1): what is active now, grouped by brand. Aggregates only, no personal data.

Counts include officer-confirmed sites and high-score suspected ones, labelled separately. Domain names
appear only when confirmed, defanged and never as links.
"""
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.brands import arabic_name, display_name, load_brands, safe_action
from app.defang import defang
from app.models import Check, Domain

WINDOW = timedelta(days=7)
SUSPECTED_FROM = 70
CATEGORY_TEXT = {  # the `category` values used in data/brands.yaml
    "police": ("fake police and fine-payment sites", "مواقع مزيفة للشرطة ودفع المخالفات"),
    "government": ("fake government service sites", "مواقع خدمات حكومية مزيفة"),
    "identity": ("fake identity and login sites", "مواقع مزيفة للهوية وتسجيل الدخول"),
    "delivery": ("fake parcel delivery sites", "مواقع مزيفة لتوصيل الطرود"),
    "bank": ("fake banking sites", "مواقع بنكية مزيفة"),
    "telecom": ("fake telecom sites", "مواقع اتصالات مزيفة"),
    "utility": ("fake utility bill sites", "مواقع مزيفة لفواتير الخدمات"),
}


def build(session: Session, data_dir: str, now: datetime | None = None) -> dict:
    now = now or datetime.now(UTC)
    since, today, yesterday = now - WINDOW, now - timedelta(hours=24), now - timedelta(hours=48)
    brands = load_brands(data_dir)
    by_id = {brand["id"]: brand for brand in brands}

    confirmed = session.execute(
        select(Domain.brand_id, Domain.domain, Domain.updated_at)
        .where(Domain.status == "confirmed", Domain.brand_id.in_(by_id), Domain.updated_at >= since)
        .order_by(Domain.updated_at.desc())
    ).all()
    suspected = session.execute(
        select(Check.brand_id, Check.domain, func.min(Check.created_at))
        .where(Check.brand_id.in_(by_id), Check.score >= SUSPECTED_FROM, Check.created_at >= since, Check.domain.is_not(None),
               Check.source != "batch")  # the judges' evaluation sets are not sightings
        .group_by(Check.brand_id, Check.domain)
    ).all()
    confirmed_domains = {domain for _, domain, _ in confirmed}

    rows: dict[str, dict] = {}
    for brand_id, domain, when in confirmed:
        row = rows.setdefault(brand_id, {"confirmed": [], "suspected": set(), "new_today": set(), "yesterday": set()})
        row["confirmed"].append(domain)
        bucket = "new_today" if when >= today else "yesterday" if when >= yesterday else None
        if bucket:
            row[bucket].add(domain)
    for brand_id, domain, first in suspected:
        if domain in confirmed_domains:
            continue
        row = rows.setdefault(brand_id, {"confirmed": [], "suspected": set(), "new_today": set(), "yesterday": set()})
        row["suspected"].add(domain)
        bucket = "new_today" if first >= today else "yesterday" if first >= yesterday else None
        if bucket:
            row[bucket].add(domain)

    out = []
    for brand_id, row in rows.items():
        brand = by_id[brand_id]
        out.append({
            "brand_id": brand_id, "brand": display_name(brand), "brand_ar": arabic_name(brand),
            "category": brand.get("category"),
            "confirmed": len(row["confirmed"]), "suspected": len(row["suspected"]),
            "active": len(row["confirmed"]) + len(row["suspected"]),
            "new_today": len(row["new_today"]), "yesterday": len(row["yesterday"]),
            "examples": [defang(domain) for domain in row["confirmed"][:3]],
            "tip_en": brand.get("tip_en"), "tip_ar": brand.get("tip_ar"),
            "safe_action": safe_action(brand, f"https://{brand['official_domains'][0]}/"),
        })
    out.sort(key=lambda item: (-item["active"], item["brand"]))

    categories: dict[str, dict] = {}
    for item in out:
        key = item["category"] or "other"
        group = categories.setdefault(key, {"category": key, "active": 0, "new_today": 0, "brands": []})
        group["active"] += item["active"]
        group["new_today"] += item["new_today"]
        group["brands"].append(item["brand"])
    headlines = []
    for group in sorted(categories.values(), key=lambda g: -g["active"]):
        en, ar = CATEGORY_TEXT.get(group["category"], ("scam sites", "مواقع احتيال"))
        imitating = ", ".join(group["brands"][:3])
        en = en.replace("sites", "site") if group["active"] == 1 else en
        headlines.append({**group, "en": f"{group['active']} {en} active, imitating {imitating}",
                          "ar": f"{group['active']} {ar} نشطة، تقلّد {imitating}"})
    return {
        "generated_at": now.isoformat(), "window_days": WINDOW.days,
        "totals": {"active": sum(i["active"] for i in out), "confirmed": sum(i["confirmed"] for i in out),
                   "suspected": sum(i["suspected"] for i in out), "new_today": sum(i["new_today"] for i in out),
                   "yesterday": sum(i["yesterday"] for i in out)},
        "headlines": headlines, "brands": out,
    }
