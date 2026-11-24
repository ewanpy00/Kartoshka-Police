"""Takedown requests: creation, state machine and offline detection (docs/admin-dashboard.md, D4).

    pack_ready -> sent -> offline_pending -> closed -> reopened
                   ^----------- live -------'

- Packs are made only for domains an officer confirmed; an auto-confirmed domain is reviewed first.
- Nothing is sent from here. "Send" in the console opens a mailto link and downloads the zip; the
  officer then marks the request sent, which starts the re-checks.
- After `sent` the domain is re-checked every `TAKEDOWN_RECHECK_MIN` minutes. A check is offline only
  when the phone and the bot profile both find the site gone, so geofencing or cloaking cannot fake a
  takedown. `TAKEDOWN_OFFLINE_CHECKS` offline results in a row, at least one interval apart, close it.
- A capture whose page facts could not be read says nothing about the page. Such a check is no result: it
  neither counts toward the offline checks nor resets them, and it is written to the request's audit trail.
- A closed domain stays on the blocklist and on the watchlist for 30 more days; if it comes back the
  request is `reopened`.
- `overdue` is derived (sent longer than `TAKEDOWN_SLA_H` ago and not closed), not stored.
"""
import logging
import statistics
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import dns.exception
import dns.resolver
import httpx
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app import audit, cache
from app.brands import scoring_brands
from app.config import Settings, get_settings
from app.deep import signals
from app.fast import lookups, rdap
from app.models import Check, Domain, Evidence, TakedownRequest, Watchlist
from app.review import confirmer
from app.takedown import contacts, pack

OPEN = ("sent", "offline_pending", "reopened")
STATES = ("pack_ready", "sent", "offline_pending", "closed", "reopened")
KEEP_WATCHING = timedelta(days=30)
VT_REFRESH = timedelta(hours=24)
logger = logging.getLogger(__name__)
GONE_STATUS = (404, 410)
HOLD = ("client hold", "server hold")
CF_INTERSTITIAL = ("suspected phishing", "reported for potential phishing", "this website has been reported")


class Refused(Exception):
    pass


class Unreadable(Exception):
    """The capture carries no readable page facts, so it cannot say whether the page is live or gone."""


@dataclass
class Probe:
    offline: bool
    reason: str | None = None
    profiles: dict = field(default_factory=dict)
    readable: bool = True  # False: a profile could not read the page, so this probe is no result


def latest_evidence(session: Session, domain: str) -> tuple[Check, Evidence] | None:
    check = session.scalar(
        select(Check).where((Check.domain == domain) | (Check.host == domain), Check.evidence_id.is_not(None))
        .order_by(Check.created_at.desc()).limit(1))
    if check is None:
        return None
    return check, session.get(Evidence, check.evidence_id)


def new_id() -> str:
    return f"td_{uuid.uuid4().hex[:12]}"


