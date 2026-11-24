"""Writes app/src/main/assets/brands.json from data/brands.yaml (the offline catalog Gatekeeper bundles).

    python3 gatekeeper/tools/brands_json.py        # from the repository root; needs pyyaml

Only what the phone needs: match tokens, official domains, display names and the safe_action services.
"""
import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def tokens(brand: dict) -> list[str]:
    raw = brand.get("match_tokens") or [brand["id"], *brand.get("names", [])]
    found = []
    for name in raw:
        token = re.sub(r"[\s\-_.&]", "", str(name).lower())
        if name.isascii() and len(token) >= 3 and token not in found:
            found.append(token)
    return found


def main() -> int:
    brands = yaml.safe_load((ROOT / "data/brands.yaml").read_text(encoding="utf-8"))
    out = []
    for b in brands:
        names = b.get("names", [])
        arabic = next((n for n in names if not n.isascii()), names[0] if names else b["id"])
        out.append({
            "id": b["id"],
            "name_en": next((n for n in names if n.isascii()), b["id"]),
            "name_ar": arabic,
            "tokens": tokens(b),
            "official_domains": [d.lower() for d in b.get("official_domains", [])],
            "services": [{"keywords": s.get("keywords", []), "label_en": s["label_en"], "label_ar": s["label_ar"],
                          "url": s["url"]} for s in b.get("services", [])],
        })
    target = ROOT / "gatekeeper/app/src/main/assets/brands.json"
    target.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {len(out)} brands to {target.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
