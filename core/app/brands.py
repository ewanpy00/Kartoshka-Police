from functools import lru_cache
from pathlib import Path

import yaml


@lru_cache
def load_brands(data_dir: str) -> list[dict]:
    return yaml.safe_load((Path(data_dir) / "brands.yaml").read_text(encoding="utf-8"))


def find_brand(brands: list[dict], brand_id: str | None) -> dict | None:
    return next((brand for brand in brands if brand["id"] == brand_id), None)


def safe_action(brand: dict, url: str) -> dict:
    """Pick the brand's service whose keywords appear in the URL, else its homepage."""
    lowered = url.lower()
    services = brand.get("services", [])
    for service in services:
        if any(keyword.lower() in lowered for keyword in service["keywords"]):
            return {"label_en": service["label_en"], "label_ar": service["label_ar"], "url": service["url"]}
    return {
        "label_en": f"Go to the official {brand['names'][0]} website",
        "label_ar": "الانتقال إلى الموقع الرسمي",
        "url": f"https://{brand['official_domains'][0]}",
    }
