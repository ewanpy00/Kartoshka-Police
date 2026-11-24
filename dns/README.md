# DNS Shield (stretch)

AdGuard Home plus a small sync service (`dns/sync/shield.py`). They do not start with `make up`; start them with:

    make up-stretch

- On first start, `dnssync` sets AdGuard Home up through its install API. The admin user is `ADGUARD_USER`, the password is `ADGUARD_PASSWORD` (generated into `.env` by `scripts/env.sh`).
- Every minute it pulls `GET /v1/blocklist?since=`. That feed holds only officer-confirmed domains, because DNS cannot show warnings. The domains go into its own section of AdGuard's user rules as `||domain^`, between the `! kartoshka-police:start` and `! kartoshka-police:end` lines. Rules you add outside that section are kept.
- Block counters go back to core as `POST /v1/hits` (channel `dns`): per-domain deltas of AdGuard's top blocked domains. Only domains and counts are sent, never a client address. They show as "Blocked N times" in My reports and on the console's Impact page.
- DNS listens on host port 5335, bound to `BIND_ADDR` (127.0.0.1 by default). Try it with `dig @127.0.0.1 -p 5335 <confirmed domain>`; the answer is `0.0.0.0`.
- Admin UI: http://127.0.0.1:3001, localhost only and never exposed to the LAN.
- For phones (Private DNS needs DoT on port 853 with a certificate) or a home router, point them at a resolver reachable on the LAN. That setup is outside this demo stack.

`dns/conf/` is AdGuard's runtime config: local and git-ignored, because AdGuard rewrites it while running.
