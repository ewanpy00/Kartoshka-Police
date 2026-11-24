from app.checks import host_and_parents
from app.models import Domain


def check(client, url, **extra):
    response = client.post("/v1/check", json={"url": url, **extra})
    assert response.status_code == 200
    return response.json()


def test_healthz(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "ok", "redis": "ok"}


def test_allowlisted_url_is_allowed(client):
    body = check(client, "https://google.com/search")
    assert body["verdict"] == "allow"
    assert body["score"] == 0
    assert body["safe_action"] is None
    assert [reason["code"] for reason in body["reasons"]] == ["ALLOWLISTED"]


def test_subdomain_of_official_domain_is_allowed(client):
    body = check(client, "https://login.id.uaepass.ae/")
    assert body["verdict"] == "allow"
    assert body["reasons"][0]["code"] == "ALLOWLISTED"


def test_blocklisted_url_is_blocked_with_safe_action(client):
    body = check(client, "https://uaepass-verify.example/login")
    assert body["verdict"] == "block"
    assert body["score"] == 100
    assert body["brand"] == "UAE PASS"
    assert body["safe_action"]["url"] == "https://uaepass.ae"
    assert body["reasons"][0]["code"] == "BLOCKLISTED"


def test_blocklisted_tamm_fines_url_gets_the_keyword_matched_service(client):
    body = check(client, "https://tamm-fines-pay.example/pay-fines")
    assert body["brand"] == "TAMM"
    assert body["safe_action"]["url"] == "https://www.tamm.abudhabi/wb/adp/pay-traffic-fines"


def test_blocklisted_url_without_keywords_falls_back_to_homepage(client, session):
    session.add(Domain(domain="plain-clone.example", status="confirmed", brand_id="tamm"))
    body = check(client, "https://plain-clone.example/")
    assert body["safe_action"] == {
        "label_en": "Go to the official TAMM website",
        "label_ar": "الانتقال إلى الموقع الرسمي",
        "url": "https://tamm.abudhabi",
    }


def test_unknown_url_is_pending_and_deep_mode_enqueues(client, enqueued):
    fast = check(client, "https://unknown-site.example/")
    assert fast["verdict"] == "pending"
    assert fast["reasons"] == []
    assert enqueued == []
    deep = check(client, "https://unknown-site.example/", mode="deep")
    assert enqueued == [deep["check_id"]]


def test_verdict_has_every_field(client):
    body = check(client, "https://unknown-site.example/")
    assert set(body) == {
        "check_id", "url", "final_url", "verdict", "score", "stage", "brand",
        "safe_action", "reasons", "campaign_id", "evidence_id",
    }
    assert body["check_id"].startswith("c_")


def test_get_check_by_id_returns_the_same_verdict(client):
    created = check(client, "https://uaepass-verify.example/login")
    response = client.get(f"/v1/check/{created['check_id']}")
    assert response.status_code == 200
    assert response.json() == created


def test_get_unknown_check_is_404(client):
    assert client.get("/v1/check/c_missing").status_code == 404


def test_blocklist_lists_confirmed_domains(client):
    domains = {entry["domain"] for entry in client.get("/v1/blocklist").json()["domains"]}
    assert "uaepass-verify.example" in domains
    assert "google.com" not in domains


def test_backslash_url_is_not_allowed_through_the_official_domain(client):
    url = "https://evil.example\\@uaepass.ae/"
    assert host_and_parents(url) == ["evil.example"]
    assert check(client, url)["verdict"] == "pending"


def test_host_case_and_trailing_dot_are_normalised(client):
    assert check(client, "https://UAEPASS.ae./login")["verdict"] == "allow"
    assert check(client, "https://uaepass-verify.example./login")["verdict"] == "block"


def test_idna_host_is_punycode_encoded():
    assert host_and_parents("https://bücher.example/") == ["xn--bcher-kva.example"]


def test_idna2003_lookalikes_do_not_match_the_allowlist(client):
    assert host_and_parents("https://uaepaß.ae/") == ["xn--uaepa-pqa.ae"]
    assert check(client, "https://uaepaß.ae/login")["verdict"] == "pending"
    assert check(client, "https://uae\u200dpass.ae/login")["verdict"] == "pending"


def test_one_odd_label_does_not_stop_the_parent_domains_matching(client, session):
    session.add(Domain(domain="xn--bcher-kva.example", status="confirmed", brand_id="tamm"))
    assert check(client, "https://foo_bar.bücher.example/")["verdict"] == "block"
    assert check(client, "https://foo_bar.uaepass.ae/")["verdict"] == "allow"
