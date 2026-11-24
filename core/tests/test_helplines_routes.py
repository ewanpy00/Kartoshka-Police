"""Fake helplines: numbers from each case's representative evidence, confirmed ones as a CSV."""
import csv
import io
from datetime import UTC, datetime, timedelta

from admin_factories import AUTH, add_check, add_evidence
from app import brands
from app.models import Domain


def scam_record(session, domain, brand, phones=(), whatsapp=(), score=80, source="api", created_at=None):
    check = add_check(session, domain, score=score, source=source, created_at=created_at, brand=brand)
    return add_evidence(session, check, brand=brand, phones=phones, whatsapp=whatsapp)


def numbers(client):
    response = client.get("/v1/admin/helplines", headers=AUTH)
    assert response.status_code == 200
    return response.json()["numbers"]


def csv_rows(client):
    return list(csv.reader(io.StringIO(client.get("/v1/admin/helplines.csv", headers=AUTH).text)))[1:]


def test_lists_fake_numbers_and_excludes_official_branless_and_official_hosts(client, session, monkeypatch):
    monkeypatch.setattr(brands, "official_phones", lambda: frozenset({"+971600561111"}), raising=False)
    first = scam_record(session, "uaepass-fake.example", "UAE PASS", phones=["+971501234567", "+971600561111"])
    scam_record(session, "uaepass-fake.example", "UAE PASS", whatsapp=["+971501234567"])
    scam_record(session, "no-brand.example", None, phones=["+971509999999"])
    scam_record(session, "uaepass.ae", "UAE PASS", phones=["+971508888888"])
    rows = [n for n in numbers(client) if n["domain"].endswith(".example")]
    assert len(rows) == 1
    assert rows[0] | {"first_seen": None} == {
        "phone": "+971501234567", "brand": "UAE PASS", "source": "page",
        "domain": "uaepass-fake.example", "evidence_id": first.id, "first_seen": None, "confirmed": False,
    }


def test_numbers_come_from_the_representative_evidence_only(client, session):
    now = datetime.now(UTC)
    scam_record(session, "uaepass-rep.example", "UAE PASS", phones=["+971501111111"], score=95, created_at=now - timedelta(days=1))
    scam_record(session, "uaepass-rep.example", "UAE PASS", phones=["+971502222222"], score=60, created_at=now)
    assert [n["phone"] for n in numbers(client) if n["domain"] == "uaepass-rep.example"] == ["+971501111111"]


def test_csv_is_an_attachment_with_formula_safe_cells(client, session):
    scam_record(session, "=HYPERLINK(1).example", "TAMM", phones=["+971501234567"])
    session.add(Domain(domain="=HYPERLINK(1).example", status="confirmed", source="officer", confirmed_by="officer"))
    session.flush()
    response = client.get("/v1/admin/helplines.csv", headers=AUTH)
    assert "attachment" in response.headers["content-disposition"]
    rows = list(csv.reader(io.StringIO(response.text)))
    assert rows[0] == ["phone", "brand", "source", "domain", "evidence_id", "first_seen"]
    mine = next(row for row in rows[1:] if row[3].endswith("HYPERLINK(1).example"))
    assert mine[0] == "'+971501234567" and mine[3] == "'=HYPERLINK(1).example"


def test_csv_exports_only_officer_confirmed_domains(client, session):
    scam_record(session, "uaepass-csv.example", "UAE PASS", phones=["+971501234567"])

    def ours(rows):
        return [r for r in rows if r[3] == "uaepass-csv.example"]

    assert [n["confirmed"] for n in numbers(client) if n["domain"] == "uaepass-csv.example"] == [False]
    assert ours(csv_rows(client)) == []
    session.add(Domain(domain="uaepass-csv.example", status="confirmed", source="officer", confirmed_by="officer"))
    session.flush()
    assert [n["confirmed"] for n in numbers(client) if n["domain"] == "uaepass-csv.example"] == [True]
    assert len(ours(csv_rows(client))) == 1


def test_auto_confirmed_domain_number_is_not_exported(client, session):
    scam_record(session, "uaepass-auto.example", "UAE PASS", phones=["+971501234567"])
    session.add(Domain(domain="uaepass-auto.example", status="confirmed", source="auto", confirmed_by="auto"))
    session.flush()
    assert [n["confirmed"] for n in numbers(client) if n["domain"] == "uaepass-auto.example"] == [False]
    assert [r for r in csv_rows(client) if r[3] == "uaepass-auto.example"] == []


def test_domain_cleared_by_an_officer_rerun_contributes_no_numbers(client, session):
    earlier = datetime.now(UTC) - timedelta(hours=1)
    scam_record(session, "tammaverick.example", "TAMM", phones=["+971501234567"], created_at=earlier)
    assert [n for n in numbers(client) if n["domain"] == "tammaverick.example"]
    scam_record(session, "tammaverick.example", "TAMM", phones=["+971501234567"], score=5, source="officer")
    assert [n for n in numbers(client) if n["domain"] == "tammaverick.example"] == []


def test_warn_band_representative_is_listed(client, session):
    scam_record(session, "uaepass-warn.example", "UAE PASS", phones=["+971501234567"], score=50)
    assert "uaepass-warn.example" in [n["domain"] for n in numbers(client)]
