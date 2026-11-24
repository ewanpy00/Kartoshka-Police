# Kartoshka-Police

Kartoshka-Police is an anti-phishing system for UAE residents. One core service analyses a link and returns a verdict (`allow`, `block` or `pending`). Every client calls the same core API: the Gatekeeper browser, DNS, the batch and CLI route used by judges, and the hunter that looks for new look-alike domains in certificate transparency logs. Confirmed verdicts go to an officer console for review. See `ARCHITECTURE.md` for the design and `IDEA.md` for the product background.

**Status:** every layer of `ARCHITECTURE.md` is built and runs in the compose stack, except the Android app, which is source only (see `gatekeeper/README.md`). Progress notes per slice are in `docs/app-plan.md`.

| Layer | What runs |
|---|---|
| Core | `/v1/check` with a deterministic fast score (lists, lexical, homoglyphs, RDAP, CT, ASN, feeds, campaign graph, URL model), deep analysis in the sandbox (two profiles, form capture, kit hashes, visual brand match), the AI explanation layer, evidence packs (JSON and PDF), reports, radar, takedowns and the campaign graph |
| Hunter | Certificate Transparency with name and infrastructure filters, OpenPhish, WhoisDS newly registered domains, and the watchlist ticker; candidates are screened by core |
| Officer console | Queue with keyboard review, case card, Hunter feed, campaigns graph, takedowns, impact, model quality, health |
| Resident PWA | Link X-ray, safe preview, my reports, scam radar, SMS paste, share target |
| DNS Shield | AdGuard Home fed every minute with the confirmed list, block counters back to core (stretch profile) |
| Gatekeeper | Android default-browser source; its logic is unit-tested on a JVM and was checked against core |

## Repository layout

| Path | What it is |
|---|---|
| `core/` | FastAPI core API, database migrations, RQ worker jobs |
| `sandbox/` | Hardened headless browser that captures suspicious pages |
| `hunter/` | Finds new look-alike domains (CT, feeds, newly registered domains) and sends them to core |
| `console/` | Officer console (Vue 3 + Vite) |
| `resident/` | Resident screens as a PWA (Vue 3 + Vite); also shown inside Gatekeeper |
| `gatekeeper/` | Android browser client, a separate Gradle build (not part of the compose stack) |
| `dns/` | AdGuard Home DNS shield and its sync service (stretch profile) |
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
| Officer console | http://127.0.0.1:5173 (mock sign-in, clearly labelled as a demo) |
| Resident PWA | http://127.0.0.1:5174 |
| Product tour (for the pitch) | http://127.0.0.1:5174/showcase?lang=en (or `?lang=ar`) |
| AdGuard admin (`make up-stretch` only) | http://127.0.0.1:3001 (user and password in `.env`) |
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
| `make test` | Run pytest in core, sandbox, hunter and the DNS sync, the console and resident type checks and builds, and the Gatekeeper logic tests (JVM, in a Gradle container) |
| `make eval` | Run the evaluation on `data/eval/test.csv` (development set) and `data/eval/holdout.csv` (hold-out) |
| `make refs` | Capture the brands' official pages and store their visual hashes (needs internet) |
| `make retrain` | Retrain the URL model with officer decisions added as labels |
| `make reset` | Delete all containers and volumes, after a typed `yes` |

### Tests and evaluation

```bash
make test
make eval
```

`make test` on 2026-11-24 ran these suites:

| Suite | Result |
|---|---|
| core | 160 passed |
| sandbox | 38 passed |
| hunter | 33 passed |
| dns | 3 passed |
| gatekeeper | 9 passed |
| console and resident | both builds clean |

`make eval` on 2026-11-24 used the batch cutoff of 40 and the fast path only, without GSB or VirusTotal keys:

| Set | Precision | Recall | FPR | Notes |
|---|---|---|---|---|
| Development (`test.csv`, 611 rows) | 0.996 | 0.753 | 0.004 | Every UAE brand row is caught (60/60, 16 brands); OpenPhish recall is 0.93 |
| Hold-out (`holdout.csv`, 450 rows, untouched) | 0.982 | 0.717 | 0.027 | OpenPhish 0.96, PhishTank 0.47 |

Most misses are PhishTank links behind QR-code and URL shorteners (`qrco.de`, `q-r.to`, `bit.ly`). The fast path cannot see where these lead; the deep analysis follows them, but the batch route does not run it. In the ablation, the URL model gives the largest single gain, from 0.25 to 0.75 recall on the development set.

`make eval` posts the development set and the hold-out set to `/v1/batch?explain=true`. For each set it prints a confusion matrix with precision, recall and false positive rate, rows per origin and per UAE brand, an ablation by signal group and a cutoff sweep. The stack must be running. `python eval/build_set.py <feeds_dir>` rebuilds both sets and the URL-model training lists from feed snapshots.

### API keys

Put API keys (Anthropic, VirusTotal, Google Safe Browsing, search, URLhaus) in `.env`. That file is git-ignored and must never be committed. Every key is optional: without one, that source shows as `skipped` and the score uses the rest. Without `ANTHROPIC_API_KEY` there is no AI explanation; the verdict does not depend on it.

### Demo checklist

- Register the team's own look-alike test domain and host the demo kit on it. Never use a real scam site on stage.
- Set `TAKEDOWN_RECHECK_MIN=1` in `.env` so "Check now" twice can close a takedown during the demo.
- Product tour: `/showcase` on the resident PWA plays every resident feature in 24 s and loops, with no API calls (sample data, labelled). Keys: Space pause, ← → scene, R restart, L language, F full screen; `?t=12000` starts at 12 s, `?paused` holds the first frame. `?phone` shows only the phone screen, full window, for a vertical recording. Add `?demo=1` to the other resident pages to click through them with the same sample data.
- Recording the tour on a phone: the Gatekeeper APK carries the same tour offline (long press the app icon → Product tour, or long press the Home header). `make record-tour lang=ar` opens it on the emulator or a USB phone, records the screen and saves `showcase-video/kartoshka-tour-phone-<lang>.mp4`.
- For the phone, follow `gatekeeper/README.md`. Without the APK, the resident PWA on the phone (`adb reverse tcp:5174 tcp:5174`) shows the same screens.

## Configuration

All settings live in `.env`; `.env.example` lists each one with its default. `BIND_ADDR=0.0.0.0` publishes core to the whole local network and is meant only for connecting the demo phone. The console is always bound to localhost.

## Sandbox isolation

The sandbox opens untrusted pages. What is and is not protected, verified with raw sockets from inside the sandbox container:

- **Unreachable:** postgres, redis and certstream publish no host port, so the sandbox cannot reach them by service name or by container IP. The sandbox also gets no `.env` file, so API keys and the write token never enter it.
- **Reachable:** core and the console publish host ports, and Docker's bridge isolation does not apply to published ports. The sandbox can reach both by container IP and through `host.docker.internal`.
- **What protects core today:** the request guard in the sandbox's browser, which blocks every browser request to an internal address (including redirect hops and WebSockets), and the write token, without which a write gets 401. A compromised browser process could still call core's open routes. An egress proxy for the sandbox is the planned fix.

See decisions 2 and 3 and the follow-ups in `docs/devops-plan.md` for detail and the guard's known limits.
