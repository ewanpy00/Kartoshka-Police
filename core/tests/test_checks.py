from app.models import Domain
from app.normalize.url import host_and_parents


def check(client, url, **extra):
    response = client.post("/v1/check", json={"url": url, **extra})
    assert response.status_code == 200, response.text
    return response.json()


def codes(body):
    return [reason["code"] for reason in body["reasons"]]


def test_healthz(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "ok", "redis": "ok"}


def test_allowlisted_url_is_allowed(client):
    body = check(client, "https://google.com/search")
    assert body["verdict"] == "allow"
    assert body["score"] == 0
    assert body["safe_action"] is None
    assert codes(body) == ["ALLOWLISTED"]


def test_tranco_site_is_allowed(client):
    assert check(client, "https://www.github.com/")["verdict"] == "allow"


def test_gov_ae_subdomain_is_official(client):
    body = check(client, "https://services.mohre.gov.ae/login")
    assert body["verdict"] == "allow"


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
    assert {s["id"]: s["status"] for s in body["sources"]}["police_blocklist"] == "hit"


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


def test_brand_lookalike_on_risky_tld_is_blocked_and_queues_deep(client, enqueued):
    body = check(client, "https://uaepass-verify.top/login")
    assert body["verdict"] == "block"
    assert body["score"] > 70
    assert body["brand"] == "UAE PASS"
    assert body["safe_action"]["url"] == "https://uaepass.ae"
    assert {"BRAND_IN_DOMAIN", "ACTION_WORDS", "BRAND_ACTION", "RISKY_TLD"} <= set(codes(body))
    assert body["deep_status"] == "queued"
    assert enqueued == [body["check_id"]]
    sources = {s["id"]: s for s in body["sources"]}
    assert sources["sandbox"] == {"id": "sandbox", "status": "unknown", "detail": "running"}


def test_fines_lookalike_gets_the_tamm_fines_button(client):
    body = check(client, "https://tamm-fines-pay.top/")
    assert body["brand"] == "TAMM"
    assert body["safe_action"]["url"] == "https://www.tamm.abudhabi/wb/adp/pay-traffic-fines"


def test_reasons_are_bilingual(client):
    body = check(client, "https://uaepass-verify.top/login")
    for item in body["reasons"]:
        assert item["en"] and item["ar"]
        assert any("؀" <= ch <= "ۿ" for ch in item["ar"])


def test_unknown_plain_url_is_allowed_without_deep(client, enqueued):
    body = check(client, "https://my-bakery-shop.example/")
    assert body["verdict"] == "allow"
    assert body["deep_status"] is None
    assert enqueued == []


def test_deep_mode_enqueues_even_a_low_score(client, enqueued):
    body = check(client, "https://my-bakery-shop.example/", mode="deep")
    assert enqueued == [body["check_id"]]


def test_sources_cover_every_layer_in_order(client, settings):
    settings.google_safe_browsing_api_key = settings.virustotal_api_key = None  # the container env may hold real keys
    body = check(client, "https://uaepass-verify.top/login")
    assert [s["id"] for s in body["sources"]] == [
        "allowlist", "police_blocklist", "gsb", "virustotal", "feeds", "rdap", "ct", "campaign", "sandbox", "ai",
    ]
    statuses = {s["id"]: s["status"] for s in body["sources"]}
    assert statuses["gsb"] == "skipped" and statuses["virustotal"] == "skipped"


def test_young_domain_adds_an_age_reason(client, offline):
    offline["young-uaepass.top"] = {"found": True, "registered": "2099-01-01T00:00:00Z"}
    body = check(client, "https://young-uaepass.top/")
    assert "DOMAIN_AGE" in codes(body)


def test_resident_view_hides_weights(client):
    body = check(client, "https://uaepass-verify.top/login", source="gatekeeper")
    assert all(item["weight"] is None for item in body["reasons"])
    assert body["score"] > 70


def test_bare_host_is_accepted(client):
    assert check(client, "uaepass-verify.top")["verdict"] == "block"


def test_non_http_urls_are_rejected(client):
    for url in ("javascript:alert(1)", "ftp://example.com/x", "mailto:a@b.c", "http://localhost"):
        assert client.post("/v1/check", json={"url": url}).status_code == 422


