import csv
import io

from admin_factories import AUTH, add_check, add_evidence


def scam_record(session, domain, brand, phones=(), whatsapp=()):
    evidence = add_evidence(session, add_check(session, domain), brand=brand)
    evidence.payload = {**evidence.payload, "scam": {"brand": brand, "phones": list(phones), "whatsapp": list(whatsapp), "payment_hosts": []}}
    session.flush()
    return evidence


def numbers(client):
    response = client.get("/v1/admin/helplines", headers=AUTH)
    assert response.status_code == 200
    return response.json()["numbers"]


def test_empty_list_when_nothing_qualifies(client):
    assert numbers(client) == []


def test_lists_fake_numbers_and_excludes_official_branless_and_official_hosts(client, session):
    first = scam_record(session, "uaepass-fake.example", "UAE PASS", phones=["+971501234567", "+971600561111"])
    scam_record(session, "uaepass-fake.example", "UAE PASS", whatsapp=["+971501234567"])
    scam_record(session, "no-brand.example", None, phones=["+971509999999"])
    scam_record(session, "uaepass.ae", "UAE PASS", phones=["+971508888888"])
    rows = numbers(client)
    assert len(rows) == 1
    assert rows[0] | {"first_seen": None} == {
        "phone": "+971501234567", "brand": "UAE PASS", "source": "page",
        "domain": "uaepass-fake.example", "evidence_id": first.id, "first_seen": None,
    }


def test_csv_is_an_attachment_with_formula_safe_cells(client, session):
    scam_record(session, "=HYPERLINK(1).example", "TAMM", phones=["+971501234567"])
    response = client.get("/v1/admin/helplines.csv", headers=AUTH)
    assert "attachment" in response.headers["content-disposition"]
    rows = list(csv.reader(io.StringIO(response.text)))
    assert rows[0] == ["phone", "brand", "source", "domain", "evidence_id", "first_seen"]
    assert rows[1][0] == "'+971501234567" and rows[1][3] == "'=HYPERLINK(1).example"
