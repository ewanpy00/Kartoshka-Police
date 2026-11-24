"""Campaign console routes (D3): list, detail, graph, bulk confirm, exclude, merge, pivot, entity card."""
from factories import make_check, with_evidence
from sqlalchemy import select

from app.graph import build as graph
from app.graph import cluster
from app.models import AuditLog, Domain, Edge, Review

AUTH = {"Authorization": "Bearer test-token"}


def campaign_of(session, sites: list[str], node=("phone", "+971500000901"), scores=None):
    """Sites with a check, evidence and a shared strong node; returns the campaign."""
    for n, site in enumerate(sites):
        check = make_check(session, site, (scores or {}).get(site, 90), hours_ago=n + 1)
        with_evidence(session, check)
        graph.record(session, site, [node, ("asn", "AS64500 EXAMPLE")], check.evidence_id)
    campaign = graph.refresh(session, sites[0])
    session.flush()
    return campaign


def test_list_detail_and_graph(client, session):
    campaign = campaign_of(session, ["c-one.top", "c-two.top", "c-three.top"], scores={"c-three.top": 40})
    listed = client.get("/v1/admin/campaigns?status=suspected", headers=AUTH).json()
    assert campaign.id in {c["id"] for c in listed["campaigns"]}
    confirmed = client.get("/v1/admin/campaigns?status=confirmed", headers=AUTH).json()
    assert campaign.id not in {c["id"] for c in confirmed["campaigns"]}

    detail = client.get(f"/v1/admin/campaigns/{campaign.id}", headers=AUTH).json()
    assert detail["status"] == "suspected" and detail["domain_count"] == 3
    rows = {d["domain"]: d for d in detail["domains"]}
    assert rows["c-one.top"]["display"] == "c-one[.]top" and rows["c-one.top"]["links"] == ["phone"]
    assert rows["c-one.top"]["tick"] and not rows["c-three.top"]["tick"]  # below 70 arrives unticked

    shape = client.get(f"/v1/admin/campaigns/{campaign.id}/graph", headers=AUTH).json()
    kinds = {n["kind"] for n in shape["nodes"]}
    assert kinds == {"domain", "phone", "asn"}
    strengths = {(e["target"].split(":")[0], e["strength"]) for e in shape["edges"]}
    assert strengths == {("phone", "strong"), ("asn", "weak")}
    assert client.get("/v1/admin/campaigns/cmp_missing", headers=AUTH).status_code == 404


def test_confirm_all_writes_one_review_per_site_and_refuses_protected(client, session):
    campaign = campaign_of(session, ["b-one.top", "b-two.top", "b-safe.top"], node=("payment", "collector.example/pay"))
    session.add(Domain(domain="b-safe.top", status="allowlisted", source="seed"))
    session.flush()
    body = client.post(f"/v1/admin/campaigns/{campaign.id}/confirm", headers=AUTH,
                       json={"domains": ["b-one.top", "b-two.top", "b-safe.top", "elsewhere.top"], "reviewer": "Officer C"}).json()
    assert sorted(d["domain"] for d in body["confirmed"]) == ["b-one.top", "b-two.top"]
    assert {r["domain"]: r["why"] for r in body["refused"]} == {"b-safe.top": "allowlisted", "elsewhere.top": "not in this campaign"}
    reviews = session.scalars(select(Review).where(Review.reviewer == "Officer C")).all()
    assert len(reviews) == 2 and all(r.note.startswith(f"[{campaign.id}]") for r in reviews)
    assert session.get(Domain, "b-one.top").status == "confirmed"
    assert session.get(Domain, "b-safe.top").status == "allowlisted"
    detail = client.get(f"/v1/admin/campaigns/{campaign.id}", headers=AUTH).json()
    assert detail["status"] == "confirmed" and detail["confirmed_count"] == 2


