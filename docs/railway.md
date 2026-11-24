# Kartoshka-Police on Railway: one service, one URL

Status: written on 2026-11-25 from Railway's documentation as read that day. The dashboard steps and the edge behaviour in the checklist have not been run against a real Railway project.

## What gets deployed

One Railway service built from `Dockerfile.railway`, plus Railway's managed Postgres and Redis. The service holds four processes under `tini`, started by `deploy/railway/start.sh`:

| Process | User | Listens on |
|---|---|---|
| core (FastAPI) | `core` | `0.0.0.0:$PORT` (Railway sets `PORT`) |
| RQ worker, queue `deep` | `core` | nothing |
| sandbox (Playwright and Chromium) | `pwuser` | `127.0.0.1:8001`, reachable only from inside the container |
| hunter, only when `HUNTER_ENABLED=true` | `core` | nothing |

One public URL serves three things:

| Path | What |
|---|---|
| `/` | Resident app (the check screens) |
| `/console` | Officer console, behind an access code |
| `/v1/...` and `/healthz` | The core API, same origin as both apps |

Not deployed: DNS Shield (AdGuard and `dnssync`), and certstream. The local compose stack is unchanged and still runs with `make up`.

## Deploy steps

1. Choose an access code. Generate it on your machine without it landing in shell history or logs, and copy it straight into the dashboard:

   ```bash
   python3 -c "import secrets,sys; sys.stdout.write(secrets.token_urlsafe(32))" | pbcopy
   ```

   On Linux use `xclip -selection clipboard` or `wl-copy` in place of `pbcopy`. Nothing is printed. The value is at least 32 characters, which the start script requires. It is the `CORE_WRITE_TOKEN` and also the console access code, so store it in a password manager.