def create(session: Session, domains: list[str], reviewer: str, now: datetime | None = None,
           ip_lookup=None) -> tuple[list[TakedownRequest], list[dict]]:
    """One request per domain and recipient; one pack per recipient. The caller commits."""
    now = now or datetime.now(UTC)
    ip_lookup = ip_lookup or contacts.ip_abuse
    refused, ready = [], []
    for domain in sorted({d.lower().strip() for d in domains}):
        row = session.get(Domain, domain)
        if row is None or row.status != "confirmed":
            refused.append({"domain": domain, "why": "not confirmed"})
            continue
        if confirmer(row) != "officer":
            refused.append({"domain": domain, "why": "auto-confirmed: an officer must review it first"})
            continue
        found = latest_evidence(session, domain)
        if found is None:
            refused.append({"domain": domain, "why": "no evidence record"})
            continue
        ready.append((domain, *found))
    groups: dict[tuple[str, str], list] = {}
    for domain, check, evidence in ready:
        infra = (evidence.payload or {}).get("infra") or {}
        open_kinds = set(session.scalars(select(TakedownRequest.recipient_kind).where(
            TakedownRequest.domain == domain, TakedownRequest.status != "closed")))
        fresh = [r for r in contacts.recipients(domain, infra, ip_lookup) if r.kind not in open_kinds]
        if not fresh:
            refused.append({"domain": domain, "why": "requests already open for every recipient"})
        for recipient in fresh:
            groups.setdefault((recipient.kind, recipient.recipient), []).append((domain, check, evidence))
    created = []
    for (kind, recipient), members in groups.items():
        items = [pack.Item(domain, evidence, check.brand) for domain, check, evidence in members]
        digest = pack.sha256(pack.build(session, recipient, kind, items, now))
        for domain, check, _ in members:
            request = TakedownRequest(id=new_id(), domain=domain, campaign_id=check.campaign_id, recipient_kind=kind,
                                      recipient=recipient, status="pack_ready", pack_sha256=digest, generated_at=now,
                                      checks_offline=0)
            session.add(request)
            created.append(request)
    for request in created:
        audit.record(session, reviewer, "takedown.create", "takedown", request.id, None,
                     {"domain": request.domain, "recipient_kind": request.recipient_kind, "recipient": request.recipient,
                      "pack_sha256": request.pack_sha256})
    session.flush()
    return created, refused


def batch(session: Session, request: TakedownRequest) -> list[TakedownRequest]:
    """The requests that share this request's pack: same recipient, generated together."""
    return list(session.scalars(select(TakedownRequest).where(
        TakedownRequest.recipient == request.recipient, TakedownRequest.recipient_kind == request.recipient_kind,
        TakedownRequest.generated_at == request.generated_at).order_by(TakedownRequest.domain)))


def pack_bytes(session: Session, request: TakedownRequest) -> bytes:
    items = []
    for member in batch(session, request):
        found = latest_evidence_for(session, member)
        if found is not None:
            items.append(pack.Item(member.domain, found[1], found[0].brand))
    return pack.build(session, request.recipient, request.recipient_kind, items, request.generated_at)


def latest_evidence_for(session: Session, request: TakedownRequest) -> tuple[Check, Evidence] | None:
    """The evidence the pack was built from: the newest record from before the pack was generated."""
    check = session.scalar(
        select(Check).join(Evidence, Evidence.id == Check.evidence_id)
        .where((Check.domain == request.domain) | (Check.host == request.domain), Evidence.created_at <= request.generated_at)
        .order_by(Evidence.created_at.desc()).limit(1))
    return (check, session.get(Evidence, check.evidence_id)) if check else None


def watch(session: Session, domain: str, url: str | None, next_at: datetime, expires_at: datetime) -> None:
    statement = insert(Watchlist).values(domain=domain, url=url, reason="TAKEDOWN", last_status="takedown",
                                         next_check_at=next_at, expires_at=expires_at, checks_done=0)
    session.execute(statement.on_conflict_do_update(
        index_elements=[Watchlist.domain],
        set_={"reason": "TAKEDOWN", "next_check_at": next_at,
              "expires_at": func.greatest(Watchlist.expires_at, statement.excluded.expires_at)},
    ))


def mark_sent(session: Session, request: TakedownRequest, reviewer: str, now: datetime | None = None,
              settings: Settings | None = None) -> list[TakedownRequest]:
    """Marks every request of the pack sent and starts the re-checks. The caller commits."""
    now = now or datetime.now(UTC)
    settings = settings or get_settings()
    if request.status != "pack_ready":
        raise Refused(f"request is {request.status}, not pack_ready")
    members = [m for m in batch(session, request) if m.status == "pack_ready"]
    for member in members:
        member.status, member.sent_at, member.sent_by = "sent", now, reviewer
        audit.record(session, reviewer, "takedown.sent", "takedown", member.id, {"status": "pack_ready"}, {"status": "sent"})
        found = latest_evidence(session, member.domain)
        watch(session, member.domain, found[0].url if found else None,
              now + timedelta(minutes=settings.takedown_recheck_min), now + KEEP_WATCHING)
    session.flush()
    return members


