# Kartoshka-Police DevOps skeleton: plan

Status: built and verified on 2026-11-24, and merged into `main`. Progress notes are at the bottom of this file.

## Context

The repo holds only docs (ARCHITECTURE.md, FUTURE.md, IDEA.md, two brief PDFs) on `main`. Five people need to start building in parallel, and the hackathon submission is 08:00 tomorrow. This plan produces a one-command development stack (`make up`) on macOS Apple Silicon and Linux, with hot reload and interface-correct stubs, and no detection logic.

The docs define the routes, the verdict JSON, the table names and two brand entries. They define no ports, env var names, network names, table columns or `/capture` contract, so this plan fixes those. Where the brief and ARCHITECTURE.md disagree the brief wins: AdGuard sits behind a `stretch` profile, there is no `nrd.py`, and nothing ML-related is scaffolded. The layout is at the repo root, not under `kartoshka/`.

## How the work runs

The main session plans, coordinates, commits and verifies. Subagents write everything else. Sonnet does implementation and review, Haiku does scaffolding, and Opus is not used.

| Step | Who | What |
|---|---|---|
| 0 | main | Create branch `devops/skeleton` and commit this file. |
| 0 | F (Haiku) | Scaffolding files that B and D read. About a minute, so it runs before wave 1. |
| 1 | A, B, C, D, E (Sonnet, parallel) | One package each, disjoint files. |
| 2 | A (continued) | Merge any service-block deltas that B to E reported. |
| 3 | main | Run the verification list. Send each failure, with the exact error, to the owning agent or a fresh Sonnet agent. |
| 4 | reviewer (fresh Sonnet) | Gets this file and `git diff main...devops/skeleton`. Returns defects only, ranked, under 20 lines. Fixes go back to owners. |

Rules for every subagent brief:
- The brief is self-contained: goal, owned files, the fixed interfaces it needs, its acceptance check, what not to touch. It points at this file and the ARCHITECTURE.md line ranges instead of retyping them.
- Agents do not run git commands that change state. The main session commits once per package (`git add <owned paths>`), so five agents never contend for the index.
- Only A edits `docker-compose.yml` and the `Makefile`. Others report deltas from the service contract below, not whole blocks.
- Wave-1 acceptance checks use `docker build` and `docker run` with container and network names prefixed `kp-<package>-`, publish no host ports, and clean up afterwards. Nobody but A runs `docker compose`.
- Versions below were looked up on 2026-11-24. Agents confirm each tag by building, and read current docs for rq 3 and Playwright 1.65 rather than relying on memory.
- Reports are at most 15 lines: what was built, commands run and results, anything stubbed or unverified.
- A package stuck for 15 minutes is cut to a healthcheck-only stub. Package C gets 30 minutes and builds in two phases (see its details).

## Fixed interfaces

### Networks and exposure

| Network | Members | Type |
|---|---|---|
| `internal` | postgres, redis, core, worker, hunter, certstream, console, adguard | ordinary bridge (core, hunter and certstream need egress) |
| `sandbox_net` | worker, sandbox | ordinary bridge (sandbox needs egress) |

- Compose project name: `kartoshka-police`.
- Published host ports: core on `${BIND_ADDR}:${CORE_PORT}` (127.0.0.1:8000), console on `127.0.0.1:${CONSOLE_PORT}` (5173). Nothing else.
- `BIND_ADDR` defaults to `127.0.0.1` and applies to core and, in the stretch profile, AdGuard's DNS port. `0.0.0.0` is for the demo phone only, because it exposes them to the whole LAN. The console port and AdGuard's setup UI are never published beyond localhost.
- Postgres and redis are never published to the host. They stay on `internal` only. An unpublished port cannot be reached from the sandbox by any route; a published one can (see decision 2), so no service may gain a published port without that in mind.
- The sandbox gets no `env_file`, only explicit `environment` entries, so API keys and the write token never enter it.

### Services

