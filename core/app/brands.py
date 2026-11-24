"""The UAE brand registry (data/brands.yaml) and the helpers every layer uses."""
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import phonenumbers
import yaml

SHORT_TOKEN = 5
WORD_SPLIT = re.compile(r"[^a-z]+")
# Work bounds: the host and the page text are written by the attacker.
MAX_LABEL = 100        # characters of one label looked at; a DNS label is at most 63
MAX_LABELS = 10        # labels of the domain part and of the subdomain part looked at
MAX_WORDS = 16         # hyphen-separated words of one label looked at
MAX_AFFIX = 32         # longest run of fillers and action words around a token (the DP is quadratic in it)
MAX_TEXT = 20_000      # characters of page text looked at
SEPARATORS = r"[\s\-_.&]"


@lru_cache
def load_brands(data_dir: str) -> list[dict]:
    return yaml.safe_load((Path(data_dir) / "brands.yaml").read_text(encoding="utf-8"))


@lru_cache
def load_global_brands(data_dir: str) -> list[dict]:
    path = Path(data_dir) / "global_brands.yaml"
    if not path.exists():
        return []
    brands = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    for brand in brands:
        brand["scope"] = "global"
    return brands


@lru_cache
def scoring_brands(data_dir: str) -> list[dict]:
    """UAE brands first (they win ties), then the global ones the scorer also recognises."""
    return [*load_brands(data_dir), *load_global_brands(data_dir)]


def find_brand(brands: list[dict], brand_id: str | None) -> dict | None:
    return next((brand for brand in brands if brand["id"] == brand_id), None)


def display_name(brand: dict) -> str:
    return brand["names"][0]


def arabic_name(brand: dict) -> str:
    return next((name for name in brand["names"] if not name.isascii()), display_name(brand))


def tokens(brand: dict) -> list[str]:
    """Match tokens: explicit match_tokens, else the ASCII names without spaces or hyphens."""
    raw = brand.get("match_tokens") or [brand["id"], *brand.get("names", [])]
    found = []
    for name in raw:
        if not name.isascii():
            continue
        token = re.sub(r"[\s\-_.&]", "", name.lower())
        if len(token) >= 3 and token not in found:
            found.append(token)
    return found


@lru_cache
def official_phones(data_dir: str | None = None) -> frozenset[str]:
    """Every brand's official phone numbers as E.164 strings, so an official number never links campaigns."""
    if data_dir is None:
        from app.config import get_settings

        data_dir = get_settings().data_dir
    found = set()
    for brand in scoring_brands(data_dir):
        for raw in brand.get("official_phones") or []:
            digits = re.sub(r"\D", "", str(raw))
            if not digits:
                continue  # a placeholder such as "<fill from the official website>"
            try:
                number = phonenumbers.parse(str(raw), None if str(raw).strip().startswith("+") else "AE")
                valid = phonenumbers.is_valid_number(number)
            except phonenumbers.NumberParseException:
                valid = False
            found.add(
                phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164) if valid
                else "+" + (digits if str(raw).strip().startswith("+") or digits.startswith("971") else "971" + digits.lstrip("0"))
            )
    return frozenset(found)


def official_labels(brand: dict) -> list[str]:
    """The registrable labels of the official domains: uaepass for uaepass.ae, dubaipolice for dubaipolice.gov.ae."""
    labels = []
    for domain in brand.get("official_domains", []):
        label = domain.split(".")[0]
        if label not in labels:
            labels.append(label)
    return labels


COUNTRY_SECOND_LEVELS = frozenset({"com", "co", "net", "org"})


def country_domain(host: str, label: str) -> bool:
    """host is <label>.<cc>, <label>.com.<cc> or <label>.co.<cc> (or a subdomain of one)."""
    parts = host.split(".")
    for index in range(len(parts) - 1):
        if parts[index] != label:
            continue
        rest = parts[index + 1 :]
        if len(rest) == 1 and len(rest[0]) == 2:
            return True
        if len(rest) == 2 and rest[0] in COUNTRY_SECOND_LEVELS and len(rest[1]) == 2:
            return True
    return False


def is_official(host: str, brand: dict) -> bool:
    if any(host == d or host.endswith("." + d) for d in brand.get("official_domains", [])):
        return True
    return bool(brand.get("country_domains")) and any(country_domain(host, label) for label in brand["country_domains"])


def is_any_official(host: str, brands: list[dict]) -> dict | None:
    return next((brand for brand in brands if is_official(host, brand)), None)


