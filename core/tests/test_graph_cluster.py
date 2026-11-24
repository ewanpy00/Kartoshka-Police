"""Clustering rules (main's 3bad956 and rule tests on feat/app's graph): only strong links merge, official contacts never
link, the hub rule holds, country is not a node, and a campaign needs an officer confirm to be called confirmed."""
import pytest
from factories import make_check
from sqlalchemy import select

import app.brands
from app.graph import build as graph
from app.graph import cluster, rules
from app.models import AuditLog, Campaign, Check, Domain, Entity

PHONE = "+971500000001"
OFFICIAL = "+971600561111"


def site(session, domain, *nodes):
    make_check(session, domain, 90)
    graph.record(session, domain, list(nodes), None)
    return graph.refresh(session, domain)


def campaign_ids(session, *domains):
    return {d: graph.campaign_of(session, d) for d in domains}


@pytest.fixture
def official_phone(monkeypatch):
    monkeypatch.setattr(app.brands, "official_phones", lambda: frozenset({OFFICIAL}), raising=False)


def test_shared_phone_forms_one_campaign(session):
    assert site(session, "a.example", ("phone", PHONE)) is None
    campaign = site(session, "b.example", ("phone", PHONE))
    assert campaign_ids(session, "a.example", "b.example") == {"a.example": campaign.id, "b.example": campaign.id}
    assert {c.campaign_id for c in session.scalars(select(Check).where(Check.domain.in_(["a.example", "b.example"])))} == {campaign.id}
    assert campaign.confirmed_count == 0  # clustering alone never makes it confirmed


@pytest.mark.parametrize("node", [("ns", "ns1.bigprovider.net"), ("registrar", "Big Registrar"), ("asn", "AS64500 X"),
                                  ("kit_sim", "abc")])
def test_weak_links_do_not_cluster(session, node):
    site(session, "a.example", node)
    site(session, "b.example", node)
    assert set(campaign_ids(session, "a.example", "b.example").values()) == {None}


def test_shared_ip_behind_a_cdn_does_not_cluster_but_a_plain_one_does(session):
    assert rules.strength("ip", "104.16.0.1", shared_infra=True) == "weak"
    site(session, "a.example", ("ip", "104.16.0.1", rules.strength("ip", "104.16.0.1", shared_infra=True)))
    site(session, "b.example", ("ip", "104.16.0.1", rules.strength("ip", "104.16.0.1", shared_infra=True)))
    assert set(campaign_ids(session, "a.example", "b.example").values()) == {None}
    site(session, "c.example", ("ip", "203.0.113.9"))
    campaign = site(session, "d.example", ("ip", "203.0.113.9"))
    assert campaign_ids(session, "c.example", "d.example") == {"c.example": campaign.id, "d.example": campaign.id}


def test_hub_entity_does_not_merge(session, monkeypatch):
    monkeypatch.setattr(cluster, "hub_degree", lambda: 2)
    site(session, "a.example", ("phone", PHONE))
    site(session, "b.example", ("phone", PHONE))
    site(session, "c.example", ("phone", PHONE))
    assert session.scalar(select(Entity.domain_count).where(Entity.kind == "phone")) == 3
    assert graph.campaign_of(session, "c.example") is None


def test_hub_degree_comes_from_the_graph_hub_degree_setting():
    from app.config import Settings

    assert Settings(graph_hub_degree=7).graph_hub_degree == 7 and not hasattr(Settings(), "hub_threshold")


def test_official_phone_never_links(session, official_phone):
    site(session, "a.example", ("phone", OFFICIAL))
    site(session, "b.example", ("whatsapp", OFFICIAL.removeprefix("+971")))  # local form of the same number
    assert set(campaign_ids(session, "a.example", "b.example").values()) == {None}
    assert session.scalars(select(Entity).where(Entity.kind.in_(["phone", "whatsapp"]))).all() == []
    site(session, "c.example", ("phone", OFFICIAL), ("phone", PHONE))
    campaign = site(session, "d.example", ("phone", PHONE))
    assert campaign_ids(session, "c.example", "d.example") == {"c.example": campaign.id, "d.example": campaign.id}
    assert [e.value for e in session.scalars(select(Entity).where(Entity.kind == "phone"))] == [PHONE]


def test_a_missing_official_phones_function_counts_as_none(session, monkeypatch):
    monkeypatch.delattr(app.brands, "official_phones", raising=False)
    assert graph.official_phones() == frozenset()
    site(session, "a.example", ("phone", OFFICIAL))
    assert site(session, "b.example", ("phone", OFFICIAL)) is not None  # nothing is official yet, so it still links


def test_official_payment_host_never_links(session):
    site(session, "a.example", ("payment", "pay.uaepass.ae/checkout"))
    site(session, "b.example", ("payment", "pay.uaepass.ae/checkout"))
    assert set(campaign_ids(session, "a.example", "b.example").values()) == {None}
    session.add(Domain(domain="gateway.example", status="allowlisted", source="seed"))
    session.flush()
    site(session, "c.example", ("payment", "gateway.example/pay"))
    site(session, "d.example", ("payment", "gateway.example/pay"))
    assert set(campaign_ids(session, "c.example", "d.example").values()) == {None}
    site(session, "e.example", ("payment", "collector.example/pay"))
    assert site(session, "f.example", ("payment", "collector.example/pay")) is not None


def test_country_is_never_an_entity(session):
    site(session, "a.example", ("ip", "203.0.113.9"), ("country", "AE"))
    assert session.scalars(select(Entity).where(Entity.kind == "country")).all() == []


def test_campaign_is_confirmed_only_after_an_officer_confirm(session):
    site(session, "a.example", ("phone", PHONE))
    campaign = site(session, "b.example", ("phone", PHONE))
    session.add(Domain(domain="a.example", status="confirmed", source="auto", confirmed_by="auto"))
    session.flush()
    cluster.refresh(session, "a.example")
    assert session.get(Campaign, campaign.id).confirmed_count == 0
    session.get(Domain, "a.example").confirmed_by = "officer"
    session.flush()
    cluster.refresh(session, "a.example")
    assert session.get(Campaign, campaign.id).confirmed_count == 1


def test_merge_keeps_oldest_campaign_and_audits(session):
    site(session, "a1.example", ("phone", "+971500000011"))
    site(session, "a2.example", ("phone", "+971500000011"))
    site(session, "b1.example", ("phone", "+971500000022"))
    site(session, "b2.example", ("phone", "+971500000022"))
    before = campaign_ids(session, "a1.example", "b1.example")
    assert before["a1.example"] != before["b1.example"]
    oldest = min(session.scalars(select(Campaign).where(Campaign.id.in_(before.values()))), key=lambda c: c.first_seen)
    site(session, "bridge.example", ("phone", "+971500000011"), ("phone", "+971500000022"))
    ids = campaign_ids(session, "a1.example", "a2.example", "b1.example", "b2.example", "bridge.example")
    assert set(ids.values()) == {oldest.id}
    assert len(session.scalars(select(Campaign).where(Campaign.id.in_(before.values()))).all()) == 1
    entry = session.scalars(select(AuditLog).where(AuditLog.action == "campaign.merge")).one()
    assert entry.actor == "system" and entry.target == oldest.id