| Service | Image or build | Internal port | Healthcheck | Notes |
|---|---|---|---|---|
| postgres | `postgres:16.16-alpine3.24` | 5432 | `pg_isready` | volume `pgdata` |
| redis | `redis:7.4.12-alpine3.22` | 6379 | `redis-cli ping` | no volume |
| core | build `./core` (`python:3.12.16-slim-trixie`) | 8000 | GET `/healthz` via python urllib | command: `alembic upgrade head && python -m app.seed && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`; depends on healthy postgres and redis |
| worker | same image as core | none | `python -m app.worker_health` (exit 0 when an RQ worker is registered) | `watchfiles` wrapping `rq worker $RQ_QUEUE --url $REDIS_URL`; depends on healthy core, redis, sandbox; on both networks |
| sandbox | build `./sandbox` (`mcr.microsoft.com/playwright/python:v1.65.2-noble`, pip `playwright==1.65.2`) | 8001 | GET `/healthz` via python urllib | hardening below |
| certstream | `0rickyy0/certstream-server-go:v1.10.1` | 8080 | `wget -qO- http://127.0.0.1:8080/example.json` | uses the config baked into the image, so no config file is committed |
| hunter | build `./hunter` (python 3.12 slim) | none | `python -m app.health` (exit 0 when `/tmp/hunter.heartbeat` is newer than 60 s) | `watchfiles` wrapping `python -m app.certstream_consumer`; depends on healthy certstream |
| console | build `./console` (`node:24.22.3-alpine3.24`) | 5173 | `wget -qO- http://127.0.0.1:5173/` | `npm run dev`; `node_modules` in an anonymous volume; gets `VITE_CORE_WRITE_TOKEN=${CORE_WRITE_TOKEN}` |
| adguard | `adguard/adguardhome:v0.107.80` | 53, 3000 | none | profile `stretch`; DNS on `${BIND_ADDR}:${ADGUARD_DNS_PORT}` (127.0.0.1:5335), setup UI on `127.0.0.1:${ADGUARD_UI_PORT}` (3001) |

Mounts: core and worker get `./core:/srv/core`, `./data:/srv/data:ro`, `./eval:/srv/eval:ro`, working dir `/srv/core`. Hunter gets `./hunter:/srv/hunter`, `./data:/srv/data:ro`. Sandbox gets `./sandbox:/srv/sandbox:ro` and the `captures` volume at `/captures`; the worker mounts `captures` read-only. Python containers run as a non-root user with `PYTHONDONTWRITEBYTECODE=1`.

Sandbox hardening: `user: pwuser`, `cap_drop: [ALL]`, `security_opt: [no-new-privileges:true]`, `read_only: true`, `tmpfs: /tmp` with `HOME=/tmp`, `shm_size: 256m`, `init: true`, `mem_limit: 1g`, `cpus: 1.0`, `pids_limit: 512`.

### Environment variables (`.env.example`)

