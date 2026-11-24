"""Score bands: <30 allow, 30-70 warn (deep analysis runs), >70 block (deep analysis confirms)."""
WARN_FROM = 30
BLOCK_ABOVE = 70

SOURCE_ORDER = ["allowlist", "police_blocklist", "gsb", "virustotal", "feeds", "rdap", "ct", "campaign", "sandbox", "ai"]


def band(score: int) -> str:
    if score > BLOCK_ABOVE:
        return "block"
    if score >= WARN_FROM:
        return "warn"
    return "allow"


def total(reasons: list[dict]) -> int:
    return max(0, min(100, sum(r["weight"] for r in reasons)))


def needs_deep(score: int) -> bool:
    return score >= WARN_FROM


def source(id: str, status: str, detail: str | None = None) -> dict:
    entry = {"id": id, "status": status}
    if detail:
        entry["detail"] = detail
    return entry


def ordered(sources: dict[str, dict]) -> list[dict]:
    return [sources.get(id) or source(id, "skipped") for id in SOURCE_ORDER]
