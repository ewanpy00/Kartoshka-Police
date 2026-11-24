# Kartoshka-Police

Kartoshka-Police protects UAE residents from scam links and gives the police the evidence to shut those sites down. It was built for the ScamShield AI hackathon (42 Abu Dhabi × Abu Dhabi Police).

One core service checks a link and returns a verdict (`allow`, `warn` or `block`) with a 0–100 score and reasons in Arabic and English. Every part of the system uses that same service:

- **Residents** check links in the **Gatekeeper** Android app (the phone's default browser, so every tapped link is checked first) or in the **resident web app** (Link X-ray, safe preview, My reports, Scam radar).
- **The Hunter** finds new look-alike domains before anyone reports them, from certificate transparency logs, phishing feeds and newly registered domains.
- **Officers** review suspected sites in the **officer console**, confirm or reject them, see the campaigns behind them, and prepare takedown requests.
- **DNS Shield** (optional) blocks officer-confirmed domains for every device on a home network.

```
  Hunter (CT logs, feeds, new domains)          Residents (Gatekeeper app, resident web app)
                 │                                              │
                 └──────────────► Core: link check ◄────────────┘
                                  fast score → deep analysis in a sandbox → verdict + evidence
                                         │
               ┌─────────────────────────┼─────────────────────────┐
               ▼                         ▼                         ▼
        Officer console          Blocklist (confirmed)       Takedown packs
        review · campaigns       → Gatekeeper, DNS Shield    → registrar, host
```

For the full design see [ARCHITECTURE.md](ARCHITECTURE.md). For every other document see [docs/README.md](docs/README.md).

## What is built

| Part | What runs |
|---|---|
| Core | `/v1/check` with a deterministic fast score (allow and block lists, lexical and homoglyph checks, domain age from RDAP, certificate transparency, ASN, threat feeds, campaign links, a LightGBM URL model), deep analysis in the sandbox (two browser profiles, form capture, kit hashes, visual brand match), an AI explanation layer, evidence packs (JSON and PDF), reports, radar, takedowns and the campaign graph |
| Hunter | Certificate transparency with name and infrastructure filters, OpenPhish, WhoisDS newly registered domains, and the watchlist re-checks; candidates are scored by core |
| Officer console | Review queue with keyboard shortcuts, case card, Hunter live feed and watchlist, campaigns (graph, merge, exclude, related-site search), takedown tracking, fake helplines, Impact, Model quality, evidence chain, audit log, system health |
| Resident web app | Link X-ray, safe preview, My reports, Scam radar, SMS paste, share target |
| Gatekeeper | Android default browser, built separately with Android Studio; its decision logic is unit-tested on a plain JVM |
| DNS Shield | AdGuard Home, fed every minute with the confirmed list, with block counts sent back to core (optional `stretch` profile) |

## Repository layout

| Path | What it is |
|---|---|
| `core/` | FastAPI core API, database migrations, RQ worker jobs |
| `sandbox/` | Locked-down headless browser that captures suspicious pages |
| `hunter/` | Finds new look-alike domains and sends them to core |
| `console/` | Officer console (Vue 3 + Vite) |
| `resident/` | Resident web app (Vue 3 + Vite); also shown inside Gatekeeper |
| `gatekeeper/` | Android app, a separate Gradle build (not part of the Docker stack) |
| `dns/` | DNS Shield: AdGuard Home and its sync service |
| `data/` | Allowlist, blocklist, UAE brand definitions, evaluation sets |
| `eval/` | Evaluation tool: precision, recall and false positive rate |
| `scripts/` | Shell scripts behind the `make` targets |
| `docs/` | Plans, build records, the test dataset and the product brief |

## Run it

You need Docker Desktop (or Docker Engine with Compose v2), GNU Make, and about 4 GB of memory free for Docker.

```bash
make up
```

On the first run this creates `.env` from `.env.example` with a generated `CORE_WRITE_TOKEN`, builds every image, starts the stack and waits until every service is healthy.

| What | Address |
|---|---|
| Core API | http://127.0.0.1:8000 (interactive docs at `/docs`) |
| Officer console | http://127.0.0.1:5173 (demo sign-in, labelled as such; not connected to UAE PASS) |
| Resident web app | http://127.0.0.1:5174 |
| AdGuard admin (`make up-stretch` only) | http://127.0.0.1:3001 (user and password in `.env`) |
| AdGuard DNS (`make up-stretch` only) | port 5335 |

Nothing else is published to the host. Postgres and Redis are reachable only inside the Docker network.

### Make targets

| Target | What it does |
|---|---|
| `make up` | Create `.env` if missing, build, start and wait until healthy |
| `make up-stretch` | The same, plus DNS Shield |
| `make down` | Stop the stack |
| `make ps` | Show service status |
| `make logs` | Follow the logs; `make logs s=core` shows one service |
| `make migrate` | Apply database migrations |
| `make seed` | Reload `data/` into the `domains` table |
| `make test` | Run the test suites: core, sandbox, Hunter and DNS sync (pytest), the console and resident type checks and builds, and the Gatekeeper logic tests (JVM, in a Gradle container) |
| `make eval` | Score the evaluation sets and print precision, recall and false positive rate |
| `make refs` | Capture the brands' official pages and store their visual hashes (needs internet) |
| `make retrain` | Retrain the URL model with officer decisions added as labels |
| `make reset` | Delete all containers and volumes, after you type `yes` |

### Show it

- **Officer console:** open http://127.0.0.1:5173 and sign in. The review queue fills by itself as the Hunter finds candidates, usually within minutes of `make up`.
- **Phone:** follow [gatekeeper/README.md](gatekeeper/README.md). Without the app, open the resident web app on the phone (`adb reverse tcp:5174 tcp:5174`); it shows the same screens.
- **On stage:** use the team's own look-alike test domain, never a real scam site. Set `TAKEDOWN_RECHECK_MIN=1` in `.env` so pressing "Check now" twice can close a takedown during the demo.

## How well it scores

`make eval` sends the development set and the hold-out set to `/v1/batch?explain=true` (the stack must be running). For each set it prints a confusion matrix with precision, recall and false positive rate, results per source and per UAE brand, an ablation by signal group and a cutoff sweep.

Results from 2026-11-24, with a cutoff of 40, the fast path only and no Safe Browsing or VirusTotal keys:

| Set | Precision | Recall | False positive rate | Notes |
|---|---|---|---|---|
| Development (`data/eval/test.csv`, 611 rows) | 0.996 | 0.753 | 0.004 | Every UAE brand row is caught (60 of 60, 16 brands); OpenPhish recall 0.93 |
| Hold-out (`data/eval/holdout.csv`, 450 rows, never tuned on) | 0.982 | 0.717 | 0.027 | OpenPhish 0.96, PhishTank 0.47 |

Most misses are PhishTank links behind QR-code services and URL shorteners (`qrco.de`, `q-r.to`, `bit.ly`). The fast path can't see where they lead; the deep analysis follows them, but the batch route doesn't run it. In the ablation, the URL model gives the largest single gain, from 0.25 to 0.75 recall on the development set.

`python eval/build_set.py <feeds_dir>` rebuilds both sets and the URL model's training lists from feed snapshots. A separate, larger labelled set (2,221 URLs, with UAE and worldwide subsets) is in [docs/data_set/](docs/data_set/DATASET_SOURCES.md).

`make test` on 2026-11-24: core 160 passed, sandbox 38, Hunter 33, DNS 3, Gatekeeper 9; console and resident builds clean.

## Configuration and API keys

All settings live in `.env`; `.env.example` lists each one with its default.

- **API keys** (Anthropic, VirusTotal, Google Safe Browsing, search, URLhaus) go in `.env`. That file is git-ignored and must never be committed. Every key is optional: without one, that source shows as `skipped` and the score uses the rest. Without `ANTHROPIC_API_KEY` there is no AI explanation; the verdict doesn't depend on it.
- **`BIND_ADDR=0.0.0.0`** publishes core to the whole local network. Use it only to connect a demo phone over Wi-Fi, then set it back. The console is always bound to localhost.
- **The console build includes `CORE_WRITE_TOKEN`** so it can call core's admin routes. Never deploy a console build made with a real token to a public host.

## Sandbox isolation

The sandbox opens untrusted pages. Checked with raw sockets from inside the sandbox container:

- **Unreachable:** Postgres, Redis and certstream publish no host port, so the sandbox can't reach them by service name or by container IP. The sandbox also gets no `.env`, so API keys and the write token never enter it.
- **Reachable:** core and the console publish host ports, and Docker's bridge isolation doesn't apply to published ports, so the sandbox can reach both by container IP and through `host.docker.internal`.
- **What protects core today:** the request guard in the sandbox's browser blocks every request to an internal address (including redirect hops and WebSockets), and every write needs the write token. A compromised browser process could still call core's open routes. An egress proxy for the sandbox is the planned fix.

Decisions 2 and 3 and the follow-ups in [docs/devops-plan.md](docs/devops-plan.md) have the detail and the guard's known limits.