def overdue(request: TakedownRequest, now: datetime, settings: Settings) -> bool:
    return (request.status in OPEN and request.sent_at is not None
            and request.sent_at < now - timedelta(hours=settings.takedown_sla_h))


# --- offline detection (runs in the worker: only the worker reaches the sandbox) ---------------------

def dns_state(host: str) -> str | None:
    """`nxdomain` or `servfail` when the name no longer resolves, None when it does."""
    resolver = dns.resolver.Resolver()
    resolver.lifetime = 5.0
    for rtype in ("A", "AAAA"):
        try:
            resolver.resolve(host, rtype)
            return None
        except dns.resolver.NXDOMAIN:
            return "nxdomain"
        except dns.resolver.NoAnswer:
            continue
        except (dns.resolver.NoNameservers, dns.exception.Timeout):
            return "servfail"
        except dns.exception.DNSException:
            return "servfail"
    return "nxdomain"  # the name exists but has no address


def rdap_state(domain: str) -> str | None:
    try:
        info = rdap.lookup_sync(domain)
    except Exception:
        return None
    states = " ".join(s.lower() for s in (info or {}).get("status") or [])
    return "rdap_hold" if any(h in states for h in HOLD) else None


def page_state(capture: dict, host: str) -> str | None:
    """Why this capture shows no phishing page any more, or None when the page is still live.

    Raises `Unreadable` when the page facts are missing: an unread page has no forms to find, and that must
    never be taken for a removed form or any other offline reason.
    """
    if capture.get("facts_available") is not True:
        raise Unreadable
    if capture.get("status") in GONE_STATUS:
        return "http_gone"
    text = (capture.get("text") or "").lower()
    if any(marker in text for marker in CF_INTERSTITIAL):
        return "cf_interstitial"
    found = signals.analyse(capture, host, None, scoring_brands(get_settings().data_dir))
    if found.parked:
        return "parked"
    if not found.asks_for and not any(form.get("fields") for form in capture.get("forms") or []):
        return "form_removed"
    return None


def capture(url: str, profile: str, settings: Settings) -> tuple[dict | None, str | None]:
    try:
        response = httpx.post(f"{settings.sandbox_url}/capture", json={"url": url, "profile": profile}, timeout=90)
    except httpx.HTTPError:
        return None, None  # the sandbox itself failed: no result, not an offline result
    if response.status_code == 502:
        return None, "refused"
    if response.status_code != 200:
        return None, None
    return response.json(), None


def probe(domain: str, url: str | None, settings: Settings) -> Probe | None:
    """None when the check could not run (sandbox down); otherwise both profiles' results.

    When either profile could not read the page the probe is returned with `readable` false: it is not offline
    and not live, and `recheck` treats it as no result.
    """
    url = url or f"https://{domain}/"
    host = (httpx.URL(url).host or domain).lower()
    gone = dns_state(host) or rdap_state(domain)
    if gone:
        return Probe(True, gone, {"phone": gone, "bot": gone})
    results, unread = {}, set()
    for profile in ("phone", "bot"):
        cap, failure = capture(url, profile, settings)
        if cap is None and failure is None:
            return None
        try:
            results[profile] = failure if cap is None else page_state(cap, host)
        except Unreadable:
            unread.add(profile)
    if unread:
        profiles = {p: "unreadable" if p in unread else results[p] or "live" for p in ("phone", "bot")}
        return Probe(False, None, profiles, readable=False)
    offline = all(results.values())
    return Probe(offline, results["phone"] if offline else None, {k: v or "live" for k, v in results.items()})


def poll_failed(service: str, domain: str, error: Exception) -> None:
    """Log the status code or the exception class only: an httpx message carries the request URL, key included."""
    reason = error.response.status_code if isinstance(error, httpx.HTTPStatusError) else type(error).__name__
    logger.warning("%s poll failed for %s: %s", service, domain, reason)