2. In Railway: New Project, Deploy from GitHub repo, pick this repository and the branch to deploy. The first build will fail or crash until the variables below exist. That is expected.
3. On the project canvas press `+ New`, add Postgres, then `+ New` again and add Redis. Note the service names shown on the canvas. The references below assume `Postgres` and `Redis`; use the names you see.
4. Open the app service, Variables tab. Use New Variable for each row, or the RAW Editor to paste several. Add every variable marked required in the table below. Changes are staged: press Deploy to apply them.
5. Service Settings: set the health check path to `/healthz` (Railway's docs place it under service settings without naming the section). If the first start is slow, raise the timeout with `RAILWAY_HEALTHCHECK_TIMEOUT_SEC`.
6. Service Settings, Networking, Public Networking, Generate Domain. This gives a `*.up.railway.app` address.
7. Deploy, wait for the health check to pass, then work through the first-deploy checklist.

There is no `railway.json` or `railway.toml`. Railway has deprecated Config as Code: new services cannot opt in, and existing files stop being read on 2026-12-01. The Dockerfile is selected with the service variable `RAILWAY_DOCKERFILE_PATH` instead, and the health check is set in service settings.

## Variables

Set these on the app service. Names in the first group are Railway's; the rest are read by the image.

| Name | Required | Hosted value or default | What it is for |
|---|---|---|---|
| `RAILWAY_DOCKERFILE_PATH` | required | `Dockerfile.railway` | Makes Railway build this Dockerfile instead of looking for one at the root. |
| `RAILWAY_HEALTHCHECK_TIMEOUT_SEC` | optional | Railway default 300 | Time Railway waits for `/healthz` to answer at deploy. Migrations and seeding run first. |
| `RAILWAY_SHM_SIZE_BYTES` | required | `268435456` | `/dev/shm` size, 256 MB. Railway's default of 64 MB is too small for Chromium. |
| `PORT` | set by Railway | injected | Port core listens on. The start script defaults to 8000 when it is unset. |
| `DATABASE_URL` | required | `${{Postgres.DATABASE_URL}}` | Postgres connection. Core accepts the plain `postgres://` scheme Railway supplies. |
| `REDIS_URL` | required | `${{Redis.REDIS_URL}}` | Redis for the queue, caches, rate limits and daily budgets. |
| `CORE_WRITE_TOKEN` | required | the generated code, at least 32 characters | Write token for officer routes and the console access code. Start refuses a shorter one. |
| `DEMO_BANNER` | optional | `true` | Build argument. Shows the demo banner in both apps. A change rebuilds the image. |
| `ANTHROPIC_API_KEY` | optional | unset | Turns on the AI layer. Without it the app uses rules and the brand catalogue only. |
| `AI_DAILY_CALLS` | optional | `200` | Daily cap on AI calls (UTC day). Unset means no cap. Over the cap, verdicts fall back to rules. |
| `DEEP_DAILY_CHECKS` | optional | `300` | Daily cap on deep browser checks. Unset means no cap. Over it, a check keeps its fast verdict and is not queued. |
| `BATCH_MAX_URLS` | optional | `200` suggested, code default 5000 | Most URLs one batch call accepts. It can be lowered but not raised above 5000. |
| `CHECK_RATE_PER_MIN` | optional | default 120 | `POST /v1/check` per client address, without a write token. |
| `READ_RATE_PER_MIN` | optional | default 300 | Public reads per client address. |
| `BLOCKLIST_RATE_PER_MIN` | optional | default 60 | `/v1/blocklist` and `/v1/blocklist.txt` per client address. |
| `REPORT_IP_RATE_PER_HOUR` | optional | default 60 | `POST /v1/report` per client address. |
| `PREVIEW_IP_RATE_PER_HOUR` | optional | default 30 | `POST /v1/preview` per client address. |
| `SMS_IP_RATE_PER_HOUR` | optional | default 120 | `POST /v1/sms` per client address. |
| `BATCH_RATE_PER_HOUR` | optional | default 20 | `POST /v1/batch` per client address, without a write token. |
| `AUTH_FAIL_PER_10MIN` | optional | default 10 | Wrong bearer tokens per client address before every token from that address, right or wrong, gets 429 for the rest of the window. |
| `HUNTER_ENABLED` | optional | `false` (image default) | `true` starts hunter inside the service. |
| `HUNTER_SOURCES` | optional | `feeds,nrd,watchlist` | Hunter sources. A value containing `ct` stops the service from starting. |
| `HUNTER_SUBMIT_PER_MINUTE` | optional | `20` | Most entries hunter sends to core per minute; the rest wait. |
| `URLHAUS_AUTH_KEY` | optional | unset | Free abuse.ch key; without it URLhaus is skipped. |
| `VIRUSTOTAL_API_KEY`, `GOOGLE_SAFE_BROWSING_API_KEY`, `SEARCH_API_KEY` | optional | unset | Optional lookups; each runs only when its key is set. |
| `RQ_QUEUE` | optional | `deep` | Queue the worker listens on and core enqueues to. |

Fixed inside the image, no need to set: `STATIC_DIR=/srv/static`, `TRUST_PROXY=true`, `SANDBOX_URL=http://127.0.0.1:8001`, `DATA_DIR=/srv/data`, `CAPTURES_DIR=/captures`.

Only `DEMO_BANNER` reaches the build. Railway passes a service variable to a Dockerfile build only if it is declared with `ARG`, and no secret is. No token or URL appears in an `ARG`, an `ENV` or a `RUN` line, and the console bundle contains no token: the officer types the access code at sign-in.

The sandbox runs with an empty environment plus `PATH`, `HOME`, `CAPTURES_DIR`, `CAPTURE_TIMEOUT_MS` and `PLAYWRIGHT_BROWSERS_PATH`. The database URL, Redis URL and token are never in its environment, and the worker reads its Redis URL from the environment rather than from its command line, which every user in the container can read.

## Health check

Set the path to `/healthz` in service settings. Railway uses the injected `PORT`, counts any 2xx as healthy, and sends the request from the host `healthcheck.railway.app`.

## First-deploy checklist

1. Open the generated domain. The resident app loads at `/` and shows the demo banner.
2. Open `/console`. A wrong access code shows "Access code not accepted". The generated code signs in.
3. Run one check of a domain you own or a `.example` name from the resident app, and confirm a verdict comes back.
4. In `/console`, open System health and confirm the budget row shows the AI and deep limits you set.
5. Confirm the edge overwrites a client-sent `X-Real-IP`. Send a forged value and compare it with your real address (for example from a "what is my IP" site):

   ```bash
   curl -s -o /dev/null -w '%{http_code}\n' -H 'X-Real-IP: 203.0.113.9' https://YOUR-DOMAIN.up.railway.app/healthz
   ```

   That only shows the request is accepted. To prove the overwrite, call `POST /v1/check` more times than `CHECK_RATE_PER_MIN` allows (or temporarily set it to `3`) while sending a different forged `X-Real-IP` on each request. If a `429` still arrives, the limiter is keying on your real address and the header is overwritten. If it never does, `TRUST_PROXY` must be set to `false` until you know why, because every client could then pick its own address.
6. In the deployment logs, confirm migrations and seeding ran and no line names a missing variable.

## Turning it off

- Stop the running deployment: the deployment's three-dot menu, Remove.
- Remove everything: delete the app service, Postgres and Redis from each service's settings (danger section). Deleting Postgres deletes the data.
- Backstop: a workspace hard usage limit takes workloads offline when reached.
- The generated domain: Railway's docs do not describe removing one. Deleting the service removes it with it.

## Known limits

- No certstream in the image, so hunter has no certificate-transparency source here. It runs `feeds`, `nrd` and `watchlist` only.
- Chromium's own sandbox is off, as it is in the local stack. Railway documents nothing on user namespaces or seccomp. The boundary is the separate Unix user (`pwuser`, which cannot read `/srv/core`, `/srv/hunter` or `/srv/data`) plus the container.
- A compromised browser process can reach loopback, including core on `127.0.0.1:$PORT`, and the private network, including `postgres.railway.internal` and `redis.railway.internal`. The request guard in the sandbox blocks these for page requests (it covers `*.railway.internal`, loopback and private addresses), but it is not a network boundary.
- The guard has a documented DNS-rebinding race: a name can resolve to a public address when checked and a private one when the browser connects.
- Compose-level limits have no Railway equivalent here: `cap_drop`, read-only root filesystem, memory and pid caps.
- The health check runs only at deploy start. A process that dies later is caught by the start script, which exits non-zero when any child exits; whether the service then restarts depends on its restart policy in service settings. A hung process is not caught.
- Sign-in lockout is per address. After `AUTH_FAIL_PER_10MIN` wrong codes from one address, the right code is refused from that address too until the window ends, so someone on the same office or carrier address can lock officers out for up to ten minutes. The alternative, letting the right code through, would let guessing continue, so the lockout is kept.
- Client addresses come from `X-Real-IP`. Railway documents that header but not `X-Forwarded-For`, so the latter is not trusted. Many phones on one mobile carrier can share an address, which is why the per-address limits are well above one phone's use.
- Not verified locally: that the edge overwrites `X-Real-IP`, Chromium start-up and memory under Railway's limits, and the dashboard steps.
