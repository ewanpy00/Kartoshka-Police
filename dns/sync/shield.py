"""DNS Shield sync (ARCHITECTURE.md section 4): core's confirmed blocklist into AdGuard Home, every minute.

- First run: if AdGuard Home has not been set up, configures it through its install API (admin user from
  ADGUARD_USER / ADGUARD_PASSWORD, web UI on 3000, DNS on 53 inside the container).
- Every minute: `GET /v1/blocklist?since=` (only confirmed domains; DNS cannot show warnings), then
  rewrites this service's own section of AdGuard's user rules (`||domain^`, between two marker lines).
  Rules an admin added outside the section are kept.
- Block counters: the per-domain deltas of AdGuard's "top blocked domains" go to `POST /v1/hits`
  (channel dns). Only domains and counts leave the resolver, never a client address.

    python shield.py            # loop forever
    python shield.py --once     # one sync, for checks
"""
import logging
import os
import sys
import time

import httpx

log = logging.getLogger("dnssync")
START, END = "! kartoshka-police:start", "! kartoshka-police:end"
EVERY_S = int(os.environ.get("DNS_SYNC_EVERY_S", "60"))


class Shield:
    def __init__(self, core: httpx.Client, adguard: httpx.Client, user: str, password: str) -> None:
        self.core, self.adguard = core, adguard
        self.user, self.password = user, password
        self.blocked: set[str] = set()
        self.since: str | None = None
        self.seen_counts: dict[str, int] = {}
        self.written: list[str] | None = None

    # --- AdGuard setup -------------------------------------------------------------------------------
    def ensure_setup(self) -> bool:
        """True when AdGuard is ready. Configures a fresh instance; never touches a configured one."""
        try:
            probe = self.adguard.get("/control/install/get_addresses")
        except httpx.HTTPError as error:
            log.warning("adguard unreachable: %s", error)
            return False
        if probe.status_code != 200:
            return True  # already configured: the install API is gone
        if not self.password:
            log.error("AdGuard Home is not set up and ADGUARD_PASSWORD is empty")
            return False
        response = self.adguard.post("/control/install/configure", json={
            "web": {"ip": "0.0.0.0", "port": 3000}, "dns": {"ip": "0.0.0.0", "port": 53},
            "username": self.user, "password": self.password,
        })
        response.raise_for_status()
        log.info("configured AdGuard Home (admin user %s)", self.user)
        return True

    # --- rules ---------------------------------------------------------------------------------------
    def pull(self) -> bool:
        """Apply core's changes since the last pull. True when the set changed."""
        params = {"since": self.since} if self.since else {}
        response = self.core.get("/v1/blocklist", params=params)
        response.raise_for_status()
        body = response.json()
        before = set(self.blocked)
        self.blocked |= {d["domain"] for d in body["domains"]}
        self.blocked -= {d["domain"] for d in body["removed"]}
        stamps = [d["updated_at"] for d in body["domains"] + body["removed"]]
        if stamps:
            self.since = max(stamps + ([self.since] if self.since else []))
        return self.blocked != before or self.written is None

    def merged_rules(self, current: list[str]) -> list[str]:
        """The admin's own rules, then this service's section."""
        own, inside = [], False
        for rule in current:
            if rule == START:
                inside = True
            elif rule == END:
                inside = False
            elif not inside:
                own.append(rule)
        while own and not own[-1].strip():
            own.pop()
        return own + [START, *[f"||{domain}^" for domain in sorted(self.blocked)], END]

    def push_rules(self) -> int:
        status = self.adguard.get("/control/filtering/status", auth=(self.user, self.password))
        status.raise_for_status()
        rules = self.merged_rules(status.json().get("user_rules") or [])
        response = self.adguard.post("/control/filtering/set_rules", json={"rules": rules}, auth=(self.user, self.password))
        response.raise_for_status()
        self.written = rules
        return len(self.blocked)

    # --- block counters ------------------------------------------------------------------------------
    def ours(self, host: str) -> str | None:
        labels = host.lower().rstrip(".").split(".")
        for i in range(len(labels) - 1):
            candidate = ".".join(labels[i:])
            if candidate in self.blocked:
                return candidate
        return None

    def hit_deltas(self, top_blocked: list[dict]) -> dict[str, int]:
        deltas: dict[str, int] = {}
        current: dict[str, int] = {}
        for item in top_blocked:
            for host, count in item.items():
                current[host] = count
                domain = self.ours(host)
                if domain is None:
                    continue
                previous = self.seen_counts.get(host, 0)
                delta = count - previous if count >= previous else count  # the stats window rolled over
                if delta > 0:
                    deltas[domain] = deltas.get(domain, 0) + delta
        self.seen_counts = current
        return deltas

    def push_hits(self) -> dict[str, int]:
        stats = self.adguard.get("/control/stats", auth=(self.user, self.password))
        stats.raise_for_status()
        deltas = self.hit_deltas(stats.json().get("top_blocked_domains") or [])
        if deltas:
            self.core.post("/v1/hits", json={"channel": "dns", "counts": deltas}).raise_for_status()
        return deltas

    def once(self) -> dict:
        if not self.ensure_setup():
            return {"ready": False}
        changed = self.pull()
        written = self.push_rules() if changed else None
        hits = self.push_hits()
        return {"ready": True, "rules": written, "hits": hits}


def build() -> Shield:
    token = os.environ.get("CORE_WRITE_TOKEN", "")
    core = httpx.Client(base_url=os.environ.get("CORE_URL", "http://core:8000"), timeout=30,
                        headers={"Authorization": f"Bearer {token}"})
    adguard = httpx.Client(base_url=os.environ.get("ADGUARD_URL", "http://adguard:3000"), timeout=30)
    return Shield(core, adguard, os.environ.get("ADGUARD_USER", "admin"), os.environ.get("ADGUARD_PASSWORD", ""))


def main(argv: list[str]) -> int:
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    shield = build()
    while True:
        try:
            result = shield.once()
            if result.get("rules") is not None or result.get("hits"):
                log.info("sync: %s domains in rules, hits %s", result.get("rules"), result.get("hits"))
        except Exception as error:
            log.warning("sync failed: %s", error)
            result = {}
        if "--once" in argv:
            return 0 if result.get("ready") else 1
        time.sleep(EVERY_S)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
