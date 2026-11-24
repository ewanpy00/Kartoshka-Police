# Kartoshka-Police

Kartoshka-Police is an anti-phishing system for UAE residents. One core service analyses a link and returns a verdict (`allow`, `block` or `pending`). Every client calls the same core API: the Gatekeeper browser, DNS, the batch and CLI route used by judges, and the hunter that looks for new look-alike domains in certificate transparency logs. Confirmed verdicts go to an officer console for review. See `ARCHITECTURE.md` for the design and `IDEA.md` for the product background.

**Status:** this is the DevOps skeleton. The detection logic is stubbed. `POST /v1/check` looks the host (or any parent domain) up in the `domains` table: allowlisted gives `allow`, blocklisted gives `block`, anything else gives `pending`, which means "no verdict yet", never "safe".

## Repository layout

| Path | What it is |
|---|---|
| `core/` | FastAPI core API, database migrations, RQ worker jobs |
| `sandbox/` | Hardened headless browser that captures suspicious pages |
| `hunter/` | Consumer of the certificate transparency stream that matches brand names |
| `console/` | Officer console (Vue 3 + Vite) |
| `gatekeeper/` | Notes for the Android browser client (not part of the compose stack) |
| `dns/` | Notes for the AdGuard Home DNS shield (stretch profile) |
| `data/` | Allowlist, blocklist, brand definitions and the evaluation sample |
| `eval/` | Evaluation tool that prints precision, recall and false positive rate |
| `scripts/` | Shell scripts behind the make targets |

## How to build and run

### Prerequisites

- Docker Desktop, or Docker Engine with the Compose v2 plugin
- GNU Make
- About 4 GB of memory free for Docker

### Start

```bash
make up
```

On first run this creates `.env` from `.env.example` with a generated `CORE_WRITE_TOKEN`, builds every image, starts the stack and waits until every service is healthy.

### What is reachable

| What | Address |
|---|---|
| Core API | http://127.0.0.1:8000 (interactive docs at `/docs`) |
| Officer console | http://127.0.0.1:5173 |
| AdGuard setup (`make up-stretch` only) | http://127.0.0.1:3001 |
| AdGuard DNS (`make up-stretch` only) | port 5335 |

Nothing else is published to the host. Postgres and redis are reachable only from inside the compose network.

### Make targets

| Target | What it does |
|---|---|
| `make up` | Create `.env` if missing, build, start and wait until healthy |
| `make up-stretch` | Same, plus the AdGuard DNS service |
| `make down` | Stop the stack |
| `make ps` | Show service status |
| `make logs` | Follow logs; `make logs s=core` shows one service |
| `make migrate` | Apply database migrations in core |
| `make seed` | Reload `data/` into the `domains` table |
| `make test` | Run pytest in core, sandbox and hunter, and the console type check and build |
| `make eval` | Run the evaluation on `data/eval/test.csv` (development set) and `data/eval/holdout.csv` (hold-out) |
| `make reset` | Delete all containers and volumes, after a typed `yes` |

### Tests and evaluation

```bash
make test
make eval
```

`make eval` posts the development set and the hold-out set to `/v1/batch?explain=true`. For each set it prints a confusion matrix with precision, recall and false positive rate, rows per origin and per UAE brand, an ablation by signal group and a cutoff sweep. The stack must be running. `python eval/build_set.py <feeds_dir>` rebuilds both sets and the URL-model training lists from feed snapshots.

### API keys

Put API keys (Anthropic, VirusTotal, Google Safe Browsing, search) in `.env`. That file is git-ignored and must never be committed.

## Configuration

All settings live in `.env`; `.env.example` lists each one with its default. `BIND_ADDR=0.0.0.0` publishes core to the whole local network and is meant only for connecting the demo phone. The console is always bound to localhost.

## Sandbox isolation

The sandbox opens untrusted pages. What is and is not protected, verified with raw sockets from inside the sandbox container:

- **Unreachable:** postgres, redis and certstream publish no host port, so the sandbox cannot reach them by service name or by container IP. The sandbox also gets no `.env` file, so API keys and the write token never enter it.
- **Reachable:** core and the console publish host ports, and Docker's bridge isolation does not apply to published ports. The sandbox can reach both by container IP and through `host.docker.internal`.
- **What protects core today:** the request guard in the sandbox's browser, which blocks every browser request to an internal address (including redirect hops and WebSockets), and the write token, without which a write gets 401. A compromised browser process could still call core's open routes. An egress proxy for the sandbox is the planned fix.

See decisions 2 and 3 and the follow-ups in `docs/devops-plan.md` for detail and the guard's known limits.
