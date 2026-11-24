"""Deterministic URL and domain-name features (step 2 of the fast score). No network."""
import math
import re
from collections import Counter

from rapidfuzz.distance import Levenshtein

from app.brands import arabic_name, display_name, find_brand_in_host, find_brand_in_text, is_official, official_labels, tokens
from app.fast.homoglyph import mixed_scripts, skeleton
from app.normalize.url import NormalizedURL
from app.verdict.reasons import reason

ACTION_WORDS = frozenset(
    """pay payment payments fine fines verify verification renew renewal refund update secure security login
    signin logon account unlock blocked suspend suspended confirm otp wallet bonus reward rewards claim prize gift
    delivery parcel customs track tracking toll unpaid due urgent alert invoice bill kyc reactivate recover
    redeliver redelivery release reschedule service portal online card auth sso recovery airdrop giveaway connect
    restore validate validation appeal violation checkpoint locked signup password billing subscription""".split()
)
ARABIC_ACTION_WORDS = ("دفع", "مخالفة", "مخالفات", "تحديث", "تحقق", "استرداد", "تجديد", "حظر", "طرد", "سداد", "غرامة")
RISKY_TLDS = frozenset(
    """top xyz icu shop cyou sbs buzz click live online site vip cc win bond rest lol mom quest cfd fun space
    tk ml ga cf gq pw monster autos boats yachts today life link work support help info cam bar beauty hair
    skin makeup lat ink christmas mobi""".split()
)
FREE_HOSTING = frozenset(
    """github.io pages.dev web.app firebaseapp.com vercel.app netlify.app herokuapp.com glitch.me blogspot.com
    weebly.com wixsite.com 000webhostapp.com repl.co workers.dev onrender.com ngrok-free.app ngrok.io
    azurewebsites.net appspot.com r2.dev fly.dev surge.sh webflow.io framer.app square.site godaddysites.com
    mystrikingly.com carrd.co replit.app""".split()
)
FREE_HOSTING_HOSTS = frozenset({"sites.google.com", "docs.google.com", "forms.gle", "storage.googleapis.com"})
GOV_WORDS = ("gov", "police", "ministry", "government", "moi", "federal")
STANDARD_PORTS = (None, 80, 443)


def entropy(text: str) -> float:
    if not text:
        return 0.0
    counts = Counter(text)
    return -sum(c / len(text) * math.log2(c / len(text)) for c in counts.values())


def looks_random(label: str) -> bool:
    bare = label.replace("-", "")
    if not bare:
        return False
    digits = sum(ch.isdigit() for ch in bare)
    vowels = sum(ch in "aeiou" for ch in bare)
    if re.fullmatch(r"[a-z]{1,4}\d[a-z0-9]{0,6}", bare) and digits <= 3 and len(bare) <= 8:
        return True
    if digits >= 3 and digits / len(bare) > 0.25:
        return True
    if len(bare) >= 8 and vowels / len(bare) < 0.2:
        return True
    return len(bare) >= 14 and entropy(bare) > 3.7


def words_in(text: str) -> set[str]:
    return set(filter(None, re.split(r"[^a-z]+", text.lower())))


def action_words_in(text: str) -> list[str]:
    found = sorted(words_in(text) & ACTION_WORDS)
    found += [word for word in ARABIC_ACTION_WORDS if word in text]
    return found


def closest_official(label: str, brands: list[dict]) -> tuple[dict, str, int] | None:
    """The official domain whose label is within edit distance 1 (6-7 letters) or 2 (8+) of this one.

    Shorter official labels (tamm, dewa, eand) are skipped: one edit turns them into ordinary words.
    """
    squashed = label.replace("-", "")
    best = None
    for brand in brands:
        for domain in brand.get("official_domains", []):
            official = domain.split(".")[0]
            if len(official) < 6 or squashed == official:
                continue
            limit = 1 if len(official) < 8 else 2
            distance = Levenshtein.distance(squashed, official, score_cutoff=limit)
            if distance <= limit and (best is None or distance < best[2]):
                best = (brand, domain, distance)
    return best


def homoglyph_target(n: NormalizedURL, brands: list[dict]) -> tuple[dict, str] | None:
    """A brand token that appears only after mapping look-alike characters back to ASCII."""
    for label in n.host_unicode.split("."):
        plain = label.lower()
        mapped = skeleton(plain)
        if mapped == plain:
            continue
        for brand in brands:
            for token in tokens(brand) + official_labels(brand):
                if len(token) >= 4 and token in mapped.replace("-", "") and token not in plain.replace("-", ""):
                    return brand, token
    return None


def brand_params(brand: dict) -> dict:
    return {"brand": display_name(brand), "brand_ar": arabic_name(brand)}


