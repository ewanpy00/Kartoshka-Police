"""Deep analysis of one check (ARCHITECTURE.md 1.3), run by the RQ worker.

Sandbox capture and infrastructure lookups run in parallel. Their signals are added to the fast reasons,
the score is recomputed, an evidence record is appended to the chain, the domain's edges go into the
campaign graph, and every check of the same host that joined this analysis gets the same result.
"""
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from urllib.parse import urlsplit

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app import cache, queue
from app.brands import arabic_name, display_name, find_brand, safe_action, scoring_brands
from app.config import Settings, get_settings
from app.db import get_engine
from app.deep import infra, kit, signals, visual, watchlist
from app.evidence import store
from app.fast import intel, rdap
from app.fast.score import age_reason
from app.graph import build as graph
from app.models import Check, Domain, Verdict
from app.normalize.url import normalize
from app.verdict.bands import band, ordered, source, total
from app.verdict.reasons import KIND_AR, ago_ar, ago_en, reason

log = logging.getLogger("core.deep")

DEEP_SOURCE_IDS = ("rdap", "ct", "campaign", "sandbox", "ai")
CAPTURE_TIMEOUT_S = 90
ARTIFACT_KINDS = {"screenshot": "screenshot", "full_screenshot": "full_screenshot", "html": "html", "favicon": "favicon"}


class Unreachable(Exception):
    pass


class Refused(Exception):
    pass


def capture(url: str, settings: Settings) -> dict:
    response = httpx.post(f"{settings.sandbox_url}/capture", json={"url": url, "second_visit": True}, timeout=CAPTURE_TIMEOUT_S)
    if response.status_code == 502:
        raise Unreachable(response.json().get("detail", "navigation failed"))
    if response.status_code == 422:
        raise Refused(response.json().get("detail", "refused"))
    response.raise_for_status()
    return response.json()


def merge(base: list[dict], extra: list[dict]) -> list[dict]:
    """Fast reasons first, then new deep ones; a code that appears twice keeps its larger weight."""
    by_code = {item["code"]: item for item in base}
    order = [item["code"] for item in base]
    for item in extra:
        current = by_code.get(item["code"])
        if current is None:
            order.append(item["code"])
            by_code[item["code"]] = item
        elif (item["weight"] or 0) > (current["weight"] or 0):
            by_code[item["code"]] = item
    return [by_code[code] for code in order]


@dataclass
class Finding:
    """What the deep analysis of a host found; applied to the check and to every check that joined it."""

    reasons: list[dict] = field(default_factory=list)
    sources: dict[str, dict] = field(default_factory=dict)
    page: signals.Signals = field(default_factory=signals.Signals)
    host: str = ""
    preview: dict | None = None
    evidence_id: str | None = None
    campaign_id: str | None = None
    capture: dict | None = None
    visual: dict | None = None


def graph_nodes(session: Session, cap: dict | None, found: signals.Signals, infra_data: dict,
                kit_hash: str | None, kit_sim: int | None) -> list[tuple[str, str]]:
    nodes: list[tuple[str, str]] = []
    ips = set(infra_data.get("a") or [])
    if cap and cap.get("server_ip"):
        ips.add(cap["server_ip"])
    for ip in sorted(ips):
        nodes.append(("ip_shared" if infra.shared_ip(ip, infra_data) else "ip", ip))
    for info in (infra_data.get("asn") or {}).values():
        nodes.append(("asn", f"AS{info['asn']} {info.get('name', '')}".strip()))
    for ns in infra_data.get("ns") or []:
        provider = intel.lookup_domain(session, signals.registrable(ns))
        nodes.append(("ns_provider" if provider is not None else "ns", ns))
    registration = infra_data.get("rdap") or {}
    if registration.get("registrar"):
        nodes.append(("registrar", registration["registrar"]))
    if cap:
        tls = cap.get("tls") or {}
        if tls.get("subjectName"):
            nodes.append(("cert", f"{tls.get('issuer')}|{tls['subjectName']}|{tls.get('validFrom')}"))
        if kit_hash:
            nodes.append(("kit_hash", kit_hash))
        if kit_sim is not None:
            nodes.append(("kit_sim", f"{kit_sim:016x}"))
        if cap.get("favicon"):
            nodes.append(("favicon_hash", cap["favicon"]["sha256"]))
    nodes += [("phone", phone) for phone in found.phones]
    nodes += [("payment", host) for host in found.payment_hosts]
    return nodes