def first_hits(session: Session, domain: str, url: str | None, settings: Settings, now: datetime) -> None:
    """The one lead-time poller (takedown re-check and watchlist re-check).

    Safe Browsing, with its key set: a hit stamps `domains.gsb_first_hit_at`, a clean answer stamps the watchlist
    row's `gsb_last_clean_at`. VirusTotal likewise, but only when the row's `vt_checked_at` is missing or over 24
    hours old, and it stamps `vt_checked_at`. A service without a key is skipped and nothing is stamped. Once a
    service has flagged the domain it is not polled again. Without a watchlist row only the first hit is recorded;
    without a domain row a hit has nowhere to go, so that poll stamps nothing at all.
    """
    row = session.get(Domain, domain)
    watched = session.get(Watchlist, domain)
    url = url or f"https://{domain}/"

    def record(prefix: str, hit: bool) -> None:
        if hit and row is not None:
            setattr(row, f"{prefix}_first_hit_at", now)
        elif not hit and watched is not None:
            setattr(watched, f"{prefix}_last_clean_at", now)

    if settings.google_safe_browsing_api_key and not (row and row.gsb_first_hit_at):
        try:
            record("gsb", bool(lookups.gsb_sync(url, settings.google_safe_browsing_api_key).get("hit")))
        except Exception as error:
            poll_failed("Safe Browsing", domain, error)
    vt_due = watched is None or watched.vt_checked_at is None or now - watched.vt_checked_at > VT_REFRESH
    if settings.virustotal_api_key and vt_due and not (row and row.vt_first_hit_at):
        try:
            record("vt", lookups.virustotal_sync(url, settings.virustotal_api_key, submit=False).get("positives", 0) > 0)
            if watched is not None:
                watched.vt_checked_at = now
        except Exception as error:
            poll_failed("VirusTotal", domain, error)


