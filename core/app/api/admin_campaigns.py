"""Officer console, campaigns (D3 of docs/admin-dashboard.md). Every route needs the write token.

A campaign is the set of sites joined by strong links (app.graph.cluster). The officer can confirm the
ticked sites of a campaign in one go (one review per site, each against its own latest evidence), pull a
site out of a campaign (its edges become `excluded`), merge campaigns the graph did not join, and pivot
on any node to see which other sites use it.

An officer merge is stored as a strong `officer_link` entity shared by every site in it, so a later
`rebuild` keeps it; an exclusion is stored on the edges, which clustering ignores.
"""
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app import audit
from app import review as decisions
from app.auth import require_write_token
from app.defang import defang
from app.deps import SessionDep
from app.graph import build as graph
from app.graph import cluster, rules
from app.models import Campaign, Check, Domain, Edge, Entity

router = APIRouter(prefix="/admin", dependencies=[Depends(require_write_token)])
PAGE = 50
GRAPH_MAX_NODES = 200
ACTIVE_FOR = timedelta(days=7)
CONFIRM_FROM = 70  # sites scoring below this arrive unticked in the console


class OfficerBody(BaseModel):
    reviewer: str = Field("Demo Officer", max_length=200)
    note: str = Field("", max_length=2000)


class ConfirmBody(OfficerBody):
    domains: list[str] = Field(min_length=1, max_length=500)


class ExcludeBody(BaseModel):
    domain: str = Field(max_length=500)
    reviewer: str = Field("Demo Officer", max_length=200)
    reason: str = Field(min_length=1, max_length=500)


class MergeBody(BaseModel):
    ids: list[str] = Field(min_length=2, max_length=20)
    reviewer: str = Field("Demo Officer", max_length=200)
    reason: str = Field(min_length=1, max_length=500)


class PivotBody(BaseModel):
    kind: str | None = Field(None, max_length=40)
    value: str | None = Field(None, max_length=500)


def node_id(kind: str, value: str) -> str:
    return f"d:{value}" if kind == "domain" else f"{kind}:{value}"


def label(kind: str, value: str) -> str:
    if kind in ("domain", "ns", "payment"):
        return defang(value)
    if kind in ("kit_hash", "kit_sim", "favicon_hash"):
        return value[:12]
    if kind == "cert":
        return value.split("|")[1] if value.count("|") >= 2 else value[:60]
    return value[:80]


def latest_checks(session: Session, sites: list[str]) -> dict[str, Check]:
    latest: dict[str, Check] = {}
    if not sites:
        return latest
    rows = session.scalars(select(Check).where(or_(Check.domain.in_(sites), Check.host.in_(sites))).order_by(Check.created_at))
    for check in rows:
        for site in (check.host, check.domain):
            if site in sites:
                latest[site] = check
    return latest


def statuses(session: Session, sites: list[str]) -> dict[str, str]:
    if not sites:
        return {}
    return dict(session.execute(select(Domain.domain, Domain.status).where(Domain.domain.in_(sites))).all())


def members(session: Session, campaign_id: str) -> dict[str, int]:
    """Site name -> domain entity id for every site in the campaign."""
    rows = session.execute(
        select(Entity.value, Entity.id).join(Edge, Edge.src_id == Entity.id)
        .where(Edge.campaign_id == campaign_id, Entity.kind == "domain").distinct()
    ).all()
    return dict(rows)


def get_campaign(session: Session, campaign_id: str) -> Campaign:
    campaign = session.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(404, "Unknown campaign")
    return campaign


def summary(campaign: Campaign, now: datetime) -> dict:
    last = campaign.last_activity_at
    return {
        "id": campaign.id, "name": campaign.name, "brand_id": campaign.brand_id,
        "status": "confirmed" if campaign.confirmed_count > 0 else "suspected",
        "domain_count": campaign.domain_count, "confirmed_count": campaign.confirmed_count,
        "first_seen": campaign.first_seen.isoformat(), "last_activity_at": last.isoformat() if last else None,
        "active": bool(last and last >= now - ACTIVE_FOR),
    }


@router.get("/campaigns", description="Campaigns, most recently active first. `status` is suspected (no officer-confirmed "
            "site yet) or confirmed; `active` means a sighting in the last 7 days.")
