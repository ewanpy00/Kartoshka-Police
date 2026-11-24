"""The fast score (section 1.2): lists, cache, lexical features, then lookups inside a time budget.

First decisive hit wins: allowlist -> blocklist -> verdict cache -> feature score.
"""
import asyncio
import hashlib
import logging
from dataclasses import dataclass, field

import httpx
from sqlalchemy.orm import Session

from app import cache
from app.ai import url_model
from app.brands import arabic_name, display_name, find_brand, safe_action, scoring_brands
from app.config import Settings
from app.fast import intel, lookups, rdap
from app.fast.lexical import lexical
from app.normalize.unshorten import expand, is_shortener
from app.normalize.url import NormalizedURL, normalize, strip_query
from app.verdict.bands import band, ordered, source, total
from app.verdict.reasons import ago_ar, ago_en, reason

log = logging.getLogger("core.fast")

KIND_AR = {"ip": "عنوان IP", "ns": "خادم أسماء", "domain": "النطاق", "kit_hash": "بنية الصفحة", "favicon_hash": "أيقونة"}


@dataclass
class Assessment:
    n: NormalizedURL
    score: int
    verdict: str
    reasons: list[dict]
    sources: list[dict]
    features: dict
    brand: dict | None = None
    safe_action: dict | None = None
    decided_by: str = "score"
    timed_out: bool = False
    ips: list[str] = field(default_factory=list)

    def cacheable(self) -> dict:
        return {
            "score": self.score,
            "verdict": self.verdict,
            "reasons": self.reasons,
            "sources": self.sources,
            "features": self.features,
            "brand_id": self.brand["id"] if self.brand else None,
            "safe_action": self.safe_action,
        }


def cache_key(final_url: str) -> str:
    digest = hashlib.sha256(strip_query(final_url).encode()).hexdigest()[:32]
    return f"kp:verdict:{cache.blocklist_version()}:{digest}"


def decided(n: NormalizedURL, row, brands: list[dict], text: str) -> Assessment | None:
    """Allowlist and blocklist decisions."""
    if row is None:
        return None
    sources = {"allowlist": source("allowlist", "clean"), "police_blocklist": source("police_blocklist", "clean")}
    if row.status == "confirmed":
        brand = find_brand(brands, row.brand_id)
        code = "OFFICER_CONFIRMED" if row.source == "officer" else "BLOCKLISTED"
        sources["police_blocklist"] = source("police_blocklist", "hit", "confirmed by police" if row.source == "officer" else "confirmed")
        return Assessment(
            n, 100, "block", [reason(code)], ordered(sources), {}, brand,
            safe_action(brand, n.final, text) if brand else None, decided_by="blocklist",
        )
    code = "OFFICER_CLEARED" if row.status == "cleared" else "ALLOWLISTED"
    sources["allowlist"] = source("allowlist", "hit", row.status)
    return Assessment(n, 0, "allow", [reason(code)], ordered(sources), {}, None, None, decided_by="allowlist")


BACKGROUND: set[asyncio.Task] = set()


async def guarded(coro, budget_s: float, finish_late: bool = False):
    """Run a lookup inside the budget. Returns (result, status) with status ok | timeout | error.

    With finish_late, a lookup that misses the budget keeps running in the background so its
    cached answer is ready for the next check of the same domain.
    """
    try:
        if finish_late:
            task = asyncio.ensure_future(coro)
            BACKGROUND.add(task)
            task.add_done_callback(BACKGROUND.discard)
            task.add_done_callback(lambda t: t.cancelled() or t.exception())
            return await asyncio.wait_for(asyncio.shield(task), timeout=budget_s), "ok"
        return await asyncio.wait_for(coro, timeout=budget_s), "ok"
    except (TimeoutError, asyncio.TimeoutError):
        return None, "timeout"
    except (httpx.HTTPError, ValueError, KeyError) as error:
        log.info("lookup failed: %r", error)
        return None, "error"


def age_reason(hours: float | None) -> dict | None:
    if hours is None:
        return None
    if hours < 24 * 7:
        weight = 25
    elif hours < 24 * 30:
        weight = 15
    elif hours < 24 * 180:
        weight = 5
    else:
        return None
    return reason("DOMAIN_AGE", weight=weight, age=ago_en(hours), age_ar=ago_ar(hours))


