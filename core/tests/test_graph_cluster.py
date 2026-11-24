from graph_helpers import ingest
from sqlalchemy import select

from app.models import AuditLog, Campaign, Check, Entity

PHONE = "+971500000001"


def campaign_ids(session, *domains):
    rows = session.scalars(select(Entity).where(Entity.kind == "domain", Entity.value.in_(domains)))
    return {row.value: row.campaign_id for row in rows}


def test_shared_phone_forms_one_campaign(session, published):
    ingest(session, "a.example", phones=[PHONE], brand="UAE PASS")
    assert campaign_ids(session, "a.example") == {"a.example": None}
    ingest(session, "b.example", phones=[PHONE], brand="UAE PASS")
    ids = campaign_ids(session, "a.example", "b.example")
    assert ids["a.example"] is not None and ids["a.example"] == ids["b.example"]
    campaign = session.get(Campaign, ids["a.example"])
    assert campaign.name.startswith("UAE PASS · a.example · ")
    assert campaign.last_activity_at is not None
    assert {c.campaign_id for c in session.scalars(select(Check).where(Check.domain.in_(["a.example", "b.example"])))} == {campaign.id}
    assert published == []
    session.commit()
    assert published == [("campaign.new_domain", {"campaign_id": campaign.id, "domain": "b.example"})]


def test_third_domain_joins_existing_campaign(session):
    ingest(session, "a.example", phones=[PHONE])
    ingest(session, "b.example", phones=[PHONE], brand="UAE PASS")
    ingest(session, "c.example", phones=[PHONE])
    assert len(set(campaign_ids(session, "a.example", "b.example", "c.example").values())) == 1
    assert session.scalar(select(Entity.domain_count).where(Entity.kind == "phone")) == 3


def test_shared_name_servers_do_not_cluster(session):
    ingest(session, "a.example", name_servers=["ns1.bigprovider.net"])
    ingest(session, "b.example", name_servers=["ns1.bigprovider.net"])
    assert set(campaign_ids(session, "a.example", "b.example").values()) == {None}


def test_shared_registrar_does_not_cluster(session):
    ingest(session, "a.example", registrar="Big Registrar")
    ingest(session, "b.example", registrar="Big Registrar")
    assert set(campaign_ids(session, "a.example", "b.example").values()) == {None}


def test_shared_ip_behind_proxy_does_not_cluster(session):
    ingest(session, "a.example", ip="104.16.0.1", proxy="cloudflare")
    ingest(session, "b.example", ip="104.16.0.1", proxy="cloudflare")
    assert set(campaign_ids(session, "a.example", "b.example").values()) == {None}


def test_shared_ip_without_proxy_clusters(session):
    ingest(session, "a.example", ip="203.0.113.9")
    ingest(session, "b.example", ip="203.0.113.9")
    ids = campaign_ids(session, "a.example", "b.example")
    assert ids["a.example"] is not None and ids["a.example"] == ids["b.example"]


def test_hub_entity_does_not_merge(session):
    ingest(session, "a.example", phones=[PHONE], hub_threshold=2)
    ingest(session, "b.example", phones=[PHONE], hub_threshold=2)
    ingest(session, "c.example", phones=[PHONE], hub_threshold=2)
    assert session.scalar(select(Entity.domain_count).where(Entity.kind == "phone")) == 3
    assert campaign_ids(session, "c.example") == {"c.example": None}


def test_merge_keeps_oldest_campaign_and_audits(session):
    ingest(session, "a1.example", phones=["+971500000011"])
    ingest(session, "a2.example", phones=["+971500000011"])
    ingest(session, "b1.example", phones=["+971500000022"])
    ingest(session, "b2.example", phones=["+971500000022"])
    before = campaign_ids(session, "a1.example", "b1.example")
    assert before["a1.example"] != before["b1.example"]
    oldest = min(
        session.scalars(select(Campaign).where(Campaign.id.in_(before.values()))), key=lambda c: c.first_seen
    )
    ingest(session, "bridge.example", phones=["+971500000011", "+971500000022"])
    ids = campaign_ids(session, "a1.example", "a2.example", "b1.example", "b2.example", "bridge.example")
    assert set(ids.values()) == {oldest.id}
    assert len(session.scalars(select(Campaign).where(Campaign.id.in_(before.values()))).all()) == 1
    audit = session.scalars(select(AuditLog).where(AuditLog.action == "campaign.merge")).one()
    assert audit.actor == "system" and audit.target == oldest.id


def test_country_is_never_an_entity(session):
    ingest(session, "a.example", ip="203.0.113.9", ip_country="AE")
    assert session.scalars(select(Entity).where(Entity.kind == "country")).all() == []
    assert "AE" not in session.scalars(select(Entity.value)).all()


def test_official_hotline_does_not_cluster(session):
    ingest(session, "a.example", phones=["+971600561111"])
    ingest(session, "b.example", phones=["+971600561111"])
    assert set(campaign_ids(session, "a.example", "b.example").values()) == {None}
    ingest(session, "c.example", phones=["+971600561111", PHONE])
    ingest(session, "d.example", phones=[PHONE])
    assert len(set(campaign_ids(session, "c.example", "d.example").values())) == 1
    assert campaign_ids(session, "c.example")["c.example"] is not None


def test_official_payment_host_does_not_cluster(session):
    ingest(session, "a.example", payment_hosts=["pay.uaepass.ae"])
    ingest(session, "b.example", payment_hosts=["pay.uaepass.ae"])
    assert set(campaign_ids(session, "a.example", "b.example").values()) == {None}