def lexical(n: NormalizedURL, brands: list[dict]) -> tuple[list[dict], dict, dict | None]:
    """Reasons, a feature dict (also the URL model's input) and the impersonated brand, if any."""
    reasons: list[dict] = []
    features: dict = {}
    brand: dict | None = None
    label = n.domain_label
    host_actions = action_words_in(n.host_unicode)
    path_text = f"{n.path} {n.query}"
    path_actions = action_words_in(path_text)

    hit = None if n.is_ip else find_brand_in_host(label, n.subdomain, brands, ACTION_WORDS, n.host)
    features["brand_in_domain"] = int(bool(hit and hit.where == "domain"))
    features["brand_in_subdomain"] = int(bool(hit and hit.where == "subdomain"))
    if hit:
        brand = hit.brand
        if hit.where == "domain":
            reasons.append(reason("BRAND_IN_DOMAIN", token=hit.token, **brand_params(brand)))
        else:
            reasons.append(reason("BRAND_IN_SUBDOMAIN", token=hit.token, domain=n.domain, **brand_params(brand)))

    near = None if n.is_ip or hit else closest_official(label, brands)
    features["lookalike_distance"] = near[2] if near else 0
    if near:
        brand = brand or near[0]
        reasons.append(reason("LOOKALIKE", official=near[1], distance=near[2]))

    glyph = None if n.is_ip or hit or near else homoglyph_target(n, brands)
    features["homoglyph"] = int(bool(glyph))
    if glyph:
        brand = brand or glyph[0]
        reasons.append(reason("HOMOGLYPH", target=glyph[1]))

    scripts = mixed_scripts(n.host_unicode)
    features["mixed_scripts"] = int(bool(scripts))
    if scripts:
        reasons.append(reason("MIXED_SCRIPTS", scripts=" + ".join(scripts)))
    features["punycode"] = int("xn--" in n.host)
    if features["punycode"] and not scripts and not glyph:
        reasons.append(reason("PUNYCODE"))

    path_brand = None
    if not brand and not n.is_ip:
        found = find_brand_in_text(path_text, brands)
        if found and not is_official(n.host, found.brand):
            path_brand = found.brand
            reasons.append(reason("BRAND_IN_PATH", **brand_params(path_brand)))
    features["brand_in_path"] = int(bool(path_brand))

    actions = host_actions + [word for word in path_actions if word not in host_actions]
    features["action_words_host"] = len(host_actions)
    features["action_words_path"] = len(path_actions)
    if actions:
        reasons.append(reason("ACTION_WORDS", weight=10 if host_actions else 5, words=", ".join(actions[:4])))
    if (brand or path_brand) and (host_actions or path_actions):
        reasons.append(reason("BRAND_ACTION", **brand_params(brand or path_brand)))

    tld = n.tld.rsplit(".", 1)[-1] if n.tld else ""
    features["risky_tld"] = int(tld in RISKY_TLDS)
    if features["risky_tld"]:
        reasons.append(reason("RISKY_TLD", tld=tld))

    gov_like = not n.is_ip and not n.tld.endswith("gov.ae") and any(w in n.host for w in GOV_WORDS)
    features["gov_lookalike"] = int(gov_like)
    if gov_like and (brand or "uae" in n.host or "dubai" in n.host or "abudhabi" in n.host):
        reasons.append(reason("GOV_LOOKALIKE"))

    features["ip_host"] = int(n.is_ip)
    if n.is_ip:
        reasons.append(reason("IP_HOST"))
    features["userinfo"] = int(n.userinfo)
    if n.userinfo:
        reasons.append(reason("USERINFO"))

    suffix = n.tld if n.is_private_suffix else ""
    free = suffix in FREE_HOSTING or n.host in FREE_HOSTING_HOSTS
    features["free_hosting"] = int(free)
    if free:
        reasons.append(reason("FREE_HOSTING", suffix=suffix or n.host))

    hops = max(0, len(n.chain) - 1)
    features["redirect_hops"] = hops
    if hops >= 2:
        reasons.append(reason("REDIRECT_CHAIN", hops=hops))

    features["host_length"] = len(n.host)
    if len(n.host) > 45:
        reasons.append(reason("LONG_HOST"))
    depth = len(n.subdomain.split(".")) if n.subdomain else 0
    features["subdomain_depth"] = depth
    if depth >= 3:
        reasons.append(reason("MANY_SUBDOMAINS"))
    features["hyphens"] = label.count("-")
    if label.count("-") >= 3:
        reasons.append(reason("MANY_HYPHENS"))
    features["digits"] = sum(ch.isdigit() for ch in label)
    features["entropy"] = round(entropy(label.replace("-", "")), 3)
    features["random_name"] = int(not n.is_ip and not brand and looks_random(label))
    if features["random_name"]:
        reasons.append(reason("RANDOM_NAME"))
    features["non_standard_port"] = int(n.port not in STANDARD_PORTS)
    if features["non_standard_port"]:
        reasons.append(reason("NON_STANDARD_PORT", port=n.port))
    features["https"] = int(n.scheme == "https")
    if n.scheme == "http" and (brand or actions):
        reasons.append(reason("NO_HTTPS"))
    features["path_length"] = len(n.path)
    features["query_params"] = len(n.params)
    segments = [part for part in n.path.split("/") if part]
    features["path_depth"] = len(segments)
    features["path_php"] = int(any(part.endswith((".php", ".asp", ".aspx", ".cgi")) for part in segments))
    features["path_html"] = int(any(part.endswith((".html", ".htm")) for part in segments))
    features["host_dots"] = n.host.count(".")
    features["label_length"] = len(label)
    features["subdomain_length"] = len(n.subdomain)
    features["tld_length"] = len(tld)
    features["has_www"] = int(n.host.startswith("www."))
    features["brand_any"] = int(bool(brand or path_brand))
    features["query_length"] = len(n.query)
    return reasons, features, brand or path_brand
