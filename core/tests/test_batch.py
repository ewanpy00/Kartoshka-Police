def test_batch_returns_definite_verdicts_from_the_fast_score(client, enqueued, settings):
    urls = [
        "https://uaepass.ae/login",
        "https://uaepass-verify.example/login",
        "https://unknown-site.example/",
        "https://uaepass-verify.top/login",
    ]
    response = client.post("/v1/batch", json={"urls": urls})
    assert response.status_code == 200
    body = response.json()
    assert body["cutoff"] == settings.batch_cutoff
    by_url = {row["url"]: row for row in body["results"]}
    assert {row["verdict"] for row in body["results"]} == {"allow", "block"}
    assert by_url[urls[0]]["verdict"] == "allow"
    assert by_url[urls[1]]["verdict"] == "block"
    assert by_url[urls[2]]["verdict"] == "allow"
    assert by_url[urls[3]]["verdict"] == "block"
    assert "reasons" not in by_url[urls[3]]
    assert enqueued == []


def test_batch_explain_adds_band_and_reasons(client):
    body = client.post("/v1/batch?explain=true", json={"urls": ["https://uaepass-verify.top/login"]}).json()
    row = body["results"][0]
    assert row["band"] == "block"
    assert row["brand"] == "UAE PASS"
    assert "BRAND_IN_DOMAIN" in [r["code"] for r in row["reasons"]]


def test_batch_csv_has_the_same_rows(client):
    response = client.post("/v1/batch?format=csv", json={"urls": ["https://uaepass-verify.example/login"]})
    assert response.headers["content-type"].startswith("text/csv")
    header, row = response.text.strip().splitlines()
    assert header == "url,check_id,verdict,score,timed_out"
    assert row.startswith("https://uaepass-verify.example/login,c_")
    assert row.endswith(",block,100,false")


def test_batch_csv_defuses_formula_cells(client, monkeypatch):
    """Validation only lets http(s) URLs in, so no URL cell can start with a formula character; the writer is
    exercised through the endpoint with a check id (the other free-text cell) that does."""
    import csv
    import io
    from types import SimpleNamespace

    from app.api import check as check_module

    async def fake_run_check(session, url, *args, **kwargs):
        return SimpleNamespace(id="=1+1", score=50, sources=[], verdict="block", brand=None, reasons=[])

    monkeypatch.setattr(check_module, "run_check", fake_run_check)
    response = client.post("/v1/batch?format=csv", json={"urls": ["https://a.example/"]})
    assert response.status_code == 200
    header, row = list(csv.reader(io.StringIO(response.text)))
    assert row[1] == "'=1+1"
    assert not any(cell.startswith(("=", "+", "-", "@")) for cell in row)


def test_batch_csv_cells_use_csvsafe_for_every_prefix():
    from app.csvsafe import cell

    assert [cell(v) for v in ("=a", "+a", "-a", "@a")] == ["'=a", "'+a", "'-a", "'@a"]