def sandbox_detail(found: signals.Signals, visual_hit: dict | None, kit_found: list[dict]) -> str:
    parts = []
    if found.asks_for:
        parts.append("asks for " + ", ".join(found.asks_for))
    if visual_hit:
        parts.append(f"looks {round(visual_hit['similarity'] * 100)}% like {display_name(visual_hit['brand'])}")
    if kit_found:
        parts.append("known kit")
    if found.cloaking:
        parts.append("cloaking")
    if found.parked:
        parts.append("parked; on the watchlist")
    return "; ".join(parts) or "nothing suspicious on the page"


def analyse_page(session: Session, cap: dict, site: str, claimed: dict | None, brands: list[dict], finding: Finding) -> tuple[str | None, int | None]:
    host = urlsplit(cap["final_url"]).hostname or finding.host
    finding.host = host
    found = signals.analyse(cap, host, claimed, brands)
    finding.page = found
    finding.reasons += found.reasons
    visual_hit = None
    shot = cap.get("screenshot")
    if shot:
        try:
            visual_hit = visual.best_match(session, shot["path"], host, brands)
        except OSError as error:
            log.warning("screenshot unreadable %s: %r", shot["path"], error)
    if visual_hit:
        brand = visual_hit["brand"]
        finding.reasons.append(reason("VISUAL_MATCH", pct=round(visual_hit["similarity"] * 100),
                                      brand=display_name(brand), brand_ar=arabic_name(brand)))
        if found.brand is None:
            found.brand = brand
    kit_hash, kit_sim = kit.skeleton_hash(cap.get("skeleton") or ""), kit.simhash(cap.get("skeleton") or "")
    favicon = (cap.get("favicon") or {}).get("sha256")
    kit_found = kit.kit_reasons(session, site, kit_hash, kit_sim, favicon)
    finding.reasons += kit_found
    weighted = [item for item in found.reasons + kit_found if (item["weight"] or 0) > 0] + ([visual_hit] if visual_hit else [])
    finding.sources["sandbox"] = source("sandbox", "hit" if weighted else "clean", sandbox_detail(found, visual_hit, kit_found))
    finding.visual = visual_hit
    return kit_hash, kit_sim


def infra_reasons(infra_data: dict, fast_codes: set[str], finding: Finding) -> None:
    registration = infra_data.get("rdap")
    hours = rdap.age_hours(registration)
    if hours is not None:
        age = age_reason(hours)
        if age and "DOMAIN_AGE" not in fast_codes:
            finding.reasons.append(age)
        finding.sources["rdap"] = source("rdap", "hit" if age else "clean", f"registered {ago_en(hours)}")
    ct = infra_data.get("ct") or {}
    hours = infra.hours_since_iso(ct.get("first_seen"))
    if hours is not None:
        if hours < 72 and "FRESH_CERT" not in fast_codes:
            finding.reasons.append(reason("FRESH_CERT", age=ago_en(hours), age_ar=ago_ar(hours)))
        finding.sources["ct"] = source("ct", "hit" if hours < 72 else "clean", f"first certificate {ago_en(hours)}")