| Variable | Default | Used by |
|---|---|---|
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | `kartoshka`, `kartoshka_dev`, `kartoshka` | postgres |
| `DATABASE_URL` | `postgresql+psycopg://kartoshka:kartoshka_dev@postgres:5432/kartoshka` | core, worker |
| `REDIS_URL` | `redis://redis:6379/0` | core, worker |
| `RQ_QUEUE` | `deep` | core, worker |
| `SANDBOX_URL` | `http://sandbox:8001` | worker |
| `CAPTURE_TIMEOUT_MS` | `15000` | sandbox |
| `CERTSTREAM_URL` | `ws://certstream:8080/` (lite stream) | hunter |
| `DATA_DIR` | `/srv/data` | core, worker, hunter |
| `CORE_WRITE_TOKEN` | empty in `.env.example`; `make up` generates one when it creates `.env` | core, console (as `VITE_CORE_WRITE_TOKEN`) |
| `BATCH_URL_BUDGET_MS` | `3000` | core |
| `BATCH_CUTOFF` | `70` (40 since app slice 1) | core |
| `BATCH_CONCURRENCY` | `20` | core |
| `BIND_ADDR`, `CORE_PORT` | `127.0.0.1`, `8000` | compose (core's published address) |
| `CONSOLE_PORT` | `5173` | compose (always bound to 127.0.0.1) |
| `ADGUARD_DNS_PORT`, `ADGUARD_UI_PORT` | `5335`, `3001` | compose (stretch) |
| `AI_PROVIDER`, `ANTHROPIC_API_KEY` | `anthropic`, empty | placeholder |
| `VIRUSTOTAL_API_KEY`, `GOOGLE_SAFE_BROWSING_API_KEY`, `SEARCH_API_KEY` | empty | placeholder |

### Core HTTP contract

- `GET /healthz`: 200 `{"status":"ok","db":"ok","redis":"ok"}`; 503 with `"error"` in the failing field.
- Routes: all eight in ARCHITECTURE.md lines 223-234. Where the doc gives no response shape, the stub returns the smallest obvious JSON and the report lists it. `/v1/evidence/{id}.pdf` returns 501.
- `POST /v1/check {url, source, mode}` returns the verdict JSON from lines 74-101 and stores a `checks` row so `GET /v1/check/{id}` works. Lookup is against the `domains` table, after normalising the host the way a browser does (backslashes as slashes, lower case, no trailing dot, UTS-46 punycode per label):
  - status `official` (brand domains), matching the host or any parent domain: `allow`, score 0, reason `ALLOWLISTED`, `safe_action` null.
  - status `allowlisted` (`data/allowlist.txt`), matching the exact host or its `www.` form only, because generic sites host user content on subdomains: `allow`, as above.
  - status `confirmed`, matching the host or any parent domain, and winning over an allow entry: `block`, score 100, reason `BLOCKLISTED`, brand set, `safe_action` from brands.yaml by the documented rule (service keyword in the URL, else the brand homepage with a generic label).
  - unknown: `pending`, score 0, no reasons. With `mode: deep` it also enqueues `app.jobs.deep_check(check_id)`.
- **How clients treat `pending`.** It means "no verdict yet", never "safe". Clients poll `GET /v1/check/{id}`. Gatekeeper handles `pending` like the timeout branch in ARCHITECTURE.md section 3 (line 143 onwards): forward if the local score is low, otherwise show "Checking link" briefly, then warn. This text is in the route's OpenAPI description and in `gatekeeper/README.md`.
- `POST /v1/batch {urls[]}` never returns `pending`. Response: `{"cutoff": 70, "results": [{"url", "check_id", "verdict": "allow"|"block", "score", "timed_out"}]}`; `?format=csv` returns the same rows as CSV. Each URL is checked; a pending one gets a deep job and is awaited for up to `BATCH_URL_BUDGET_MS`. The answer is then `block` if the score is at or above `BATCH_CUTOFF`, else `allow`, and `timed_out` is true when the budget ran out. URLs are processed concurrently, at most `BATCH_CONCURRENCY` at a time. Waiting and then answering `allow` is skeleton-only behaviour; slice 1 replaces it with the fast score.
- **Write token.** `POST /v1/review/{evidence_id}` requires `Authorization: Bearer $CORE_WRITE_TOKEN`, through one reusable dependency that every later blocklist-changing route uses. A missing or wrong token gets 401. An unset or empty `CORE_WRITE_TOKEN` rejects every write. `/v1/check`, `/v1/batch` and `/v1/report` stay open: they do not change the blocklist, and residents never sign in.
- Worker job `app.jobs.deep_check`: POSTs to `SANDBOX_URL/capture` and writes `internal_requests_blocked` and `navigation_blocked` to the check row. It writes `final_url` only when `navigation_blocked` is false, because a blocked navigation never reached that page. Nothing else.

### Sandbox HTTP contract

- `GET /healthz`: 200 `{"status":"ok"}`.
- `POST /capture {"url"}`: 200 `{"final_url", "title", "screenshot_path", "navigation_blocked", "internal_requests_blocked", "internal_hosts_blocked"}`. The path is under `/captures`. One browser per process, a fresh context per job.
  - 422: the URL is not http(s), or its host is internal.
  - 502: navigation failed for a reason other than the guard.
  - If the guard blocks the main navigation part-way (a redirect to an internal host), the response is 200 with `navigation_blocked` true, `final_url` set to the blocked URL, an empty `title` and a null `screenshot_path`. Callers must not treat `final_url` as a page that was reached when `navigation_blocked` is true.
- **Internal-address guard.** A host is internal if it is a single-label name (this covers every compose service name), ends in `.internal`, `.local` or `.localhost` (this covers `host.docker.internal` and `gateway.docker.internal`), or resolves to any address that is not globally routable. That last test covers loopback, private ranges, link-local including 169.254.169.254, CGNAT and IPv6 unique-local, and it catches a public name pointing at a private address.
- The guard applies to every browser request, not just the first: navigations, each redirect hop, scripts, images, fetch and XHR, and WebSocket handshakes. Service workers are blocked at the context. Every blocked request is aborted, logged at warning level with the job URL and the blocked URL, and counted.

### Console contract

- The console calls `/api/...`; Vite proxies `/api` to `CORE_PROXY_TARGET` (compose sets `http://core:8000`) and strips the prefix, so core needs no CORS config.
- One fetch wrapper adds `Authorization: Bearer` from `VITE_CORE_WRITE_TOKEN` in browser code. The Vite proxy must not inject the token, because that would make port 5173 an authenticated relay for anything that can reach it.

### Container layout and data files

- Working directories: core and worker `/srv/core`, sandbox `/srv/sandbox`, hunter `/srv/hunter`, console `/app`. Each Python service's code is a package named `app` under its working directory, with `tests/` beside it.
- `data/allowlist.txt`: one domain per line; `#` starts a comment; blank lines are ignored.
- `data/blocklist.txt`: `domain brand_id` per line, same comment rules. The brand id matches an `id` in `data/brands.yaml`.
- `data/eval/sample.csv`: header `url,label`; labels are `phish` or `benign`.

### Command contracts (what `scripts/*.sh` call)

| Target | Command |
|---|---|
| `make up` | if `.env` is missing, copy `.env.example` and fill `CORE_WRITE_TOKEN` with a random value; `docker compose up -d --build --wait` |
| `make up-stretch` | same with `--profile stretch` |
| `make down`, `make ps`, `make logs` | the matching `docker compose` command; `make logs s=core` filters |
| `make migrate` | `docker compose exec -T core alembic upgrade head` |
| `make seed` | `docker compose exec -T core python -m app.seed` |
| `make test` | `pytest -q` in core, sandbox (includes the hostile-page test) and hunter; `npm run build` in console |
| `make eval` | `docker compose exec -T -w /srv core python -m eval data/eval/sample.csv` |
| `make reset` | asks for a typed `yes`, then `docker compose --profile stretch down -v --remove-orphans` |

The Makefile must work on GNU Make 3.81, which is what macOS ships.

## Work packages

| Pkg | Model | Owns | Acceptance check |
|---|---|---|---|
| F | Haiku | `.gitignore`, `gatekeeper/README.md`, `data/brands.yaml` (two entries verbatim from ARCHITECTURE.md lines 240-271), `data/allowlist.txt`, `data/blocklist.txt` (`domain brand_id`, `.example` domains only), `data/refs/.gitkeep`, `data/eval/sample.csv` | brands.yaml parses; `.env` is ignored; the README states the pending rule |
| A | Sonnet | `docker-compose.yml`, `.env.example`, `Makefile`, `scripts/*.sh`, `dns/` (README, gitignored `conf/`) | `docker compose config -q` passes with and without the stretch profile; postgres, redis and certstream come up healthy; every make target resolves; a fresh `.env` gets a non-empty token; the sandbox service has no token or API key in its environment |
| B | Sonnet | `core/`, `eval/` | against throwaway postgres and redis: migration applies, `alembic check` is clean, seed is idempotent, pytest passes, `/healthz` and `/v1/check` answer for allowlisted, blocklisted and unknown URLs, `/v1/review` returns 401 without the token, `/v1/batch` returns no `pending` |
| C | Sonnet | `sandbox/` | under the full hardening flags via `docker run`: `/healthz` answers, `/capture` on `https://example.com` returns title and a screenshot file, guard unit tests and the hostile-page test pass |
| D | Sonnet | `hunter/` | against a throwaway certstream container: logs a stats line with a non-zero certificate count and the heartbeat file updates; matcher unit tests pass |
| E | Sonnet | `console/`, `README.md` | `npm ci` and `npm run build` pass in the node image; the dev server serves the page; README has "How to build and run" with prerequisites, the command, ports, tests and eval |

Package details that are not obvious from the table:

- **F.** `gatekeeper/README.md` says the Android app is not part of compose, how to point the demo phone at core (`BIND_ADDR=0.0.0.0`, demo-phone only), and how to treat `pending`, taken from ARCHITECTURE.md section 3 rather than reworded from this file.
- **B.**
  - Models and one hand-checked Alembic migration for all ten tables (`checks`, `domains`, `verdicts`, `evidence`, `artifacts`, `entities`, `edges`, `campaigns`, `watchlist`, `reviews`). Columns are undocumented, so B keeps them minimal and honours the doc's hints: `evidence` stores the previous row's hash, `artifacts` stores a SHA-256 and a path, `reviews` stores reviewer and time. `checks` has `internal_requests_blocked` and `navigation_blocked` columns.
  - `app.seed` upserts `domains` from brands.yaml official domains, allowlist.txt and blocklist.txt.
  - The write-token dependency compares in constant time. Tests cover a missing token, a wrong token, the right token and an unset variable.
  - `/v1/batch` as in the contract. A test submits an unknown URL with a short budget and asserts a definite verdict with `timed_out` true.
  - `eval` reads a `url,label` CSV, posts the URLs to `/v1/batch` and prints a confusion matrix with precision, recall and FPR.
  - Tests roll back so they leave no rows.
- **C.** Two phases, so the guard cannot hold up the stack.
  - Phase 1: hardened capture. The Dockerfile creates `/captures` owned by `pwuser` so the named volume inherits it.
  - Phase 2: the guard, the two new response fields and the tests.
  - Interception mechanism: C first checks, against Playwright 1.65, whether `context.route` handlers run on redirect hops. If they do, use `context.route`. If they do not, intercept HTTP(S) through a CDP session's `Fetch.requestPaused`, which pauses every hop, attached to each page the context opens. WebSockets go through `context.route_web_socket` in either case.
  - If the CDP redirect guard is not working within the 30-minute limit, C ships the `context.route` guard, the redirect case of the hostile-page test is recorded as a gap under known limits in this file, and the build continues.
  - `is_internal(host)` is a pure function with unit tests: each compose service name, both Docker host aliases, 169.254.169.254, a private IP literal, an IPv6 loopback, and a public-looking name whose resolver is patched to return a private address.
  - Hostile-page test (`sandbox/tests/test_hostile_page.py`, run inside the hardened container). The test starts two listeners on 127.0.0.1: a page server and a canary that records any connection. The page tries `fetch` to `host.docker.internal:8000`, each compose service name, a private IP, 169.254.169.254 and the canary; an image and a WebSocket to the canary; and a link through the page server's `/redirect`, which answers 302 to the canary. The capture function takes one explicit allowed origin, passed only by this test and never by the HTTP endpoint, so the page server itself can load. The test first confirms the canary is reachable directly, then asserts the canary saw zero browser connections, `internal_requests_blocked` equals the number of attempts, `internal_hosts_blocked` lists every target, and each block was logged.
- **D.** The matcher is a plain substring test of each brand's ASCII names against the certificate's domains, skipping official domains. It logs each match and a stats line every 30 s, and reconnects with backoff. It does not call core.
- **E.** Vue 3 with TypeScript from the standard Vite template, one page showing the `/healthz` result through the fetch wrapper, committed `package-lock.json`.

## Decisions where the spec was open

1. **Blocklist lives in the `domains` table, seeded on core start.** Core runs the idempotent seed after migrations, so `/v1/check` works straight after `make up`; `make seed` re-runs it after someone edits `data/`.
2. **Sandbox isolation is layered, and the network layer does not cover core.** Verified on Docker Engine 29.8 (Docker Desktop) with raw sockets from the sandbox container:
   - Postgres, redis and certstream, which publish no host port, are unreachable by name and by container IP.
   - Core and console, which publish a host port, are reachable from the sandbox both by container IP and through `host.docker.internal`. Docker's bridge isolation does not apply to published ports.
   - So for core the protection is the browser-level guard, which blocks both paths for pages, plus the write token, which returns 401 to the sandbox. A compromised browser process can still call core's open routes (`/healthz`, `/v1/check`, `/v1/batch`, `/v1/report`). The egress proxy in the follow-ups is the fix.
3. **Known limits of the guard.** The guard has two layers: a CDP `Fetch` session per page, which sees every redirect hop, and Playwright's `context.route`, which covers workers, cross-site iframes and popups but only the first hop. Chromium runs with site isolation off so iframes stay under the page's CDP session, and with popups disabled, because a popup's redirect hop could otherwise leave before the CDP session attached. A host that fails to resolve is blocked. What it does not cover:
   - A compromised browser process bypasses it, because it runs in the browser's control channel.
   - Redirect hops inside a dedicated or shared worker: a worker fetch to an allowed URL that redirects to an internal host is only checked at the first hop. Expected from the redirect experiment, not tested.
   - Resolve-then-check has a DNS rebinding race, because Chromium resolves the name again itself. Allowed hosts are re-resolved on every request, which narrows it.
   - WebRTC and other non-HTTP traffic are not intercepted.
   - Closing these needs an egress proxy with `sandbox_net` set to internal; that is a follow-up, not part of this skeleton.
4. **The write token is a shared dev token, not officer auth.** It ships in the console's client bundle, so anyone who can open the console can read it. The console login is a mock in the docs; real auth replaces this.
5. **Unknown URLs return `pending` from `/v1/check`, and a definite answer from `/v1/batch`.**
6. **`BATCH_CUTOFF` is 70**, the brief's block band. The eval owner tunes it (slice 1 of the application build set it to 40; see `docs/app-plan.md`, decision 11). In the skeleton nothing resolves a pending check, so every unknown URL in a batch uses its full budget and comes back `allow` with `timed_out` true. This is skeleton-only and is replaced by the fast score in slice 1.
7. **Chromium runs with Playwright's default (its own sandbox off).** The container is the boundary. Turning Chromium's sandbox on needs a custom seccomp profile; it is a follow-up.
8. **Fresh browser context per job, not a container per job.** The brief asks for a container per job; the spec for this skeleton asks for a context per job.
9. **AdGuard pinned to v0.107.80, not v1.0.0.** v1.0.0 was five days old on 2026-11-24. No config is committed because AdGuard rewrites its config file at runtime; the first-run wizard is at port 3001.
10. **certstream uses its baked-in config.** The repo's sample config has an IP whitelist that would reject the hunter.

## Verification

Run from a fresh `git clone` of the branch into a scratch directory, so only committed files are tested. Afterwards reset that copy and bring the stack up in the real working directory.

1. `make up`, then `docker compose ps`: all eight default services healthy, adguard absent.
2. `curl localhost:8000/healthz`; `POST /v1/check` with `https://uaepass.ae/login` (expect `allow`), a blocklisted `.example` URL (expect `block` with `safe_action`) and an unknown URL (expect `pending`).
3. `POST /v1/batch` with the same three URLs: no `pending`, the unknown one is `allow` with `timed_out` true, and the call takes about one budget.
4. `POST /v1/review/x` without a token returns 401 and with the token from `.env` does not. `docker compose exec sandbox env` shows no token and no API key.
5. From the worker container: POST `http://sandbox:8001/capture` for `https://example.com`; confirm the title, `internal_requests_blocked` of 0 and that the screenshot file exists in the `captures` volume. Then a `mode: deep` check to show core, redis, worker and sandbox chained.
6. From the sandbox container with python sockets: connecting to `example.com:443` succeeds (positive control); connecting to postgres, redis and core fails by service name and by their container IPs. Also try `host.docker.internal:8000` with a raw socket and report what happens, since the guard does not cover raw sockets.
7. The hostile-page test passes inside the running sandbox container. Also POST `/capture` with `http://host.docker.internal:8000/healthz` and expect 422.
8. `docker compose logs hunter`: a stats line with a non-zero certificate count.
9. Open `http://localhost:5173` with the Playwright browser tool and confirm the page shows core's health; fall back to `curl localhost:5173/api/healthz`.
10. `make test`, `make eval`, `make migrate`, `make seed`, `make reset` (answer no, then yes), `make up-stretch` (adguard starts).
11. Hot reload: touch a core source file and a console source file, confirm the reload lines in the logs.

Known risk: Docker Desktop on the build machine has 7.75 GiB and another project's six containers are running. If the stack runs out of memory, report it and do not stop those containers.

The final report covers what works, what is stubbed, what could not be verified, and each decision above.

## Follow-ups (not part of this skeleton)

- Rate limit `/v1/report`.
- Tune `BATCH_CUTOFF` on the held-out split.
- Replace the batch wait-then-allow behaviour with the fast score (slice 1).
- Egress proxy for the sandbox with `sandbox_net` set to internal, which closes the guard's known limits.
- Chromium's own sandbox, through a custom seccomp profile.
- Real officer auth in place of the shared write token.

## Progress

- 2026-11-24: plan written and amended (sandbox guard, write token, hostile-page test, batch budget, pending rule).
- 2026-11-24: approved with `BATCH_CONCURRENCY`, loopback-only console, `navigation_blocked` and the guard fallback rule. Branch `devops/skeleton` created.
- 2026-11-24: packages F, A, B, C, D and E built and committed. Fix rounds committed for core host parsing (backslash, trailing dot, UTS-46), the hunter's message validation, the sandbox guard (iframes, workers, fail closed) and the AdGuard port binding.
- 2026-11-24: first integration pass in the working directory. `make up` brought all eight default services up healthy. Verification steps 2 to 6, 8 and 9 passed there; step 6 produced the published-port finding now in decision 2.
- 2026-11-24: independent review returned five findings (popup redirect bypass, allowlist subdomain matching, stale sandbox tests, scripts failing before the first `make up`, stale console dependencies). All five fixed and committed.
- 2026-11-24: full verification list run from a clean clone of the branch; every step passed. Test counts: core 27, sandbox 36, hunter 20, console build clean. Images were already cached, so cold build time was not measured. `make up` then run again in the working directory.
- 2026-11-24: verified on a second machine (Docker Engine 29.7.2, 4 GiB, 2 CPUs, empty image cache) from `main` after the merge. Cold `make up` took 265 s; every service came up healthy and peak use stayed under 1 GiB in total. Verification steps 1 to 11 passed, with step 9 checked by curl through the Vite proxy. Step 6 reproduced decision 2: core is reachable from the sandbox by container IP and through `host.docker.internal`, postgres and redis are not. Vite logs an HMR update only when a loaded module's content changes, so `touch` alone is not enough to see it.
