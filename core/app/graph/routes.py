from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.admin.cases import state_of
from app.admin.review import PROTECTED, apply_decision
from app.db import get_session
from app.graph.schemas import (
    CampaignDetail,
    CampaignDomain,
    CampaignGraph,
    CampaignList,
    CampaignLocation,
    CampaignSummary,
    ConfirmRequest,
    ConfirmResponse,
    DomainCounts,
    GraphEdge,
    GraphNode,
    SharedEntity,
    Skipped,
)
from app.infra import location
from app.models import Campaign, Check, Domain, Edge, Entity, Evidence, Review

router = APIRouter()

SessionDep = Annotated[Session, Depends(get_session)]
ACTIVE_WINDOW = timedelta(hours=24)


def require_campaign(session: Session, campaign_id: str) -> Campaign:
    campaign = session.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(404, "Unknown campaign")
    return campaign


def member_domains(session: Session, campaign_id: str) -> list[str]:
    return list(session.scalars(select(Entity.value).where(Entity.kind == "domain", Entity.campaign_id == campaign_id).order_by(Entity.id)))


def latest_evidence(session: Session, domain: str) -> Evidence | None:
    query = select(Evidence).join(Check, Check.id == Evidence.check_id).where(Check.domain == domain).order_by(Evidence.seq.desc())
    return session.scalars(query).first()


def header(campaign: Campaign, confirmed: int) -> dict:
    last = campaign.last_activity_at
    return {
        "id": campaign.id,
        "name": campaign.name,
        "brand": campaign.brand_id,
        "status": "campaign" if confirmed else "suspected",
        "first_seen": campaign.first_seen,
        "last_activity_at": last,
        "active": last is not None and datetime.now(UTC) - last <= ACTIVE_WINDOW,
    }


def confirmed_among(session: Session, domains: list[str]) -> set[str]:
    return set(session.scalars(select(Domain.domain).where(Domain.domain.in_(domains), Domain.status == "confirmed")))


@router.get("/campaigns", response_model=CampaignList)
def list_campaigns(session: SessionDep) -> CampaignList:
    summaries = []
    for campaign in session.scalars(select(Campaign).order_by(Campaign.last_activity_at.desc())):
        domains = member_domains(session, campaign.id)
        confirmed = len(confirmed_among(session, domains))
        summaries.append(CampaignSummary(**header(campaign, confirmed), domains=DomainCounts(total=len(domains), confirmed=confirmed)))
    return CampaignList(campaigns=summaries)


@router.get("/campaigns/{campaign_id}", response_model=CampaignDetail)
def campaign_detail(campaign_id: str, session: SessionDep) -> CampaignDetail:
    campaign = require_campaign(session, campaign_id)
    domains = []
    places = Counter()
    rows = {row.domain: row for row in session.scalars(select(Domain).where(Domain.domain.in_(member_domains(session, campaign_id))))}
    for domain in member_domains(session, campaign_id):
        row = rows.get(domain)
        evidence = latest_evidence(session, domain)
        review = session.scalars(select(Review).where(Review.domain == domain).order_by(Review.id.desc())).first()
        domains.append(
            CampaignDomain(
                domain=domain,
                state=state_of(row, review),
                score=evidence.payload["risk"]["score"] if evidence else None,
                evidence_id=evidence.id if evidence else None,
                excluded=row.status if row is not None and row.status in PROTECTED else None,
            )
        )
        if evidence:
            places[tuple(location(evidence.payload["infrastructure"]).items())] += 1
    shared = session.execute(
        select(Entity.kind, Entity.value, Edge.strength, Entity.domain_count)
        .join(Edge, Edge.dst_id == Entity.id)
        .where(Edge.campaign_id == campaign_id)
        .group_by(Entity.id, Edge.strength)
        .having(Entity.domain_count > 1)
        .order_by(Edge.strength.desc(), Entity.kind, Entity.value)
    )
    return CampaignDetail(
        **header(campaign, sum(d.state in ("confirmed", "auto_confirmed") for d in domains)),
        domains=domains,
        shared=[SharedEntity(kind=k, value=v, strength=s, domain_count=n) for k, v, s, n in shared],
        locations=[CampaignLocation(**dict(place), domains=count) for place, count in places.items()],
    )


@router.get("/campaigns/{campaign_id}/graph", response_model=CampaignGraph)
def campaign_graph(campaign_id: str, session: SessionDep) -> CampaignGraph:
    require_campaign(session, campaign_id)
    edges = list(session.scalars(select(Edge).where(Edge.campaign_id == campaign_id).order_by(Edge.id)))
    ids = {e.src_id for e in edges} | {e.dst_id for e in edges}
    entities = session.scalars(select(Entity).where(Entity.id.in_(ids)).order_by(Entity.id))
    return CampaignGraph(
        nodes=[GraphNode(data={"id": str(e.id), "label": e.value, "kind": e.kind}) for e in entities],
        edges=[GraphEdge(data={"id": str(e.id), "source": str(e.src_id), "target": str(e.dst_id), "strength": e.strength}) for e in edges],
    )


@router.post("/campaigns/{campaign_id}/confirm", response_model=ConfirmResponse)
def confirm_campaign(campaign_id: str, body: ConfirmRequest, session: SessionDep) -> ConfirmResponse:
    require_campaign(session, campaign_id)
    members = set(member_domains(session, campaign_id))
    rows = {row.domain: row for row in session.scalars(select(Domain).where(Domain.domain.in_(members)))}
    confirmed, skipped = [], []
    for domain in dict.fromkeys(body.domains):
        row = rows.get(domain)
        evidence = latest_evidence(session, domain)
        if domain not in members:
            reason = "not_in_campaign"
        elif row is not None and row.status in PROTECTED:
            reason = row.status
        elif evidence is None:
            reason = "no_evidence"
        elif row is not None and row.status == "confirmed":
            reason = "already_confirmed"
        else:
            apply_decision(session, domain, evidence.id, "confirm", None, body.reviewer)
            confirmed.append(domain)
            continue
        skipped.append(Skipped(domain=domain, reason=reason))
    session.commit()
    return ConfirmResponse(confirmed=confirmed, skipped=skipped)