def apply(check: Check, finding: Finding, brands: list[dict]) -> None:
    reasons = [item for item in merge(check.reasons or [], finding.reasons) if item["code"] != "BRAND_CREDENTIALS"]
    floor = signals.credential_floor(reasons, finding.page, finding.host or check.host or "")
    if floor:
        reasons.append(floor)
    check.reasons = reasons
    check.score = total(reasons)
    check.verdict = band(check.score)
    check.stage = "deep"
    sources = {item["id"]: item for item in check.sources or []}
    sources.update({key: value for key, value in finding.sources.items() if key in DEEP_SOURCE_IDS})
    check.sources = ordered(sources)
    brand = finding.page.brand
    if brand is not None and check.brand_id is None:
        check.brand, check.brand_id = display_name(brand), brand["id"]
    if check.brand_id and check.verdict != "allow" and not check.safe_action:
        known = find_brand(brands, check.brand_id)
        if known:
            check.safe_action = safe_action(known, check.final_url or check.url)
    check.preview = finding.preview
    check.evidence_id = finding.evidence_id
    check.campaign_id = finding.campaign_id or check.campaign_id
    check.deep_status = "done"


def payload(check: Check, finding: Finding, infra_data: dict, kit_hash: str | None, kit_sim: int | None, failure: str | None) -> dict:
    cap = finding.capture or {}
    found = finding.page
    visual_hit = finding.visual
    return {
        "check_id": check.id,
        "url": check.url,
        "final_url": cap.get("final_url") or check.final_url or check.url,
        "chain": cap.get("chain") or check.chain or [],
        "host": check.host,
        "domain": check.domain,
        "discovered_via": check.source,
        "captured_at": datetime.now(UTC).isoformat(),
        "brand": display_name(found.brand) if found.brand else check.brand,
        "verdict": check.verdict,
        "score": check.score,
        "reasons": check.reasons,
        "sources": check.sources,
        "failure": failure,
        "page": {
            "title": cap.get("title"), "status": cap.get("status"), "lang": cap.get("lang"),
            "text_excerpt": (cap.get("text") or "")[:3000], "forms": cap.get("forms") or [],
            "scripts": (cap.get("scripts") or [])[:50], "request_hosts": (cap.get("request_hosts") or [])[:50],
            "asks_for": found.asks_for, "phones": found.phones, "payment_hosts": found.payment_hosts,
            "tls": cap.get("tls"), "server_ip": cap.get("server_ip"), "parked": found.parked,
            "cloaking": found.cloaking, "bot_visit": cap.get("bot_visit"),
        },
        "visual": {"brand_id": visual_hit["brand"]["id"], "similarity": visual_hit["similarity"],
                   "reference_url": visual_hit["reference_url"], "phash": visual_hit["hash"]} if visual_hit else None,
        "kit": {"kit_hash": kit_hash, "kit_sim": f"{kit_sim:016x}" if kit_sim is not None else None,
                "favicon_sha256": (cap.get("favicon") or {}).get("sha256")},
        "infra": infra_data,
        "sandbox": {
            "profile": "Android phone, ar-AE, Asia/Dubai", "exit": "sandbox_net (no UAE exit IP)",
            "internal_requests_blocked": cap.get("internal_requests_blocked"),
            "navigation_blocked": cap.get("navigation_blocked"), "elapsed_ms": cap.get("elapsed_ms"),
        },
        "artifacts": artifacts(cap),
    }


def artifacts(cap: dict) -> list[dict]:
    return [
        {"kind": kind, "sha256": cap[key]["sha256"], "path": cap[key]["path"], "bytes": cap[key].get("bytes")}
        for key, kind in ARTIFACT_KINDS.items() if cap.get(key)
    ]


