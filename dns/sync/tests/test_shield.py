import httpx

from shield import END, START, Shield


class FakeAdGuard:
    def __init__(self, configured=True):
        self.configured = configured
        self.rules = ["||ads.example^", START, "||old-scam.top^", END]
        self.top_blocked = []
        self.install = None

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/control/install/get_addresses":
            return httpx.Response(200 if not self.configured else 404, json={})
        if path == "/control/install/configure":
            self.install = request.read()
            self.configured = True
            return httpx.Response(200)
        if path == "/control/filtering/status":
            return httpx.Response(200, json={"user_rules": self.rules})
        if path == "/control/filtering/set_rules":
            import json
            self.rules = json.loads(request.read())["rules"]
            return httpx.Response(200)
        if path == "/control/stats":
            return httpx.Response(200, json={"top_blocked_domains": self.top_blocked})
        return httpx.Response(404)


class FakeCore:
    def __init__(self):
        self.domains = [{"domain": "tamm-pay.top", "brand_id": "tamm", "updated_at": "2026-11-24T10:00:00Z"}]
        self.removed = []
        self.hits = []
        self.queries = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/blocklist":
            self.queries.append(dict(request.url.params))
            body = {"domains": self.domains, "removed": self.removed, "version": 1, "generated_at": "x"}
            self.domains, self.removed = [], []
            return httpx.Response(200, json=body)
        if request.url.path == "/v1/hits":
            import json
            self.hits.append(json.loads(request.read()))
            return httpx.Response(200, json={})
        return httpx.Response(404)


def shield(adguard: FakeAdGuard, core: FakeCore) -> Shield:
    return Shield(httpx.Client(base_url="http://core", transport=httpx.MockTransport(core.handler)),
                  httpx.Client(base_url="http://adguard", transport=httpx.MockTransport(adguard.handler)), "admin", "pw")


def test_sync_rewrites_only_its_own_section_and_follows_removals():
    adguard, core = FakeAdGuard(), FakeCore()
    s = shield(adguard, core)
    assert s.once()["rules"] == 1
    assert adguard.rules == ["||ads.example^", START, "||tamm-pay.top^", END]
    core.domains = [{"domain": "rta-fines.top", "brand_id": "rta", "updated_at": "2026-11-24T11:00:00Z"}]
    core.removed = [{"domain": "tamm-pay.top", "brand_id": "tamm", "updated_at": "2026-11-24T11:05:00Z"}]
    s.once()
    assert adguard.rules == ["||ads.example^", START, "||rta-fines.top^", END]
    assert core.queries[-1] == {"since": "2026-11-24T10:00:00Z"}
    assert s.once()["rules"] is None  # nothing changed: no rewrite


def test_fresh_adguard_is_configured_once():
    adguard, core = FakeAdGuard(configured=False), FakeCore()
    s = shield(adguard, core)
    assert s.once()["ready"] and adguard.install is not None
    adguard.install = None
    s.once()
    assert adguard.install is None


def test_hits_are_sent_as_deltas_for_our_domains_only():
    adguard, core = FakeAdGuard(), FakeCore()
    s = shield(adguard, core)
    adguard.top_blocked = [{"www.tamm-pay.top": 3}, {"ads.example": 50}]
    s.once()
    adguard.top_blocked = [{"www.tamm-pay.top": 5}, {"tamm-pay.top": 1}]
    s.once()
    assert core.hits == [{"channel": "dns", "counts": {"tamm-pay.top": 3}}, {"channel": "dns", "counts": {"tamm-pay.top": 3}}]