@dataclass
class BrandHit:
    brand: dict
    token: str
    where: str  # domain | subdomain | path


FILLERS = frozenset(
    """uae ae dubai abudhabi ad gov online my app web site official center centre now portal id home mobile
    secure services service info net the e m go get uaegov""".split()
)


def affix_ok(affix: str, action_words: frozenset[str], long_token: bool) -> bool:
    """What may sit next to a brand token inside one word: nothing, or a run of action words and
    fillers (uaepassverifylogin). A long token may also carry one stray letter (emiratespostt)."""
    if not affix:
        return True
    if len(affix) > MAX_AFFIX:
        return False
    allowed = FILLERS | action_words
    reachable = [True] + [False] * len(affix)
    for end in range(1, len(affix) + 1):
        reachable[end] = any(
            reachable[start] and (affix[start:end] in allowed or affix[start:end].rstrip("s") in allowed)
            for start in range(end)
        )
    return reachable[-1] or (long_token and len(affix) == 1)


def token_in_label(token: str, label: str, action_words: frozenset[str], whole_word: bool = False) -> bool:
    """A brand token counts when a word of the label, or the whole label without hyphens, is the token
    plus action words or fillers (uaepassverify, my-tammpay, uae-pass-login). mashreqia and salikhan
    do not match."""
    long_token = len(token) >= SHORT_TOKEN and not whole_word
    label = label[:MAX_LABEL]
    words = [w for w in WORD_SPLIT.split(label) if w][:MAX_WORDS]
    for word in [*words, label.replace("-", "")]:
        start = word.find(token)
        while start != -1:
            if affix_ok(word[:start], action_words, long_token) and affix_ok(word[start + len(token):], action_words, long_token):
                return True
            start = word.find(token, start + 1)
    return False


def find_brand_in_host(
    labels_domain: str, labels_sub: str, brands: list[dict], action_words: frozenset[str], host: str = ""
) -> BrandHit | None:
    """The first brand named in the registrable label, then in the subdomain. A brand on its own
    official domain is not an impersonation (global brands are not in the domains table)."""
    for where, text in (("domain", labels_domain), ("subdomain", labels_sub)):
        if not text:
            continue
        for brand in brands:
            if host and is_official(host, brand):
                continue
            for token in tokens(brand):
                whole = bool(brand.get("whole_word"))
                if any(token_in_label(token, label, action_words, whole) for label in text.split(".")[:MAX_LABELS]):
                    return BrandHit(brand, token, where)
    return None


@lru_cache(maxsize=512)
def name_pattern(raw: str) -> re.Pattern | None:
    """An ASCII brand name as a whole word: "UAE PASS" also matches "uae-pass" and "uaepass", "Tammer" does not match "TAMM"."""
    parts = [re.escape(part) for part in re.split(SEPARATORS + "+", raw.lower()) if part]
    if len("".join(parts)) < 3 or not parts:
        return None
    return re.compile(rf"(?<![^\W_]){f'{SEPARATORS}*'.join(parts)}(?![^\W_])")


def find_brand_in_text(text: str, brands: list[dict]) -> BrandHit | None:
    """Brand names in page text, title or a URL path. ASCII names match as whole words, whatever their length
    ("Tammer" is not TAMM). Arabic names have no case and take attached prefixes (بالهوية), so they match as substrings."""
    text = text[:MAX_TEXT]
    lowered = text.lower()
    for brand in brands:
        raw_names = brand.get("match_tokens") or [brand["id"], *brand.get("names", [])]
        for raw in raw_names:
            if not raw.isascii():
                continue
            pattern = name_pattern(raw)
            if pattern is not None and pattern.search(lowered):
                return BrandHit(brand, re.sub(r"[\s\-_.&]", "", raw.lower()), "text")
        for name in brand.get("names", []):
            if not name.isascii() and len(name) >= 3 and name in text:
                return BrandHit(brand, name, "text")
    return None


def safe_action(brand: dict, url: str, text: str = "") -> dict:
    """Pick the brand's service whose keywords appear in the URL (or pasted SMS), else its homepage."""
    lowered = f"{url} {text}".lower()
    for service in brand.get("services", []):
        if any(keyword.lower() in lowered for keyword in service["keywords"]):
            return {"label_en": service["label_en"], "label_ar": service["label_ar"], "url": service["url"]}
    return {
        "label_en": f"Go to the official {display_name(brand)} website",
        "label_ar": "الانتقال إلى الموقع الرسمي",
        "url": f"https://{brand['official_domains'][0]}",
    }
