"""A0 for the AI facts: how far an AI answer may move the deterministic score.

docs/app-plan.md decision 1: the score is the sum of reason weights. The AI adds one `AI_ASSESSMENT`
reason; its weight lifts a score that is already in the 30-70 band and never past 70, so the AI can
re-rank uncertain cases (the officer queue sorts by score) but cannot turn a warn into a block or an
allow into a warn. Outside the band the reason carries weight 0 and only explains. Hard floors
(`BRAND_CREDENTIALS`) come from the deterministic signals, never from the AI.
"""
from app.verdict.reasons import reason

BAND = (30, 70)
LIFT = {"high": 15, "medium": 5, "low": 0}
INJECTION_LIFT = 5


def lift(facts: dict) -> int:
    return LIFT.get(facts.get("scam_likelihood"), 0) + (INJECTION_LIFT if facts.get("injection_attempt") else 0)


def ai_reason(base_score: int, facts: dict) -> dict:
    low, high = BAND
    weight = max(0, min(lift(facts), high - base_score)) if low <= base_score <= high else 0
    text_en = " ".join(facts.get("reasons_en") or []) or f"likelihood of a scam: {facts.get('scam_likelihood')}"
    text_ar = " ".join(facts.get("reasons_ar") or []) or text_en
    return reason("AI_ASSESSMENT", weight=weight, text_en=text_en, text_ar=text_ar)


def source_status(facts: dict) -> tuple[str, str]:
    likelihood = facts.get("scam_likelihood")
    status = {"high": "hit", "low": "clean"}.get(likelihood, "unknown")
    detail = f"{likelihood} likelihood, {facts.get('scam_type')}"
    if facts.get("brand_claimed") not in (None, "none"):
        detail += f", presents itself as {facts.get('brand_other_name') or facts['brand_claimed']}"
    if facts.get("injection_attempt"):
        detail += ", tries to instruct an AI"
    return status, detail
