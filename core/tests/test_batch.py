def test_unknown_url_gets_a_definite_verdict_after_the_budget(client):
    urls = ["https://uaepass.ae/login", "https://uaepass-verify.example/login", "https://unknown-site.example/"]
    response = client.post("/v1/batch", json={"urls": urls})
    assert response.status_code == 200
    body = response.json()
    assert body["cutoff"] == 70
    by_url = {row["url"]: row for row in body["results"]}
    assert {row["verdict"] for row in body["results"]} == {"allow", "block"}
    assert by_url[urls[1]]["verdict"] == "block"
    assert by_url[urls[2]]["verdict"] == "allow"
    assert by_url[urls[2]]["timed_out"] is True
    assert by_url[urls[0]]["timed_out"] is False


def test_batch_csv_has_the_same_rows(client):
    response = client.post("/v1/batch?format=csv", json={"urls": ["https://uaepass-verify.example/login"]})
    assert response.headers["content-type"].startswith("text/csv")
    header, row = response.text.strip().splitlines()
    assert header == "url,check_id,verdict,score,timed_out"
    assert row.startswith("https://uaepass-verify.example/login,c_")
    assert row.endswith(",block,100,False")