def analyse(session: Session, check: Check, settings: Settings) -> list[Check]:
    brands = scoring_brands(settings.data_dir)
    target = check.final_url or check.url
    n = normalize(target)
    claimed = find_brand(brands, check.brand_id)
    finding = Finding(host=n.host)
    failure = None
    with ThreadPoolExecutor(max_workers=2) as pool:
        capture_job = pool.submit(capture, target, settings)
        infra_job = pool.submit(infra.collect, n.host, n.domain or n.host)
        try:
            finding.capture = capture_job.result()
        except Unreachable as error:
            failure = f"unreachable: {error}"[:300]
        except Refused as error:
            failure = f"refused: {error}"[:300]
        infra_data = infra_job.result()

    site = intel.site_key(session, n.host, n.domain)
    kit_hash = kit_sim = None
    cap = finding.capture
    if cap is None and failure and failure.startswith("unreachable"):
        finding.reasons.append(reason("UNREACHABLE"))
        finding.sources["sandbox"] = source("sandbox", "unknown", "page did not load; on the watchlist")
        watchlist.add(session, site, target, "UNREACHABLE", check.brand_id)
    elif cap is None:
        finding.sources["sandbox"] = source("sandbox", "skipped", "internal address")
    elif cap.get("navigation_blocked"):
        finding.sources["sandbox"] = source("sandbox", "unknown", "page redirects to an internal address")
    else:
        kit_hash, kit_sim = analyse_page(session, cap, site, claimed, brands, finding)
        if finding.page.parked:
            watchlist.add(session, site, target, "PARKED", check.brand_id)
        else:
            watchlist.seen_live(session, site)

    fast_codes = {item["code"] for item in check.reasons or []}
    infra_reasons(infra_data, fast_codes, finding)

    nodes = graph_nodes(session, cap, finding.page, infra_data, kit_hash, kit_sim)
    confirmed = session.get(Domain, site)
    links = intel.campaign_links(session, [(kind, value) for kind, value in nodes if kind in graph.LINKING])
    if links and "CAMPAIGN_LINK" not in fast_codes and not (confirmed and confirmed.status == "confirmed"):
        kind, value, campaign = links[0]
        finding.reasons.append(reason("CAMPAIGN_LINK", kind=kind, kind_ar=KIND_AR.get(kind, kind), value=value, campaign=campaign.id))
        finding.sources["campaign"] = source("campaign", "hit", f"{campaign.id}, {campaign.domain_count} domains")
    finding.sources["ai"] = source("ai", "skipped", "AI layer not configured" if not settings.ai_enabled else "not run")

    apply(check, finding, brands)
    evidence = store.append(session, check.id, check.domain, payload(check, finding, infra_data, kit_hash, kit_sim, failure),
                            artifacts(cap or {}))
    finding.evidence_id = check.evidence_id = evidence.id
    if cap and cap.get("screenshot"):
        finding.preview = check.preview = {"screenshot": f"/v1/preview/{evidence.id}.png", "asks_for": finding.page.asks_for}
    if cap:
        check.internal_requests_blocked = cap.get("internal_requests_blocked")
        check.navigation_blocked = cap.get("navigation_blocked")
        if not cap.get("navigation_blocked") and cap.get("final_url") and cap["final_url"] != check.url:
            check.final_url = cap["final_url"]
        if len(cap.get("chain") or []) > len(check.chain or []):
            check.chain = cap["chain"]

    graph.record(session, site, nodes, evidence.id)
    campaign = graph.refresh(session, site)
    if campaign is not None:
        finding.campaign_id = check.campaign_id = campaign.id

    updated = [check]
    joined = session.scalars(select(Check).where(Check.host == check.host, Check.deep_status == "joined", Check.id != check.id))
    for other in joined:
        apply(other, finding, brands)
        updated.append(other)
    for item in updated:
        session.add(Verdict(check_id=item.id, verdict=item.verdict, score=item.score, stage=item.stage, reasons=item.reasons))
    return updated


def deep_check(check_id: str) -> None:
    settings = get_settings()
    with sessionmaker(get_engine())() as session:
        check = session.get(Check, check_id)
        if check is None:
            return
        host = check.host or ""
        try:
            updated = analyse(session, check, settings)
            session.commit()
        except Exception:
            session.rollback()
            check = session.get(Check, check_id)
            check.deep_status = "failed"
            session.commit()
            raise
        finally:
            queue.release_deep(host)
        for item in updated:
            cache.publish({
                "type": "check.updated", "check_id": item.id, "domain": item.domain, "verdict": item.verdict,
                "score": item.score, "stage": item.stage, "brand": item.brand, "campaign_id": item.campaign_id,
                "evidence_id": item.evidence_id, "at": datetime.now(UTC).isoformat(),
            })