def campaigns(
    session: SessionDep,
    status: Annotated[str | None, Query(pattern="^(suspected|confirmed)$")] = None,
    brand: str | None = None,
    active: bool | None = None,
    cursor: int = 0,
) -> dict:
    now = datetime.now(UTC)
    query = select(Campaign)
    if status == "suspected":
        query = query.where(Campaign.confirmed_count == 0)
    elif status == "confirmed":
        query = query.where(Campaign.confirmed_count > 0)
    if brand:
        query = query.where(Campaign.brand_id == brand)
    if active is True:
        query = query.where(Campaign.last_activity_at >= now - ACTIVE_FOR)
    elif active is False:
        query = query.where(or_(Campaign.last_activity_at.is_(None), Campaign.last_activity_at < now - ACTIVE_FOR))
    total = session.scalar(select(func.count()).select_from(query.subquery()))
    rows = session.scalars(
        query.order_by(Campaign.last_activity_at.desc().nulls_last(), Campaign.id).offset(cursor).limit(PAGE)).all()
    return {"total": total, "campaigns": [summary(c, now) for c in rows],
            "next_cursor": cursor + PAGE if cursor + PAGE < total else None}


@router.get("/campaigns/{campaign_id}", description="One campaign: its sites with their latest verdict, and the "
            "entities that link them. `tick` says whether the console pre-ticks the site for \"Confirm all\".")
def campaign_detail(campaign_id: str, session: SessionDep) -> dict:
    campaign = get_campaign(session, campaign_id)
    sites = members(session, campaign_id)
    names = sorted(sites)
    latest = latest_checks(session, names)
    status = statuses(session, names)
    links = session.execute(
        select(Edge.src_id, Entity.kind, Entity.value, Entity.domain_count, Edge.strength, Edge.excluded)
        .join(Entity, Entity.id == Edge.dst_id).where(Edge.src_id.in_(sites.values()))
    ).all()
    by_site: dict[int, list[str]] = {}
    shared: dict[tuple[str, str], dict] = {}
    for src_id, kind, value, degree, strength, excluded in links:
        if strength == "strong" and not excluded:
            by_site.setdefault(src_id, []).append(kind)
        entry = shared.setdefault((kind, value), {"kind": kind, "value": value, "label": label(kind, value),
                                                  "strength": strength, "domain_count": degree, "in_campaign": 0})
        entry["in_campaign"] += 1
    domains = []
    for name in names:
        check = latest.get(name)
        domains.append({
            "domain": name, "display": defang(name), "status": status.get(name),
            "score": check.score if check else None, "verdict": check.verdict if check else None,
            "evidence_id": check.evidence_id if check else None, "brand_id": check.brand_id if check else None,
            "last_seen": check.created_at.isoformat() if check else None,
            "links": sorted(set(by_site.get(sites[name], []))),
            "tick": status.get(name) != "confirmed" and bool(check and check.score >= CONFIRM_FROM and check.evidence_id),
        })
    entities = sorted((e for e in shared.values() if e["in_campaign"] > 1 or e["strength"] == "strong"),
                      key=lambda e: (e["strength"] != "strong", -e["in_campaign"], e["kind"]))
    return {**summary(campaign, datetime.now(UTC)), "domains": domains, "entities": entities}


@router.get("/campaigns/{campaign_id}/graph", description="Cytoscape elements for the campaign: its sites and every "
            "entity they use. Above 200 nodes, entities used by only one site are collapsed into per-kind counts.")
