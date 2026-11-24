def test_batch_returns_definite_verdicts_from_the_fast_score(client, enqueued):
    urls = [
        "https://uaepass.ae/login",
        "https://uaepass-verify.example/login",
        "https://unknown-site.example/",
        "https://uaepass-verify.top/login",
    ]
    response = client.post("/v1/batch", json={"urls": urls})
    assert response.status_code == 200
    body = response.json()
    assert body["cutoff"] == 40
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
