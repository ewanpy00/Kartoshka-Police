"""Hunter's two filters before core (ARCHITECTURE.md section 2).

Name filter: look-alike names. A brand token of 5 letters or more matches anywhere in a label, with one
typo (two for 8+ letters), or after undoing homoglyphs (Cyrillic look-alikes, 0→o, 1→l, rn→m). A shorter
token (rta, icp, dib) matches a whole word only: `rta-fines.top` and `payrta.top` match, `portal.top`
does not. Official domains of the brand never match.

Infrastructure filter: names that say nothing about a brand. A risky TLD plus either an action word
(`pay-fine-online.top`) or a short random-looking label with digits (Smishing Triad style `dwu6.top`).

Both filters are cheap pre-screens. Core's fast score decides which candidates get a deep analysis.
"""
import re
import unicodedata
from dataclasses import dataclass

ACTION_WORDS = frozenset(
    """pay payment payments fine fines verify verification renew renewal refund update secure security login
    signin logon account unlock blocked suspend suspended confirm otp wallet bonus reward rewards claim prize gift
    delivery parcel customs track tracking toll unpaid due urgent alert invoice bill kyc reactivate recover
    redeliver redelivery release reschedule service services portal online card auth sso recovery connect
    restore validate validation appeal violation locked signup password billing traffic""".split()
)
FILLERS = frozenset("uae ae dubai abudhabi ad gov my app web site official center centre now id home mobile e m go get".split())
RISKY_TLDS = frozenset(
    """top xyz icu shop cyou sbs buzz click live online site vip cc win bond rest lol mom quest cfd fun space
    tk ml ga cf gq pw monster autos today life link work support help info cam bar lat ink mobi""".split()
)
SECOND_LEVELS = frozenset("co com net org gov ac edu".split())
HOMOGLYPHS = str.maketrans({
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x", "і": "i", "ј": "j", "ԁ": "d", "ѕ": "s",
    "ɑ": "a", "ı": "i", "ӏ": "l", "ο": "o", "α": "a", "ν": "v", "τ": "t", "0": "o", "1": "l", "3": "e", "5": "s", "4": "a",
})
WORD = re.compile(r"[a-z0-9]+")
RANDOM_LABEL = re.compile(r"^(?=[a-z0-9]{3,8}$)(?=.*\d)(?=.*[a-z])[a-z0-9]+$")


@dataclass(frozen=True)
class Candidate:
    host: str
    brand_id: str | None
    kind: str          # name | typo | homoglyph | infra
    detail: str


def brand_tokens(brand: dict) -> list[str]:
    raw = brand.get("match_tokens") or [brand["id"], *brand.get("names", [])]
    found = []
    for name in raw:
        if not name.isascii():
            continue
        token = re.sub(r"[\s\-_.&]", "", name.lower())
        if len(token) >= 3 and token not in found:
            found.append(token)
    return found


def prepare(brands: list[dict]) -> list[tuple[str, list[str], list[str]]]:
    """(brand id, tokens, official domains) for every brand, computed once."""
    return [(b["id"], brand_tokens(b), [d.lower() for d in b.get("official_domains", [])]) for b in brands]


def clean_host(raw: str) -> str | None:
    host = raw.strip().lower().removeprefix("*.").rstrip(".")
    if not host or "." not in host or len(host) > 253:
        return None
    if "xn--" in host:
        try:
            host = host.encode().decode("idna")
        except UnicodeError:
            pass
    return host


def name_labels(host: str) -> list[str]:
    """Labels without the public suffix (approximate: the TLD, plus `co.`/`com.` style second levels)."""
    labels = host.split(".")
    cut = 2 if len(labels) > 2 and labels[-2] in SECOND_LEVELS and len(labels[-1]) == 2 else 1
    return labels[:-cut]


def skeleton(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).translate(HOMOGLYPHS).replace("rn", "m").replace("vv", "w")
    return text


def distance(a: str, b: str, limit: int) -> int:
    """Damerau-Levenshtein (optimal string alignment), stopping early past `limit`."""
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    previous2, previous = None, list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            current[j] = min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (ca != cb))
            if previous2 is not None and i > 1 and j > 1 and ca == b[j - 2] and a[i - 2] == cb:
                current[j] = min(current[j], previous2[j - 2] + 1)
        if min(current) > limit:
            return limit + 1
        previous2, previous = previous, current
    return previous[-1]


def segments_ok(rest: str) -> bool:
    """`rest` is empty or splits into action words and fillers (dynamic programming)."""
    words = ACTION_WORDS | FILLERS
    ok = [True] + [False] * len(rest)
    for end in range(1, len(rest) + 1):
        ok[end] = any(ok[start] and rest[start:end] in words for start in range(max(0, end - 12), end))
    return ok[-1]


def whole_word(token: str, word: str) -> bool:
    if word == token:
        return True
    if word.startswith(token) and segments_ok(word[len(token):]):
        return True
    return word.endswith(token) and segments_ok(word[: -len(token)])


def official(host: str, domains: list[str]) -> bool:
    return any(host == d or host.endswith("." + d) for d in domains)


def name_match(host: str, prepared: list[tuple[str, list[str], list[str]]]) -> Candidate | None:
    labels = name_labels(host)
    if not labels:
        return None
    words = [w for label in labels for w in re.findall(r"[^\W_]+", label)]
    squashed = ["".join(re.findall(r"[^\W_]+", label)) for label in labels]
    ghosts = [skeleton(s) for s in squashed]
    for brand_id, tokens, domains in prepared:
        if official(host, domains):
            continue
        for token in tokens:
            if len(token) >= 5:
                if any(token in s for s in squashed):
                    return Candidate(host, brand_id, "name", token)
                if any(token in g for g in ghosts):
                    return Candidate(host, brand_id, "homoglyph", token)
                limit = 2 if len(token) >= 8 else 1
                for word in words + squashed:
                    if len(word) >= 5 and abs(len(word) - len(token)) <= 1 and distance(word, token, limit) <= limit:
                        return Candidate(host, brand_id, "typo", f"{token}~{word}")
            elif any(whole_word(token, w) for w in words):
                return Candidate(host, brand_id, "name", token)
            elif any(whole_word(token, skeleton(w)) for w in words if not w.isascii() or any(c.isdigit() for c in w)):
                return Candidate(host, brand_id, "homoglyph", token)
    return None


def infra_match(host: str) -> Candidate | None:
    tld = host.rsplit(".", 1)[-1]
    if tld not in RISKY_TLDS:
        return None
    labels = name_labels(host)
    if not labels:
        return None
    words = {w for label in labels for w in WORD.findall(label)}
    actions = sorted(words & ACTION_WORDS)
    if len(actions) >= 2:
        return Candidate(host, None, "infra", f".{tld} + {'/'.join(actions[:3])}")
    if len(labels) == 1 and RANDOM_LABEL.match(labels[0]):
        return Candidate(host, None, "infra", f".{tld} + random label")
    return None


def screen(raw: str, prepared: list[tuple[str, list[str], list[str]]], infra: bool = True) -> Candidate | None:
    host = clean_host(raw)
    if host is None:
        return None
    return name_match(host, prepared) or (infra_match(host) if infra else None)
