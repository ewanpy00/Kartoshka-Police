from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class DomainCounts(BaseModel):
    total: int
    confirmed: int


class CampaignHeader(BaseModel):
    id: str
    name: str | None
    brand: str | None
    status: Literal["campaign", "suspected"]
    first_seen: datetime
    last_activity_at: datetime | None
    active: bool


class CampaignSummary(CampaignHeader):
    domains: DomainCounts


class CampaignList(BaseModel):
    campaigns: list[CampaignSummary]


class CampaignDomain(BaseModel):
    domain: str
    state: str
    score: int | None
    evidence_id: str | None
    excluded: Literal["official", "allowlisted"] | None


class SharedEntity(BaseModel):
    kind: str
    value: str
    strength: Literal["strong", "weak"]
    domain_count: int


class CampaignLocation(BaseModel):
    hosted_in: str | None
    registered_through: str | None
    network_owner: str | None
    behind_proxy: bool | None
    domains: int


class CampaignDetail(CampaignHeader):
    domains: list[CampaignDomain]
    shared: list[SharedEntity]
    locations: list[CampaignLocation]


class NodeData(BaseModel):
    id: str
    label: str
    kind: str


class EdgeData(BaseModel):
    id: str
    source: str
    target: str
    strength: str


class GraphNode(BaseModel):
    data: NodeData


class GraphEdge(BaseModel):
    data: EdgeData


class CampaignGraph(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class ConfirmRequest(BaseModel):
    domains: list[str]
    reviewer: str


class Skipped(BaseModel):
    domain: str
    reason: Literal["not_in_campaign", "official", "allowlisted", "no_evidence", "already_confirmed"]


class ConfirmResponse(BaseModel):
    confirmed: list[str]
    skipped: list[Skipped]