async def assess(session: Session, url: str, settings: Settings, budget_ms: int | None = None, text: str = "") -> Assessment:
    budget_s = (budget_ms or settings.fast_lookup_budget_ms) / 1000
    brands = scoring_brands(settings.data_dir)
    loop = asyncio.get_running_loop()
    started = loop.time()

    expansion = None
    if is_shortener(normalize(url).host):
        expansion = await expand(url, budget_s)
    n = normalize(url, expansion.final if expansion else None, expansion.chain if expansion else None)

    original_host = normalize(url).host
    row = intel.lookup_domain(session, n.host)
    if original_host != n.host:
        first = intel.lookup_domain(session, original_host)
        if first is not None and first.status == "confirmed":
            row = first
    result = decided(n, row, brands, text)
    if result:
        return result

    cached = await cache.get_json(cache_key(n.final))
    if cached:
        brand = find_brand(brands, cached.get("brand_id"))
        return Assessment(
            n, cached["score"], cached["verdict"], cached["reasons"], cached["sources"], cached["features"],
            brand, cached.get("safe_action"), decided_by="cache",
        )

    reasons, features, brand = lexical(n, brands)
    if expansion and not expansion.complete:
        reasons.append(reason("SHORTENER"))
    sources: dict[str, dict] = {
        "allowlist": source("allowlist", "clean"),
        "police_blocklist": source("police_blocklist", "clean"),
        "sandbox": source("sandbox", "skipped"),
        "ai": source("ai", "skipped"),
    }

    remaining = max(0.05, budget_s - (loop.time() - started))
    tasks = {"rdap": guarded(rdap.lookup(n.domain), remaining, finish_late=True), "dns": guarded(intel.resolve_a(n.host, remaining), remaining)}
    if settings.google_safe_browsing_api_key:
        tasks["gsb"] = guarded(lookups.gsb(n.final, settings.google_safe_browsing_api_key, remaining), remaining)
    if settings.virustotal_api_key:
        tasks["virustotal"] = guarded(lookups.virustotal(n.final, settings.virustotal_api_key, remaining), remaining)
    if n.is_ip:
        tasks.pop("rdap")
    results = dict(zip(tasks, await asyncio.gather(*tasks.values())))
    timed_out = any(status == "timeout" for _, status in results.values())

    rdap_info, rdap_status = results.get("rdap", (None, "skipped"))
    hours = rdap.age_hours(rdap_info)
    nrd_seen = intel.first_sighting(session, n.domain, "nrd")
    if hours is None and nrd_seen is not None:
        hours = intel.hours_since(nrd_seen)
    age = age_reason(hours)
    if age:
        reasons.append(age)
    features["domain_age_days"] = round(hours / 24, 1) if hours is not None else -1
    if rdap_status == "ok" and rdap_info.get("found"):
        detail = f"registered {ago_en(hours)}" if hours is not None else "registered"
        sources["rdap"] = source("rdap", "hit" if age else "clean", detail)
    elif rdap_status == "ok":
        sources["rdap"] = source("rdap", "unknown", "not found")
    else:
        sources["rdap"] = source("rdap", "unknown" if rdap_status != "skipped" else "skipped", rdap_status)

    gsb_info, gsb_status = results.get("gsb", (None, "skipped"))
    if gsb_status == "ok":
        if gsb_info["hit"]:
            reasons.append(reason("GSB_HIT", threat=gsb_info["threat"]))
        sources["gsb"] = source("gsb", "hit" if gsb_info["hit"] else "clean", gsb_info.get("threat"))
    else:
        sources["gsb"] = source("gsb", "skipped" if gsb_status == "skipped" else "unknown", None if gsb_status == "skipped" else gsb_status)

    vt_info, vt_status = results.get("virustotal", (None, "skipped"))
    if vt_status == "ok" and vt_info.get("known"):
        positives, count = vt_info["positives"], vt_info["total"]
        if positives:
            reasons.append(reason("VT_HIT", weight=40 if positives >= 3 else 20, positives=positives, total=count))
        sources["virustotal"] = source("virustotal", "hit" if positives else "clean", f"{positives}/{count} engines")
    elif vt_status == "ok":
        sources["virustotal"] = source("virustotal", "unknown", "not yet scanned")
    else:
        sources["virustotal"] = source("virustotal", "skipped" if vt_status == "skipped" else "unknown", None if vt_status == "skipped" else vt_status)

    feed = intel.feed_hits(session, n.domain, strip_query(n.final))
    if feed:
        reasons.append(reason("FEED_HIT", feed=feed[0].source))
        sources["feeds"] = source("feeds", "hit", ", ".join(sorted({entry.source for entry in feed})))
    else:
        sources["feeds"] = source("feeds", "clean")

    ct_hours = intel.hours_since(intel.first_sighting(session, n.domain, "ct"))
    if ct_hours is not None:
        if ct_hours < 72 and (brand or reasons):
            reasons.append(reason("FRESH_CERT", age=ago_en(ct_hours), age_ar=ago_ar(ct_hours)))
        sources["ct"] = source("ct", "hit" if ct_hours < 72 else "clean", f"first certificate {ago_en(ct_hours)}")
    else:
        sources["ct"] = source("ct", "unknown", "not seen by the hunter")

    ips = results.get("dns", (None, None))[0] or []
    nodes = [("domain", n.domain)] + [("ip", ip) for ip in ips]
    links = intel.campaign_links(session, nodes)
    if links:
        kind, value, campaign = links[0]
        reasons.append(reason("CAMPAIGN_LINK", kind=kind, kind_ar=KIND_AR.get(kind, kind), value=value, campaign=campaign.id))
        sources["campaign"] = source("campaign", "hit", f"{campaign.id}, {campaign.domain_count} domains")
    else:
        sources["campaign"] = source("campaign", "clean")

    probability = url_model.predict(features)
    if probability is not None:
        features["url_model"] = round(probability, 3)
        if probability >= 0.7:
            weight = round(15 + 25 * (probability - 0.7) / 0.3)
            reasons.append(reason("URL_MODEL", weight=weight, pct=round(probability * 100)))

    score = total(reasons)
    verdict = band(score)
    action = safe_action(brand, n.final, text) if brand and verdict != "allow" else None
    return Assessment(
        n, score, verdict, reasons, ordered(sources), features, brand, action,
        decided_by="score", timed_out=timed_out, ips=ips,
    )


def brand_label(brand: dict | None) -> tuple[str | None, str | None]:
    return (display_name(brand), arabic_name(brand)) if brand else (None, None)
