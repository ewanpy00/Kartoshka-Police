import pytest
from weasyprint.urls import URLFetcher

from app.evidence.export import ScreenshotOnlyFetcher, export_json, render_html, render_pdf
from app.models import Review
from evidence_helpers import add_record, make_payload, png_bytes

HOSTILE_TEXT = '<img src="http://169.254.169.254/latest/meta-data/"> <link rel="stylesheet" href="file:///etc/passwd">'


def hostile_record(session, tmp_path):
    (tmp_path / "shot.png").write_bytes(png_bytes())
    payload = make_payload(title="<script>alert(1)</script>", text=HOSTILE_TEXT)
    return add_record(session, "hostile", payload, "shot.png", captures_dir=tmp_path)


def test_hostile_page_renders_as_text_and_makes_no_outside_request(session, tmp_path, monkeypatch):
    evidence = hostile_record(session, tmp_path)
    html = render_html(session, evidence.id, None)
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "&lt;img src=&#34;http://169.254.169.254" in html
    assert "<script>" not in html and "<img src" not in html and "<link" not in html

    requests = []
    original = URLFetcher.fetch

    def spy(self, url, headers=None):
        requests.append(url)
        return original(self, url, headers)

    monkeypatch.setattr(URLFetcher, "fetch", spy)
    pdf = render_pdf(session, evidence.id, captures_dir=tmp_path)
    assert pdf.startswith(b"%PDF")
    assert requests and all(url.startswith("data:image/png;base64,") for url in requests)


def test_pdf_renders_without_a_screenshot(session):
    assert render_pdf(session, add_record(session, "plain").id).startswith(b"%PDF")


def test_domains_are_defanged_in_html(session):
    html = render_html(session, add_record(session, "plain").id, None)
    assert "tamm-pay[.]xyz" in html and "hxxps://tamm-pay[.]xyz/login" in html
    assert "<a " not in html


@pytest.mark.parametrize("url", ["http://169.254.169.254/", "https://example.com/a.css", "file:///etc/passwd", "ftp://host/x"])
def test_fetcher_refuses_everything_but_the_screenshot(url):
    with pytest.raises(ValueError):
        ScreenshotOnlyFetcher("data:image/png;base64,AAAA").fetch(url)


def test_fetcher_allows_only_its_own_data_uri():
    fetcher = ScreenshotOnlyFetcher("data:image/png;base64,AAAA")
    assert fetcher.fetch("data:image/png;base64,AAAA").content_type == "image/png"
    with pytest.raises(ValueError):
        fetcher.fetch("data:image/png;base64,BBBB")


def test_json_export_joins_reviews_outside_the_hash(session):
    evidence = add_record(session, "c0")
    session.add(Review(evidence_id=evidence.id, decision="confirm", reviewer="officer", reason=None))
    session.flush()
    exported = export_json(session, evidence.id)
    assert exported["hash"] == evidence.hash and exported["seq"] == evidence.seq
    assert [r["decision"] for r in exported["reviews"]] == ["confirm"]
    assert "reviews" not in exported["payload"]


def test_export_routes_need_the_token(client, session):
    evidence = add_record(session, "c0")
    for suffix in ("pdf", "json"):
        assert client.get(f"/v1/evidence/{evidence.id}.{suffix}").status_code == 401


def test_export_routes_with_token(client, session):
    evidence = add_record(session, "c0")
    headers = {"Authorization": "Bearer test-token"}
    pdf = client.get(f"/v1/evidence/{evidence.id}.pdf", headers=headers)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert pdf.headers["content-disposition"].startswith("attachment")
    assert client.get(f"/v1/evidence/{evidence.id}.json", headers=headers).json()["id"] == evidence.id
    for suffix in ("pdf", "json"):
        assert client.get(f"/v1/evidence/nope.{suffix}", headers=headers).status_code == 404
