"""The LLM behind A2 (page understanding) and A4 (SMS text): Claude through the official SDK.

`AI_PROVIDER=anthropic` with `ANTHROPIC_API_KEY` set turns it on; anything else leaves every AI source
`skipped` and the verdict comes from the deterministic score alone. A sovereign deployment would add a
local provider here (ARCHITECTURE.md, "Providers") behind the same `structured` call.

Every call asks for JSON that matches a schema (no tools, no browsing), runs with server-side refusal
fallback, and is cached in Redis by a hash of its input, so the same kit costs one call.
"""
import hashlib
import json
import logging
from functools import lru_cache

import anthropic

from app import cache
from app.config import get_settings

log = logging.getLogger(__name__)
CACHE_TTL_S = 7 * 24 * 3600
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AIUnavailable(Exception):
    """No answer: not configured, timed out, refused, or the output was unusable. Callers fall back."""


@lru_cache
def client() -> anthropic.Anthropic:
    settings = get_settings()
    return anthropic.Anthropic(api_key=settings.anthropic_api_key, timeout=settings.ai_timeout_s, max_retries=1)


def enabled() -> bool:
    return get_settings().ai_enabled


def cache_key(task: str, system: str, content: list[dict], schema: dict) -> str:
    material = json.dumps([get_settings().ai_model, system, content, schema], sort_keys=True, ensure_ascii=False)
    return f"kp:ai:{task}:{hashlib.sha256(material.encode()).hexdigest()}"


def structured(task: str, system: str, content: list[dict], schema: dict, max_tokens: int = 4000,
               effort: str = "low", timeout_s: float | None = None) -> dict:
    """One schema-shaped answer. Raises AIUnavailable instead of guessing."""
    settings = get_settings()
    if not settings.ai_enabled:
        raise AIUnavailable("AI layer not configured")
    key = cache_key(task, system, content, schema)
    cached = cache.get_json_sync(key)
    if cached is not None:
        return {**cached, "_cached": True}
    caller = client() if timeout_s is None else client().with_options(timeout=timeout_s)
    try:
        response = caller.beta.messages.create(
            model=settings.ai_model,
            max_tokens=max_tokens,
            betas=[FALLBACK_BETA],
            fallbacks="default",
            system=system,
            messages=[{"role": "user", "content": content}],
            output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
        )
    except anthropic.APIError as error:
        log.warning("AI %s failed: %s", task, type(error).__name__)
        raise AIUnavailable(f"call failed: {type(error).__name__}") from None
    if response.stop_reason == "refusal":
        category = getattr(response.stop_details, "category", None) if response.stop_details else None
        raise AIUnavailable(f"model declined ({category or 'no category'})")
    if response.stop_reason == "max_tokens":
        raise AIUnavailable("answer was cut off")
    text = next((block.text for block in response.content if block.type == "text"), None)
    try:
        answer = json.loads(text) if text else None
    except json.JSONDecodeError:
        answer = None
    if not isinstance(answer, dict):
        raise AIUnavailable("answer was not JSON")
    answer["_model"] = response.model
    cache.set_json_sync(key, answer, CACHE_TTL_S)
    return answer


def untrusted(label: str, text: str) -> str:
    """Wrap attacker-written text in a delimited block it cannot close early."""
    tag = f"untrusted_{label}"
    cleaned = text.replace(f"</{tag}", "</ " + tag).replace(f"<{tag}", "< " + tag)
    return f"<{tag}>\n{cleaned}\n</{tag}>"