def campaign_graph(campaign_id: str, session: SessionDep) -> dict:
    get_campaign(session, campaign_id)
    sites = members(session, campaign_id)
    names = sorted(sites)
    latest = latest_checks(session, names)
    status = statuses(session, names)
    rows = session.execute(
        select(Edge.src_id, Edge.strength, Edge.excluded, Entity.id, Entity.kind, Entity.value, Entity.domain_count)
        .join(Entity, Entity.id == Edge.dst_id).where(Edge.src_id.in_(sites.values()))
    ).all()
    name_of = {entity_id: name for name, entity_id in sites.items()}
    uses: dict[int, int] = {}
    for row in rows:
        uses[row.id] = uses.get(row.id, 0) + 1
    collapsed: dict[str, int] = {}
    keep = {row.id for row in rows}
    if len(names) + len(keep) > GRAPH_MAX_NODES:
        # Weak single-use entities say the least; collapse them first, then single-use strong ones.
        for strong in (False, True):
            for row in rows:
                if len(names) + len(keep) <= GRAPH_MAX_NODES:
                    break
                if row.id in keep and uses[row.id] == 1 and (row.strength == "strong") == strong:
                    keep.discard(row.id)
                    collapsed[row.kind] = collapsed.get(row.kind, 0) + 1
    nodes = []
    for name in names:
        check = latest.get(name)
        nodes.append({"id": node_id("domain", name), "kind": "domain", "label": defang(name), "status": status.get(name),
                      "score": check.score if check else None})
    seen = set()
    edges = []
    for row in rows:
        if row.id not in keep:
            continue
        target = node_id(row.kind, row.value)
        if row.id not in seen:
            seen.add(row.id)
            nodes.append({"id": target, "kind": row.kind, "label": label(row.kind, row.value),
                          "domain_count": row.domain_count, "hub": row.domain_count > cluster.hub_degree()})
        edges.append({"source": node_id("domain", name_of[row.src_id]), "target": target,
                      "strength": row.strength, "excluded": row.excluded})
    return {"nodes": nodes, "edges": edges, "collapsed": [{"kind": k, "count": n} for k, n in sorted(collapsed.items())]}


@router.post("/campaigns/{campaign_id}/confirm", description="Confirm the ticked sites, each with its own review against "
             "its latest evidence. Official, allowlisted (Tranco included) and unchecked sites are refused and listed.")
def confirm_all(campaign_id: str, body: ConfirmBody, session: SessionDep) -> dict:
    get_campaign(session, campaign_id)
    sites = members(session, campaign_id)
    wanted = sorted({d.lower().strip() for d in body.domains})
    latest = latest_checks(session, wanted)
    status = statuses(session, wanted)
    refused, outcomes = [], []
    note = f"[{campaign_id}] {body.note}".strip()
    for site in wanted:
        if site not in sites:
            refused.append({"domain": site, "display": defang(site), "why": "not in this campaign"})
        elif status.get(site) in decisions.PROTECTED:
            refused.append({"domain": site, "display": defang(site), "why": status[site]})
        elif status.get(site) == "confirmed":
            refused.append({"domain": site, "display": defang(site), "why": "already confirmed"})
        elif site not in latest or not latest[site].evidence_id:
            refused.append({"domain": site, "display": defang(site), "why": "no evidence yet"})
        else:
            outcomes.append(decisions.review(session, latest[site].evidence_id, "confirm", body.reviewer, None, note))
    session.commit()
    version = None
    for outcome in outcomes:
        version = decisions.after_commit(outcome) or version
    return {"confirmed": [{"domain": o.domain, "display": defang(o.domain), "evidence_id": o.review.evidence_id}
                          for o in outcomes],
            "refused": refused, "blocklist_version": version}


@router.post("/campaigns/{campaign_id}/exclude", description="Take a site out of the campaign: its edges are marked "
             "excluded, which clustering ignores, and the campaign is recomputed.")
def exclude(campaign_id: str, body: ExcludeBody, session: SessionDep) -> dict:
    get_campaign(session, campaign_id)
    site = body.domain.lower().strip()
    sites = members(session, campaign_id)
    if site not in sites:
        raise HTTPException(404, "That site is not in this campaign")
    session.execute(update(Edge).where(Edge.src_id == sites[site]).values(excluded=True))
    audit.record(session, body.reviewer, "campaign.exclude", "campaign", campaign_id, {"domain": site},
                 {"excluded": True}, body.reason)
    session.flush()
    cluster.refresh(session, site, body.reviewer)
    rest = sorted(set(sites) - {site})
    campaign = cluster.refresh(session, rest[0], body.reviewer) if rest else None
    session.commit()
    return {"domain": site, "display": defang(site), "campaign": campaign.id if campaign else None,
            "domain_count": campaign.domain_count if campaign else 0}


