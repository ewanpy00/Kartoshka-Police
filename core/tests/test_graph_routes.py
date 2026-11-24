from admin_factories import AUTH
from graph_helpers import ingest
from sqlalchemy import select

from app.models import Campaign, Domain, Review

PHONE = "+971500000001"


def make_campaign(session):
    for domain in ("a.example", "b.example", "google.com"):
        ingest(session, domain, phones=[PHONE], brand="UAE PASS", ip="203.0.113.9", registrar="Big Registrar")
    return session.scalars(select(Campaign)).one()


def test_list_reports_status_and_counts(client, session):
    campaign = make_campaign(session)
    [item] = client.get("/v1/admin/campaigns", headers=AUTH).json()["campaigns"]
    assert (item["id"], item["status"], item["domains"], item["active"]) == (campaign.id, "suspected", {"total": 3, "confirmed": 0}, True)
    session.add(Domain(domain="a.example", status="confirmed"))
    session.flush()
    [item] = client.get("/v1/admin/campaigns", headers=AUTH).json()["campaigns"]
    assert (item["status"], item["domains"]["confirmed"]) == ("campaign", 1)


def test_detail_lists_domains_shared_entities_and_locations(client, session):
    campaign = make_campaign(session)
    body = client.get(f"/v1/admin/campaigns/{campaign.id}", headers=AUTH).json()
    assert {d["domain"]: d["excluded"] for d in body["domains"]} == {"a.example": None, "b.example": None, "google.com": "allowlisted"}
    assert {(s["kind"], s["strength"], s["domain_count"]) for s in body["shared"]} == {
        ("phone", "strong", 3), ("ip", "strong", 3), ("registrar", "weak", 3),
    }
    assert sum(place["domains"] for place in body["locations"]) == 3
    assert set(body["locations"][0]) == {"hosted_in", "registered_through", "network_owner", "behind_proxy", "domains"}


def test_graph_shape(client, session):
    campaign = make_campaign(session)
    body = client.get(f"/v1/admin/campaigns/{campaign.id}/graph", headers=AUTH).json()
    nodes = {n["data"]["id"]: n["data"] for n in body["nodes"]}
    assert sorted(n["kind"] for n in nodes.values()) == ["domain"] * 3 + ["ip", "phone", "registrar"]
    assert {e["data"]["strength"] for e in body["edges"]} == {"strong", "weak"}
    for edge in body["edges"]:
        assert set(edge["data"]) == {"id", "source", "target", "strength"}
        assert nodes[edge["data"]["source"]]["kind"] == "domain" and edge["data"]["target"] in nodes


def test_unknown_campaign_is_404(client):
    assert client.get("/v1/admin/campaigns/cmp_missing", headers=AUTH).status_code == 404


def test_confirm_all_writes_one_review_per_domain_and_skips_protected(client, session):
    campaign = make_campaign(session)
    body = {"domains": ["a.example", "b.example", "google.com", "elsewhere.example"], "reviewer": "Sara"}
    response = client.post(f"/v1/admin/campaigns/{campaign.id}/confirm", json=body, headers=AUTH)
    assert response.json() == {
        "confirmed": ["a.example", "b.example"],
        "skipped": [{"domain": "google.com", "reason": "allowlisted"}, {"domain": "elsewhere.example", "reason": "not_in_campaign"}],
    }
    assert sorted(r.domain for r in session.scalars(select(Review))) == ["a.example", "b.example"]
    again = client.post(f"/v1/admin/campaigns/{campaign.id}/confirm", json={"domains": ["a.example"], "reviewer": "Sara"}, headers=AUTH)
    assert again.json()["skipped"] == [{"domain": "a.example", "reason": "already_confirmed"}]
