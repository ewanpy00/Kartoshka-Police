# DNS (stretch)

AdGuard Home is a stretch item. It does not start with `make up`; start it with:

    make up-stretch

- First-run setup wizard: http://127.0.0.1:3001 (localhost-only, never exposed to the LAN).
- DNS listens on host port 5335, bound to `BIND_ADDR` (127.0.0.1 by default).

No config is committed. AdGuard rewrites its config file at runtime, so `dns/conf/` is a local, git-ignored working directory.