def test_exclude_takes_a_site_out_and_is_audited(client, session):
    campaign = campaign_of(session, ["e-one.top", "e-two.top", "e-odd.top"])
    response = client.post(f"/v1/admin/campaigns/{campaign.id}/exclude", headers=AUTH,
                           json={"domain": "e-odd.top", "reviewer": "Officer D", "reason": "shared call centre number"})
    assert response.status_code == 200 and response.json()["domain_count"] == 2
    assert graph.campaign_of(session, "e-odd.top") is None
    assert graph.campaign_of(session, "e-one.top") == campaign.id
    assert session.scalar(select(AuditLog).where(AuditLog.action == "campaign.exclude", AuditLog.target == campaign.id))
    # the exclusion holds through a rebuild
    cluster.rebuild(session)
    assert graph.campaign_of(session, "e-odd.top") is None
    excluded = client.post(f"/v1/admin/campaigns/{campaign.id}/exclude", headers=AUTH,
                           json={"domain": "e-odd.top", "reason": "again"})
    assert excluded.status_code == 404


def test_officer_merge_keeps_the_oldest_and_survives_a_rebuild(client, session):
    first = campaign_of(session, ["g-a.top", "g-b.top"], node=("phone", "+971500000911"))
    second = campaign_of(session, ["g-c.top", "g-d.top"], node=("whatsapp", "+971500000922"))
    body = client.post("/v1/admin/campaigns/merge", headers=AUTH,
                       json={"ids": [second.id, first.id], "reviewer": "Officer E", "reason": "same script and wording"}).json()
    assert body["id"] == first.id and body["merged"] == [second.id] and body["domain_count"] == 4
    cluster.rebuild(session)
    assert {graph.campaign_of(session, s) for s in ("g-a.top", "g-b.top", "g-c.top", "g-d.top")} == {first.id}
    assert client.post("/v1/admin/campaigns/merge", headers=AUTH, json={"ids": [first.id, first.id], "reason": "x"}).status_code == 422


def test_pivot_and_entity_card(client, session):
    campaign = campaign_of(session, ["p-a.top", "p-b.top"], node=("phone", "+971500000933"))
    make_check(session, "p-lead.top", 55)
    graph.record(session, "p-lead.top", [("asn", "AS64500 EXAMPLE")], None)
    leads = client.post(f"/v1/admin/campaigns/{campaign.id}/pivot", headers=AUTH, json={"kind": "asn"}).json()
    lead = next(item for item in leads["leads"] if item["domain"] == "p-lead.top")
    assert lead["via"][0] == {"kind": "asn", "label": "AS64500 EXAMPLE", "strong": False} and lead["score"] == 55

    card = client.get("/v1/admin/entities/phone/+971500000933", headers=AUTH).json()
    assert {d["domain"] for d in card["domains"]} == {"p-a.top", "p-b.top"}
    assert all(d["campaign"] == campaign.id and d["strength"] == "strong" for d in card["domains"])
    assert client.get("/v1/admin/entities/phone/+0", headers=AUTH).status_code == 404


def test_graph_collapses_single_use_entities_above_the_limit(client, session, monkeypatch):
    from app.api import admin_campaigns

    monkeypatch.setattr(admin_campaigns, "GRAPH_MAX_NODES", 6)
    campaign = campaign_of(session, ["k-a.top", "k-b.top"], node=("phone", "+971500000944"))
    for n in range(5):
        graph.record(session, "k-a.top", [("ns", f"ns{n}.example")], None)
    shape = client.get(f"/v1/admin/campaigns/{campaign.id}/graph", headers=AUTH).json()
    assert len(shape["nodes"]) == 6  # 2 sites + phone + asn + 5 name servers = 9; three are collapsed
    assert {"phone", "asn"} <= {n["kind"] for n in shape["nodes"]}  # shared nodes stay
    assert shape["collapsed"] == [{"kind": "ns", "count": 3}]
    assert session.scalar(select(Edge).where(Edge.excluded.is_(True))) is None