@router.post("/campaigns/merge", description="Merge campaigns the graph did not join. The officer's link is stored as an "
             "`officer_link` entity, so it survives a rebuild. The oldest id is kept.")
def merge(body: MergeBody, session: SessionDep) -> dict:
    ids = list(dict.fromkeys(body.ids))
    found = [get_campaign(session, campaign_id) for campaign_id in ids]
    if len(found) < 2:
        raise HTTPException(422, "Give at least two different campaigns")
    sites: dict[str, int] = {}
    for campaign in found:
        sites.update(members(session, campaign.id))
    link = f"merge_{uuid.uuid4().hex[:8]}"
    for site in sorted(sites):
        graph.record(session, site, [("officer_link", link, "strong")], None)
    campaign = cluster.assign(session, set(sites.values()), body.reviewer, prefer=found)
    audit.record(session, body.reviewer, "campaign.merge.officer", "campaign", campaign.id, {"campaigns": ids},
                 {"campaign": campaign.id, "link": link, "domains": len(sites)}, body.reason)
    session.commit()
    return {**summary(campaign, datetime.now(UTC)), "merged": [c for c in ids if c != campaign.id]}


@router.post("/campaigns/{campaign_id}/pivot", description="Leads: sites outside the campaign that use one of its "
             "entities (or the one named in the body), weak links included. Nothing is changed.")
def pivot(campaign_id: str, body: PivotBody, session: SessionDep) -> dict:
    get_campaign(session, campaign_id)
    sites = members(session, campaign_id)
    entity_query = select(Entity).join(Edge, Edge.dst_id == Entity.id).where(Edge.src_id.in_(sites.values())).distinct()
    if body.kind:
        entity_query = entity_query.where(Entity.kind == body.kind)
    if body.value:
        entity_query = entity_query.where(Entity.value == body.value)
    entities = [e for e in session.scalars(entity_query) if e.domain_count <= cluster.hub_degree() * 4]
    leads: dict[str, dict] = {}
    for entity in entities:
        others = session.scalars(
            select(Entity.value).join(Edge, Edge.src_id == Entity.id)
            .where(Edge.dst_id == entity.id, Entity.kind == "domain", Entity.id.not_in(sites.values())).limit(PAGE)
        ).all()
        for other in others:
            lead = leads.setdefault(other, {"domain": other, "display": defang(other), "via": []})
            lead["via"].append({"kind": entity.kind, "label": label(entity.kind, entity.value),
                                "strong": entity.kind in rules.STRONG_KINDS})
    names = sorted(leads)
    latest = latest_checks(session, names)
    status = statuses(session, names)
    for name in names:
        check = latest.get(name)
        leads[name].update(status=status.get(name), score=check.score if check else None,
                           campaign=check.campaign_id if check else None)
    ordered = sorted(leads.values(), key=lambda lead: (-len(lead["via"]), -(lead["score"] or 0)))
    return {"leads": ordered[:PAGE], "total": len(ordered)}


@router.get("/entities/{kind}/{value:path}", description="One graph node: every site that uses it, with its campaign.")
def entity(kind: str, value: str, session: SessionDep) -> dict:
    row = session.scalar(select(Entity).where(Entity.kind == kind, Entity.value == value))
    if row is None:
        raise HTTPException(404, "Unknown entity")
    edges = session.execute(
        select(Entity.value, Edge.strength, Edge.excluded, Edge.campaign_id, Edge.evidence_id)
        .join(Entity, Entity.id == Edge.src_id).where(Edge.dst_id == row.id).order_by(Entity.value).limit(500)
    ).all()
    names = [e.value for e in edges]
    latest = latest_checks(session, names)
    status = statuses(session, names)
    return {
        "kind": row.kind, "value": row.value, "label": label(row.kind, row.value), "first_seen": row.first_seen.isoformat(),
        "domain_count": row.domain_count, "hub": row.domain_count > cluster.hub_degree(),
        "domains": [{
            "domain": e.value, "display": defang(e.value), "status": status.get(e.value), "strength": e.strength,
            "excluded": e.excluded, "campaign": e.campaign_id, "evidence_id": e.evidence_id,
            "score": latest[e.value].score if e.value in latest else None,
        } for e in edges],
    }