def lead_time_of(first_seen: datetime, first_hit_at: datetime | None, last_clean_at: datetime | None) -> dict:
    """Hours between the first check on the domain and the last clean poll. A lower bound, in whole hours."""
    clean = last_clean_at if last_clean_at and (first_hit_at is None or last_clean_at < first_hit_at) else None
    hours = max(int((clean - first_seen).total_seconds() // 3600), 0) if clean else None
    if first_hit_at:
        return {"state": "hit", "at_least_hours": hours or 0}
    if clean:
        return {"state": "ahead", "at_least_hours": hours}
    return {"state": "not_polled", "at_least_hours": None}


def lead_time(first_seen: datetime, domain: Domain | None, watched: Watchlist | None) -> dict:
    """How long the domain was watched before each service listed it: first hits from `domains`, clean polls from the watchlist."""
    return {
        "gsb": lead_time_of(first_seen, domain.gsb_first_hit_at if domain else None, watched.gsb_last_clean_at if watched else None),
        "vt": lead_time_of(first_seen, domain.vt_first_hit_at if domain else None, watched.vt_last_clean_at if watched else None),
    }


def apply(session: Session, request: TakedownRequest, result: Probe, now: datetime, settings: Settings) -> str | None:
    """Move one request by one probe result. Returns the event to publish (closed or reopened), if any."""
    interval = timedelta(minutes=settings.takedown_recheck_min)
    before = request.status
    event = None
    if request.status in ("sent", "offline_pending", "reopened"):
        if result.offline:
            if request.checks_offline == 0 or request.offline_at is None:
                request.checks_offline, request.offline_at = 1, now
            elif now >= request.offline_at + interval * request.checks_offline:
                request.checks_offline += 1
            request.offline_reason = result.reason
            request.status = "offline_pending"
            if request.checks_offline >= settings.takedown_offline_checks:
                request.status = "closed"
                event = "closed"
        else:
            request.checks_offline, request.offline_at, request.offline_reason = 0, None, None
            request.status = "reopened" if before == "reopened" else "sent"
    elif request.status == "closed" and not result.offline:
        request.status, request.checks_offline, request.offline_reason = "reopened", 0, None
        request.offline_at = None
        event = "reopened"
    if request.status != before:
        audit.record(session, "takedown_recheck", "takedown.state", "takedown", request.id, {"status": before},
                     {"status": request.status, "offline_reason": request.offline_reason,
                      "checks_offline": request.checks_offline, "profiles": result.profiles})
    return event


def recheck(session: Session, domain: str, settings: Settings | None = None, now: datetime | None = None,
            prober=probe) -> dict:
    """Probe the domain once and move every open (or closed) request for it. The caller commits."""
    settings = settings or get_settings()
    now = now or datetime.now(UTC)
    requests = list(session.scalars(select(TakedownRequest).where(
        TakedownRequest.domain == domain, TakedownRequest.status.in_(OPEN + ("closed",)))))
    if not requests:
        return {"domain": domain, "requests": 0}
    watched = session.get(Watchlist, domain)
    url = watched.url if watched else None
    result = prober(domain, url, settings)
    if result is None:
        return {"domain": domain, "requests": len(requests), "result": "sandbox unavailable"}
    if not result.readable:
        for request in requests:
            audit.record(session, "takedown_recheck", "takedown.check_unreadable", "takedown", request.id,
                         {"status": request.status},
                         {"status": request.status, "checks_offline": request.checks_offline, "profiles": result.profiles})
        session.flush()
        return {"domain": domain, "requests": len(requests), "result": "page unreadable", "profiles": result.profiles}
    events = []
    for request in requests:
        event = apply(session, request, result, now, settings)
        if event:
            events.append((request, event))
    first_hits(session, domain, url, settings, now)
    still_open = any(r.status in OPEN for r in requests)
    every = timedelta(minutes=settings.takedown_recheck_min) if still_open else timedelta(hours=6)
    if watched is not None:
        watched.last_checked_at, watched.next_check_at = now, now + every
        watched.last_status = result.reason or "live"
        watched.checks_done += 1
        if any(event == "closed" for _, event in events):
            watched.expires_at = max(watched.expires_at, now + KEEP_WATCHING)
    session.flush()
    return {"domain": domain, "requests": len(requests), "offline": result.offline, "reason": result.reason,
            "profiles": result.profiles, "events": [(r.id, e) for r, e in events]}


def publish(events: list[tuple[str, str]], session: Session) -> None:
    for request_id, event in events:
        request = session.get(TakedownRequest, request_id)
        cache.publish({"type": "takedown.offline", "id": request_id, "domain": request.domain, "state": event,
                       "offline_reason": request.offline_reason, "at": datetime.now(UTC).isoformat()})


def has_open(session: Session, domain: str) -> bool:
    return session.scalar(select(func.count()).select_from(TakedownRequest).where(
        TakedownRequest.domain == domain, TakedownRequest.status.in_(OPEN))) > 0


def stats(session: Session, now: datetime | None = None, settings: Settings | None = None) -> dict:
    now = now or datetime.now(UTC)
    settings = settings or get_settings()
    rows = session.scalars(select(TakedownRequest)).all()
    by_status = {state: 0 for state in STATES}
    per_recipient: dict[str, dict] = {}
    hours = []
    for row in rows:
        by_status[row.status] = by_status.get(row.status, 0) + 1
        entry = per_recipient.setdefault(row.recipient_kind, {"requests": 0, "closed": 0, "hours": []})
        entry["requests"] += 1
        if row.status == "closed" and row.sent_at and row.offline_at:
            taken = (row.offline_at - row.sent_at).total_seconds() / 3600
            entry["closed"] += 1
            entry["hours"].append(taken)
            hours.append(taken)
    return {
        "by_status": by_status,
        "overdue": sum(1 for row in rows if overdue(row, now, settings)),
        "median_hours_to_offline": round(statistics.median(hours), 1) if hours else None,
        "recipients": {kind: {"requests": e["requests"], "closed": e["closed"],
                              "median_hours": round(statistics.median(e["hours"]), 1) if e["hours"] else None}
                       for kind, e in sorted(per_recipient.items())},
        "sla_hours": settings.takedown_sla_h,
    }