def test_verdict_has_every_field(client):
    body = check(client, "https://unknown-site.example/")
    assert set(body) == {
        "check_id", "url", "final_url", "verdict", "score", "stage", "brand", "safe_action", "reasons",
        "sources", "preview", "deep_status", "campaign_id", "evidence_id",
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
    body = client.get("/v1/blocklist").json()
    domains = {entry["domain"] for entry in body["domains"]}
    assert "uaepass-verify.example" in domains
    assert "google.com" not in domains


def test_blocklist_txt_is_adblock_syntax(client):
    text = client.get("/v1/blocklist.txt").text
    assert "||uaepass-verify.example^" in text.splitlines()


def test_backslash_url_is_not_allowed_through_the_official_domain(client):
    url = "https://evil.example\\@uaepass.ae/"
    assert host_and_parents(url) == ["evil.example"]
    assert "ALLOWLISTED" not in codes(check(client, url))
    assert host_and_parents("https://evil.example\\path\\@uaepass.ae/") == ["evil.example"]


def test_host_case_and_trailing_dot_are_normalised(client):
    assert check(client, "https://UAEPASS.ae./login")["verdict"] == "allow"
    assert check(client, "https://uaepass-verify.example./login")["verdict"] == "block"


def test_idna_host_is_punycode_encoded():
    assert host_and_parents("https://bücher.example/") == ["xn--bcher-kva.example"]


def test_idna2003_lookalikes_do_not_match_the_allowlist(client):
    assert host_and_parents("https://uaepaß.ae/") == ["xn--uaepa-pqa.ae"]
    assert "ALLOWLISTED" not in codes(check(client, "https://uaepaß.ae/login"))
    assert "ALLOWLISTED" not in codes(check(client, "https://uae‍pass.ae/login"))


def test_cyrillic_homoglyph_of_uaepass_is_flagged(client):
    body = check(client, "https://uаepass.com/login")
    assert "ALLOWLISTED" not in codes(body)
    assert body["verdict"] in ("warn", "block")


def test_one_odd_label_does_not_stop_the_parent_domains_matching(client, session):
    session.add(Domain(domain="xn--bcher-kva.example", status="confirmed", brand_id="tamm"))
    assert check(client, "https://foo_bar.bücher.example/")["verdict"] == "block"
    assert check(client, "https://foo_bar.uaepass.ae/")["verdict"] == "allow"


def test_allowlisted_domain_does_not_cover_its_subdomains(client):
    assert "ALLOWLISTED" not in codes(check(client, "https://sites.google.com/view/x"))
    assert check(client, "https://google.com/")["verdict"] == "allow"
    assert check(client, "https://www.google.com/")["verdict"] == "allow"
    assert check(client, "https://login.uaepass.ae/")["verdict"] == "allow"


def test_brand_page_on_free_hosting_is_flagged(client):
    body = check(client, "https://sites.google.com/view/uaepass-login")
    assert "FREE_HOSTING" in codes(body)
    assert body["verdict"] in ("warn", "block")


def test_subdomain_of_a_blocklisted_domain_is_blocked(client):
    assert check(client, "https://login.uaepass-verify.example/")["verdict"] == "block"


def test_confirmed_wins_over_an_allowlist_entry(client, session):
    session.add(Domain(domain="www.google.com", status="confirmed", brand_id="tamm"))
    assert check(client, "https://www.google.com/")["verdict"] == "block"


def test_officer_cleared_domain_is_allowed(client, session):
    session.add(Domain(domain="tamm-community.example", status="cleared", source="officer"))
    body = check(client, "https://tamm-community.example/")
    assert body["verdict"] == "allow"
    assert codes(body) == ["OFFICER_CLEARED"]


def test_block_from_gatekeeper_counts_a_hit(client, session):
    from app.models import Hit

    check(client, "https://uaepass-verify.example/login", source="gatekeeper")
    hit = session.get(Hit, ("uaepass-verify.example", "browser"))
    assert hit is not None and hit.count >= 1


def test_url_model_adds_weight_only_when_confident(client, monkeypatch):
    from app.ai import url_model

    monkeypatch.setattr(url_model, "predict", lambda features: 0.65)
    body = check(client, "https://my-bakery-shop.example/")
    assert "URL_MODEL" not in [r["code"] for r in body["reasons"]]

    monkeypatch.setattr(url_model, "predict", lambda features: 0.99)
    body = check(client, "https://another-bakery.example/")
    model = next(r for r in body["reasons"] if r["code"] == "URL_MODEL")
    assert model["weight"] == 39
    assert "99" in model["en"]


def test_a_blocklist_hit_shows_the_preview_of_the_last_deep_analysis(client, session):
    from factories import make_check, with_evidence

    old = make_check(session, "shown-before.example", 95, deep_status="done",
                     preview={"screenshot": "/v1/preview/ev_x.png", "asks_for": ["card"], "title": "Pay"})
    old.stage = "deep"
    evidence_id = with_evidence(session, old)
    session.add(Domain(domain="shown-before.example", status="confirmed", brand_id="tamm"))
    session.flush()
    body = check(client, "https://shown-before.example/pay", source="resident")
    assert body["reasons"][0]["code"] == "BLOCKLISTED" and body["verdict"] == "block"
    assert body["preview"]["asks_for"] == ["card"] and body["evidence_id"] == evidence_id


def test_host_parsing_trailing_dot_case_and_per_label_punycode():
    assert host_and_parents("https://A.UAEPASS.ae./x") == ["a.uaepass.ae", "uaepass.ae"]
    assert host_and_parents("https://sub.bücher.例え.example/") == ["sub.xn--bcher-kva.xn--r8jz45g.example", "xn--bcher-kva.xn--r8jz45g.example",
                                                                 "xn--r8jz45g.example"]
    assert host_and_parents("uaepass.ae") == ["uaepass.ae"]  # a bare host is read as a host


def test_allowlisted_host_matches_only_itself_and_its_www_form(client):
    assert check(client, "https://google.com/")["verdict"] == "allow"
    assert check(client, "https://www.google.com/")["verdict"] == "allow"
    for url in ("https://accounts.google.com/", "https://google.com.evil.example/", "https://evilgoogle.com/"):
        assert "ALLOWLISTED" not in codes(check(client, url)), url


def test_official_and_confirmed_domains_match_their_parent_domains(client, session):
    assert codes(check(client, "https://a.b.c.uaepass.ae/"))[0] == "ALLOWLISTED"
    session.add(Domain(domain="scam-parent.example", status="confirmed", brand_id="tamm"))
    assert codes(check(client, "https://x.y.scam-parent.example/"))[0] == "BLOCKLISTED"
