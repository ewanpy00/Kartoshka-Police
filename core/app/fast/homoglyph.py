"""Look-alike characters and script mixing."""
import unicodedata

# Characters that render like ASCII letters. Cyrillic and Greek look-alikes, plus digit swaps used in ASCII.
CONFUSABLES = {
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x", "і": "i", "ј": "j", "ѕ": "s",
    "ԁ": "d", "ɡ": "g", "һ": "h", "ӏ": "l", "ո": "n", "ս": "u", "ԛ": "q", "ԝ": "w", "ҽ": "e", "ɑ": "a",
    "α": "a", "ο": "o", "ρ": "p", "ν": "v", "ι": "i", "κ": "k", "τ": "t", "υ": "u", "χ": "x", "ε": "e",
    "μ": "u", "η": "n", "ω": "w", "в": "b", "т": "t", "м": "m", "к": "k", "н": "h", "ь": "b", "г": "r",
    "ı": "i", "ł": "l", "ø": "o", "ß": "ss", "à": "a", "á": "a", "â": "a", "ä": "a", "å": "a", "ã": "a",
    "è": "e", "é": "e", "ê": "e", "ë": "e", "ì": "i", "í": "i", "î": "i", "ï": "i", "ò": "o", "ó": "o",
    "ô": "o", "ö": "o", "õ": "o", "ù": "u", "ú": "u", "û": "u", "ü": "u", "ñ": "n", "ç": "c", "ý": "y",
}
DIGIT_SWAPS = {"0": "o", "1": "l", "3": "e", "4": "a", "5": "s", "7": "t", "8": "b", "@": "a", "$": "s"}
SEQUENCE_SWAPS = (("rn", "m"), ("vv", "w"), ("cl", "d"))


def skeleton(text: str, digits: bool = True) -> str:
    """Map look-alike characters to the ASCII letter they imitate."""
    out = []
    for char in text.lower():
        char = CONFUSABLES.get(char, char)
        if digits:
            char = DIGIT_SWAPS.get(char, char)
        out.append(char)
    result = "".join(out)
    for pattern, replacement in SEQUENCE_SWAPS:
        result = result.replace(pattern, replacement)
    return result


def script_of(char: str) -> str | None:
    if char.isdigit() or char in "-._":
        return None
    try:
        name = unicodedata.name(char)
    except ValueError:
        return None
    for script in ("LATIN", "CYRILLIC", "GREEK", "ARABIC", "HEBREW", "ARMENIAN", "CJK", "HANGUL", "DEVANAGARI"):
        if name.startswith(script) or f" {script} " in name:
            return script.title()
    return "Other"


def scripts_in(label: str) -> list[str]:
    found = []
    for char in label:
        script = script_of(char)
        if script and script not in found:
            found.append(script)
    return found


def mixed_scripts(host_unicode: str) -> list[str] | None:
    """The scripts of the first label that mixes more than one, if any."""
    for label in host_unicode.split("."):
        scripts = scripts_in(label)
        if len(scripts) > 1:
            return scripts
    return None
