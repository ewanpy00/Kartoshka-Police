# Officer Console (admin panel) plan

This is the build plan and progress log of the Officer Console. It was built on branch `feat/admin-console`, then restyled and extended (stage 2), and all of it is merged into `main`.

## Status (2026-11-24)

All seven steps are built, committed and verified on the running stack. `make up` ends healthy and `make test` is green: core 259, sandbox 50, hunter 29, console 10 plus the type-checked build.

Verified live, not only in tests:

- A reported URL goes through the deep check and appears as a case with its screenshot.
- Confirm in the console puts the domain on `/v1/blocklist`, writes a `case.confirm` audit row, and `/v1/check` then returns block.
- Reject with a reason stores the reason and leaves the domain off the blocklist.
- Chain verify returns intact; the evidence PDF downloads with the token and is refused without it.
- A takedown pack for a confirmed domain unzips and `shasum -c manifest.sha256` passes; the stored hash equals the file's; an unconfirmed domain gets 409; resident notes are absent from the pack.
- Console in a browser: sign-in banner, queue, case card, defanged domains, HTML in a report note shown as text, AR/EN switch to RTL, live feed connected and receiving Hunter events, chain check, no console errors.

Not verified live: a campaign with real data (no two real domains shared a strong link; covered by tests), the campaign graph in a browser, Safe Browsing and VirusTotal calls against the real services (no keys set; mocked in tests).

Changes from the plan below, made during the build, are marked "changed" in the decisions table.

## Context

The Officer Console lets a police officer review suspected scam domains, confirm or reject them, see campaigns, and prepare takedown packs. Code freeze is 06:00 tomorrow.

The brief assumed a `feat/app` branch. It does not exist (not local, not on origin), so the work branches from `main`, which is the devops skeleton. Three consequences:

- **Nothing produces a verdict yet.** A deep check calls the sandbox, discards the title and screenshot, and stays `pending`. No evidence row is ever written. A new package P (deep pipeline) is needed before the queue can show a case.
- **The migration is `0002`, not `0003`**, and it creates every table the admin panel needs.
- **The proposal is only on `origin/docs`.** `docs/admin-panel.md` is copied onto the branch in the first commit. `docs/app-plan.md` does not exist and is not used.

Branch: `feat/admin-console`, created from `main`. No push, no rename.

## Decisions taken where the docs were silent or disagreed

| Topic | Decision |
|---|---|
| Score of exactly 70 | Block. `>= 70` block, `30..69` warn, `< 30` allow (matches `BATCH_CUTOFF`). |
| Case key | `checks.domain` = normalised host with a leading `www.` removed. No public-suffix handling tonight. |
| Queue membership (changed) | A domain with a resident report, or whose representative check is warn or block. The representative is the highest-scoring evidence since the last officer re-run, so a cloaking site cannot clear itself with an anonymous clean check; only an officer re-run of the flagged URL can. Official and allowlisted domains never appear. |
| Reserved sources (added) | `hunter`, `watchlist`, `user_report` and `officer` on `/v1/check` need the write token, so a caller cannot forge where a check came from. |
| Lookalike rule (added) | A brand name must be a whole dot- or hyphen-separated token of the host, a run of adjacent tokens joined, or the name joined to one of the brand's keywords. Bare substrings do not match (`rustammullagaliev.ru` is not TAMM). |
| Page facts (added) | Forms, inputs and links are read over the browser's debugging protocol, outside the page's script world. If they cannot be read the record says `capture.facts_available: false` and the score gains `PAGE_FACTS_UNAVAILABLE` (30). |
| Campaign (changed) | Two or more domains joined by a strong link. A single domain has no campaign. Official phone numbers and official payment hosts are never links. Status is `campaign` only after an officer confirm. |
| Events (added) | Review and campaign events are sent only after the database commit succeeds. |
| Helpline numbers (changed) | Taken from each case's representative evidence when it names a brand and is warn or block. Each row has `confirmed`; the CSV exports officer-confirmed rows only. |
| Ranking | `score × ln(1 + reports + hits) × freshness × boost`. `hits` = number of checks on the domain. `freshness = 1 / (1 + days since last seen)`. `boost = 1.5` when score is 30 to 69. Computed in Python. |
| Reject reasons | `legitimate_site`, `parked_or_empty`, `already_offline`, `not_enough_evidence`, `test_or_internal`. The server validates the code; AR/EN labels live in the console. |
| Auto-confirm | Deep score above 90 and a credential form. Sets `domains.confirmed_by='auto'`. Undo deletes that row and writes an audit entry; the case returns to the open queue. |
| Reject | Writes the review with its reason and removes any `confirmed` row for the domain. |
| Hash chain | `hash = sha256(prev_hash + "\n" + canonical_json({id, check_id, created_at, payload}))`. Canonical JSON: sorted keys, `(",", ":")` separators, UTF-8, no floats in payloads. Genesis `prev_hash` is 64 zeros. Order is a new `evidence.seq` identity column. Appends take a Postgres advisory lock. |
| Review and the chain | The officer decision is not part of the hashed payload. It is joined from `reviews` at export time, so evidence rows are never updated. |
| PDF library | WeasyPrint (BSD) with Jinja2 autoescape. Its `url_fetcher` hook is what fix 1 asks for. |
| Evidence exports | `/v1/evidence/{id}.pdf` and `.json` both go behind the write token. |
| WS auth (changed) | The client connects to `WS /v1/events` and sends `{"type":"auth","token"}` as its first message; the server answers `{"type":"hello"}` or closes with 4401. A token in the URL does not authenticate, because the access log records URLs. |
| Top-site list | `data/allowlist.txt` is the stand-in, as the code already says. Tranco import is a next step. |
| Takedown tables | Two tables (`takedown_packs`, `takedown_requests`) instead of the proposal's one, so the zip and its hash are stored once per recipient. The zip is stored in Postgres. |
| Takedown recipients | Registrar abuse, host abuse, Cloudflare. aeDA and the Safe Browsing report are next steps. |
| Watchlist checks | No scheduler tonight. `POST /v1/admin/watchlist/run` runs the due ones. |
| Clustering | Union-find in plain Python. No graph library. |
| Console i18n | A small dictionary module. No i18n library. |

## Work packages

All implementation is delegated to Sonnet subagents. The main session plans, verifies by running commands, and makes one commit per package. Subagents do not commit. All agents share one working tree (the containers bind-mount it), so file ownership below is strict.

| Pkg | Phase | Owns | Builds |
|---|---|---|---|
| B0 | 0 | `core/alembic/versions/0002_*.py`, `core/app/models.py`, `core/app/admin/router.py`, `core/app/events.py`, `core/app/main.py`, `core/requirements.txt`, `core/Dockerfile`, `docker-compose.yml`, `scripts/*.sh`, `core/tests/test_admin_auth.py` | Migration 0002 (all columns below). Admin router that includes each package's sub-router. `events.publish()`. New deps and system libraries, then one image rebuild. `-p kartoshka-police` in the scripts. Test that walks every `/v1/admin` route and expects 401. |
| A | 1 | `core/app/evidence/`, `core/tests/test_evidence_*.py` | Step 1 and fix 1. |
| B | 1 | `core/app/admin/{cases,review,audit}.py`, `core/app/checks.py`, `core/app/schemas.py`, `core/app/seed.py`, `/v1/report` and `/v1/review` in `main.py`, `core/tests/test_admin_*.py` | Step 2. |
| P | 1 | `sandbox/`, `core/app/jobs.py`, `core/app/deep/`, `data/cloudflare_ips.txt`, `core/tests/test_deep_*.py` | Deep pipeline: capture, RDAP, score, evidence record, auto-confirm. |
| C | 2 | `core/app/graph/`, one call added in `jobs.py`, `core/tests/test_graph_*.py` | Step 4. |
| D | 2 | `core/app/takedown/`, `core/app/helplines/`, `core/app/csvsafe.py`, the CSV branch of `/v1/batch`, `data/brands.yaml` phones, tests | Steps 5 and 6, fix 2. |
| E | 2 | `console/` only, console line of `scripts/test.sh` | Console, fixes 3 and 4. |
| F | 2 | `core/app/events.py` (WS side), `core/app/watch.py`, `core/app/infra.py`, `hunter/`, the `location` and `lead_time` fields in `admin/cases.py`, compose env pass-through, tests | Steps 3 and 7, fix 5. |
| R | 3 | none | Review by a Sonnet agent that wrote none of it: plan plus diff in, ranked defects out. |

Order: B0, then A, B and P in parallel, then C, D, E and F in parallel, then R, fixes and verification.

Reused as is: `require_write_token` (`core/app/auth.py`), `get_session` and `SessionDep` (`core/app/db.py`, `main.py`), `load_brands` and `find_brand` (`core/app/brands.py`), `enqueue_deep_check` (`core/app/queue.py`), the `session`, `client`, `settings` and `enqueued` fixtures (`core/tests/conftest.py`), `apiFetch` (`console/src/api.ts`), the sandbox request guard, and the hunter matcher.

## Fixed interfaces

### Migration 0002

| Table | Change |
|---|---|
| `checks` | add `domain` (string, indexed, nullable) |
| `evidence` | add `seq` (bigint identity, unique) |
| `domains` | add `confirmed_by` (`officer`, `auto`, or null for seeded rows) |
| `reviews` | add `domain` (indexed), `reason` (nullable) |
| `reports` (new) | `id`, `domain` (indexed), `url`, `note`, `check_id`, `created_at` |
| `audit_log` (new) | `id`, `actor`, `action`, `target`, `before` (JSON), `after` (JSON), `reason`, `created_at` |
| `entities` | add `domain_count` (int, default 0), `campaign_id` (nullable FK, set on `domain` entities) |
| `edges` | add `strength` (`strong` or `weak`) |
| `campaigns` | add `name`, `last_activity_at` |
| `watchlist` | add `gsb_first_hit_at`, `vt_first_hit_at`, `gsb_last_clean_at`, `vt_last_clean_at`, `vt_checked_at` |
| `takedown_packs` (new) | `id` (`tp_…`), `recipient_kind`, `recipient`, `sha256`, `zip` (bytes), `generated_at`, `generated_by`, `sent_at`, `sent_by` |
| `takedown_requests` (new) | `id`, `pack_id` (FK), `domain`, `evidence_id` |

Audit actions: `case.confirm`, `case.reject`, `case.auto_confirm`, `case.undo_auto_confirm`, `case.recheck`, `watchlist.add`, `campaign.merge`, `takedown.pack_built`, `takedown.sent`.

### Evidence payload, schema 1 (written by P, read by everyone else)

```json
{
  "schema": 1,
  "identity": {"url": "", "final_url": "", "domain": "", "captured_at": "ISO-8601"},
  "capture": {"title": "", "text": "up to 20000 chars",
              "forms": [{"action": "", "inputs": [{"type": "", "name": ""}]}],
              "screenshot": {"file": "<uuid>.png", "sha256": ""},
              "internal_requests_blocked": 0, "navigation_blocked": false,
              "facts_available": true},
  "risk": {"score": 0, "verdict": "allow|warn|block", "credential_form": false,
           "reasons": [{"code": "", "weight": 0, "source": "", "en": "", "ar": ""}]},
  "infrastructure": {"rdap_status": "ok|failed", "registrar": null, "registered_at": null,
                     "abuse_emails": [], "name_servers": [], "ip": null, "ip_network": null,
                     "ip_owner": null, "ip_country": null, "ip_abuse_emails": [], "proxy": null},
  "scam": {"brand": null, "phones": [], "whatsapp": [], "payment_hosts": []},
  "discovery": {"source": "", "check_id": ""}
}
```

`screenshot` is null when the capture failed. `proxy` is `"cloudflare"` or null. Phones are E.164, normalised with the `phonenumbers` library (default region AE).

### Python interfaces between packages

| Function | Owner | Callers |
|---|---|---|
| `evidence.store.append_evidence(session, check_id, payload, screenshot_file=None) -> Evidence` | A | P |
| `evidence.store.verify_chain(session) -> {"count", "intact", "first_broken"}` | A | A's route |
| `evidence.export.render_pdf(session, evidence_id) -> bytes`, `export_json(session, evidence_id) -> dict` | A | A's routes, D |
| `evidence.store.screenshot_path(evidence) -> Path or None` (inside the captures directory only) | A | A, D |
| `admin.review.apply_decision(session, domain, evidence_id, decision, reason, reviewer) -> Review` | B | B's route, C |
| `admin.review.auto_confirm(session, domain, brand_id, evidence_id)` | B | P |
| `admin.audit.record(session, actor, action, target, before=None, after=None, reason=None)` | B | all |
| `events.publish(type, data)` to Redis channel `kp:events` | B0 | B, P, C, F |
| `graph.cluster.ingest_evidence(session, evidence_id)` | C | `jobs.py` |
| `infra.location(infrastructure) -> {"hosted_in", "registered_through", "network_owner", "behind_proxy"}` | F | B's case route, C |
| `csvsafe.cell(value) -> str` | D | D, `/v1/batch` CSV |

`apply_decision` refuses (409) to confirm an official or allowlisted domain.

### Routes

All under `/v1/admin` require the write token unless marked.

| Route | Pkg | Response |
|---|---|---|
| `GET /evidence/verify` | A | `{count, intact, first_broken: {id, seq, reason} or null, message}` where reason is `payload_hash_mismatch` or `prev_hash_mismatch` |
| `GET /evidence/{id}/screenshot.png` | A | PNG, `nosniff`, checked for the PNG signature |
| `GET /v1/evidence/{id}.pdf`, `.json` (token) | A | file |
| `GET /queue?state=&source=&brand=&band=` | B | `{cases: [CaseSummary]}`; `state` is `open` (default), `auto_confirmed` or `all` |
| `GET /cases/{domain}` | B | `CaseDetail` |
| `POST /v1/review/{evidence_id}` (token, exists) | B | body `{decision, reason, reviewer}`; now updates the blocklist and audit log |
| `POST /cases/{domain}/recheck` | B | 202 `{check_id}` |
| `POST /cases/{domain}/watch` | B | 201 `{domain, next_check_at, expires_at}` |
| `POST /cases/{domain}/undo-auto-confirm` | B | `{domain, state}` |
| `GET /audit?target=&limit=` | B | `{entries: [...]}` |
| `GET /campaigns` | C | `{campaigns: [{id, name, brand, status, domains: {total, confirmed}, first_seen, last_activity_at, active}]}` |
| `GET /campaigns/{id}` | C | `{…header, domains: [{domain, state, score, evidence_id, excluded}], shared: [{kind, value, strength, domain_count}], locations: [{…location, domains}]}` |
| `GET /campaigns/{id}/graph` | C | `{nodes: [{data: {id, label, kind}}], edges: [{data: {id, source, target, strength}}]}` |
| `POST /campaigns/{id}/confirm` | C | body `{domains[], reviewer}`; `{confirmed[], skipped: [{domain, reason}]}` |
| `POST /takedowns` | D | body `{domains[], generated_by}`; 201 `{packs: [Pack], without_recipient: [domain]}`, or 409 `{refused: [{domain, reason}]}` and nothing built |
| `GET /takedowns` | D | `{packs: [Pack]}` where Pack is `{id, recipient_kind, recipient, domains[], sha256, generated_at, sent_at, sent_by}` |
| `GET /takedowns/{id}/pack.zip` | D | zip |
| `POST /takedowns/{id}/sent` | D | body `{sent_by}`; Pack |
| `GET /helplines`, `GET /helplines.csv` | D | `{numbers: [{phone, brand, source, domain, evidence_id, first_seen, confirmed}]}`; the CSV has confirmed rows only |
| `GET /feed?limit=` | F | `{items: [{check_id, domain, url, brand, verdict, score, created_at}]}` |
| `POST /watchlist/run` | F | 202 `{queued}` |
| `WS /v1/events` (first message carries the token) | F | stream of events |

`CaseSummary`: `{domain, state, score, verdict, brand, sources[], reports, hits, first_seen, last_seen, evidence_id, campaign_id, rank}`. `state` is `open`, `auto_confirmed`, `confirmed` or `rejected`.

`CaseDetail` adds: `url, final_url, title, reasons[], infrastructure, location, lead_time, report_notes: [{id, note, created_at}], checks[], reviews[], has_screenshot`.

`lead_time`: `{gsb: {state: "not_polled"|"ahead"|"hit", at_least_hours}, vt: {…}}`. `at_least_hours` runs from the first check on the domain to the last clean poll.

### Events

Envelope `{type, at, data}` on Redis channel `kp:events`.

| Type | Data | Published by |
|---|---|---|
| `hunter.candidate` | `{domain, url, brand, check_id}` | core, when a check arrives with source `hunter` |
| `check.completed` | `{check_id, domain, verdict, score, source, evidence_id}` | P |
| `case.reviewed` | `{domain, decision, reviewer}` | B |
| `campaign.new_domain` | `{campaign_id, domain}` | C |

## Package notes

**P, deep pipeline.** The sandbox additionally returns page text, form fields, and `tel:` and WhatsApp links. Reasons and weights: brand name in a non-official domain 40, credential form 25 (changed from 30 so that a login page alone is not "warn"), brand named as a whole word in the page 20, registered under 30 days ago 15, page facts unavailable 30; a brand lookalike with a credential form scores at least 70. RDAP comes from `rdap.org` for the domain and the resolved IP. Cloudflare is detected from its published IP ranges or `*.ns.cloudflare.com` name servers. If RDAP fails the record says `rdap_status: failed` and the fields stay null. `/v1/report` also queues a deep check.

**A, evidence, fix 1.** The Jinja2 environment uses autoescape. The WeasyPrint URL fetcher refuses every URL except the `data:` URI our own code builds from the local screenshot file. The agent must confirm against the installed WeasyPrint version how `data:` URIs reach the fetcher. Tests: a title of `<script>` and `<img src="http://169.254.169.254/…">` renders as text and the fetcher records zero outside requests; altering one stored row makes verify name that row.

**C, campaigns.** Entity kinds tonight: `domain`, `ip`, `ns`, `registrar`, `phone`, `whatsapp`, `payment`. Strong: phone, whatsapp, payment, and an IP that is not behind a proxy. Weak: ns, registrar, proxied IPs, and any entity with `domain_count > 50` (the hub rule). Only strong links merge; on a merge the oldest campaign id wins and the merge is audited. `country` is not an entity kind, and a test asserts it. "Confirm all" calls `apply_decision` once per domain and skips official and allowlisted domains.

**D, takedown and helplines.** Packs are built only for domains with `confirmed_by='officer'` and an evidence record. Each zip holds one folder per domain (`evidence.pdf`, `evidence.json`, `screenshot.png`), one `email.txt` in Arabic and English, and `manifest.sha256`. Report notes are never read by this package. Helpline numbers come from captured pages only, because no Maps source exists and adding one needs a paid key.

**E, console.** Adds `vue-router`, `cytoscape` and `vitest`. Pages: sign-in, queue with filters, case card, campaigns, campaign detail, takedowns, helpline numbers, live feed, chain check. No `v-html` anywhere. A `defang()` helper renders every domain and URL as plain text (`tamm-pay[.]xyz`). Screenshots and downloads are fetched with the token and shown from blob URLs. Arabic sets `dir="rtl"`; CSS uses logical properties. No sample data in `src/`; empty states instead.

**F, events, location, fix 5.** Hunter posts matches to `/v1/check` with source `hunter`, deduplicated and capped per minute. Safe Browsing is polled only inside a watchlist run; VirusTotal only when `vt_checked_at` is over 24 hours old. Both are skipped when the key is empty. `location()` returns "behind a proxy, true host unknown" in place of a country when `proxy` is set.

## Docker safety

Every compose command uses `-p kartoshka-police`, including the scripts after B0. No prune commands, no `down -v`. Nothing outside this project is stopped or changed. If port 8000 or 5173 is taken, `CORE_PORT` or `CONSOLE_PORT` changes in `.env`.

## Verification

Run by the main session; only failing output is read.

1. `make up` healthy, `make test` green.
2. Report `https://example.com` through `/v1/report`, wait for the deep check, see the case in `/v1/admin/queue`.
3. Confirm it: `/v1/blocklist` lists it, `audit_log` has `case.confirm`, `/v1/check` returns block.
4. Report and reject `https://example.org` with a reason: not on the blocklist, reason stored. Then reject `example.com` too, so the dev blocklist is left clean.
5. `GET /v1/admin/evidence/verify` returns intact; the tamper test passes.
6. Download the evidence PDF; the hostile-title and internal-image test passes.
7. Graph tests: shared phone gives one campaign; shared large-provider name servers do not; hub rule test.
8. Build a pack for the confirmed domain and check `manifest.sha256` with `shasum -c`; an unconfirmed domain gets 409.
9. Helpline CSV formula test passes.
10. Console through Playwright: AR/EN flips `dir`, an HTML title shows as text, domains are defanged, no console errors.
11. `test_admin_auth.py`: every `/v1/admin` route returns 401 without the token.

## Known limits

- The console is bound to 127.0.0.1 and the shared write token ships in its bundle. It is not officer authentication.
- The Safe Browsing key travels as a URL query parameter to Google, because that endpoint ignores the header. It is kept out of our logs.
- Clustering uses features the attacker controls (phone numbers, payment hosts, addresses). A campaign is advice for the officer: membership never blocks a domain, and "Confirm all" writes one decision per ticked domain.
- The lookalike rule misses a brand glued to a non-keyword (`tammpay.xyz`), character swaps and non-ASCII names in the domain. Those sites still score through the credential-form and page-text signals.
- A deep check that raises (sandbox error, code reload) is not retried and its check stays `pending`.
- One worker handles about two to four deep checks a minute; Hunter submits at most `HUNTER_SUBMIT_PER_MIN`.
- The evidence PDF has Latin and Arabic fonts only; other scripts in captured page text print as boxes.
- `data/brands.yaml` official phone numbers were read from the web and need a human check (TAMM `800555` is weakly sourced).
- One case per host; no public-suffix grouping.
- Evidence is append-only by convention and detected by verify; there is no database trigger.
- No scheduler: watchlist checks run on demand.
- Arabic email and label text is machine-written and needs a native proofread.
- Helpline numbers come from captured pages only.

## Open items for the team

- **Official phone numbers.** Confirm UAE PASS `600561111` (read on the u.ae page for the UAE PASS app) and TAMM `800555` (seen only on an error page of tamm.abudhabi/en/contact-us) against the official sites.
- **Arabic text.** Console labels, scoring reasons and the takedown email need a native proofread.
- **Scoring weights and ranking.** `core/app/deep/score.py` and `rank_case` in `core/app/admin/cases.py` are short and are product decisions; review the values.
- **Demo data.** The dev database holds real Hunter candidates and the `example.com` and `example.org` verification cases (both rejected as `test_or_internal`). The team's own lookalike test domain is still needed for a block-level demo case.

## Next steps (out of scope tonight)

Campaign merge, exclude and rebuild job; campaign PDF; pivot search; takedown state machine, kanban, SLA and offline detection; aeDA and Safe Browsing recipients; registrar ranking; KPI, model-quality and system-health pages; list editing and appeals; alerts; officer copilot; AI origin indicators; Tranco import; Maps listings source; favicon, kit and certificate entities; watchlist scheduler; real officer sign-in; discovery source detail (certificate stream, Maps, ads) on the case API.

## Restyle (2026-11-24)

Status: built and verified. Frontend only, `console/` plus this section. No backend change. Console tests 61 (were 10), `make test` green.

The console takes the layout of `docs/design/Phishing review queue redesign.pdf`: top bar, side menu, stat strip, searchable queue on the left, case card on the right, in the PDF's light and dark palettes (following the OS setting).

### Decisions

| Topic | Decision |
|---|---|
| Header | "Kartoshka-Police · Officer Console", EN / العربية switch, "Demo Officer". Demo banner kept. No police name, crest, unit or officer names. |
| Menu | Review queue (count), Hunter live feed, Campaigns, Fake helplines, Takedowns, Evidence chain, Audit log. |
| Stat strip | Awaiting review (`/queue`), auto-confirmed today (`/audit`, `case.auto_confirm`), chain status (`/evidence/verify`), median lead time. A figure with no data is not rendered. |
| Brand chips | `brands.yaml` has no category, so chips are All, High risk (score >= 70) and one per brand found in the loaded queue. |
| Status | `open`: "suspected phishing page". `confirmed`: "confirmed". Auto-confirmed stays "suspected" with a note until an officer confirms. |
| Score | The API score only. Reports never contribute; they show in the reports panel and order the queue through `rank`. |
| Reasons | Every reason with weight and source, in the current language, under a one-line summary. |
| Lead time | Shown only when a real Safe Browsing or VirusTotal lookup was made for the case (`state` is `ahead` or `hit`). Otherwise absent, on the card and in the strip. |
| Median lead | Computed in the browser once per session from at most 30 watched cases, after the queue has rendered, never blocking. Shown as "at least N h, K cases". |
| Chain wording | "record N", never "block N". |
| Hosting | "Unknown, behind a proxy service", no country, when the host is proxied. |
| AI summary | Panel built against an optional `summary: {en, ar}`; hidden because the API does not send it. |
| Shortcuts | J and K move, C arms the confirm and Enter commits it, Escape cancels, R goes to the reject reason. |
| Row tag | First match of: confirmed campaign with domain count, data the page requests, report count, discovery source, behind a proxy. Structured fields only. |

### Packages

| Pkg | Phase | Owns | Builds |
|---|---|---|---|
| S | 0 | `style.css`, `App.vue`, `i18n.ts`, `types.ts`, `router.ts`, `stats.ts`, `StatStrip.vue`, `AuditView.vue` stub | Tokens, shell, stat strip, all strings, types. |
| Q | 1 | `QueueView.vue`, `rowTag.ts`, their tests | Queue page and shortcuts. |
| C | 1 | `CaseCard.vue`, `CaseTitle.vue`, `LocationLines.vue`, `BlobImage.vue`, `CaseCard.test.ts` | Case card. |
| F | 1 | `FeedView.vue` | Hunter live feed. |
| G | 1 | `CampaignsView.vue`, `CampaignView.vue`, `CampaignGraph.vue` | Campaigns. |
| H | 1 | `HelplinesView.vue`, `TakedownsView.vue` | Fake helplines, takedowns. |
| E | 1 | `ChainView.vue`, `AuditView.vue` | Evidence chain, audit log. |
| R | 2 | nothing | Review by a Sonnet agent that wrote none of it. |

Same rules as above: Sonnet subagents write, the main session verifies and commits, strict file ownership, the Docker safety rule applies unchanged.

### Verification

- `make test`: all suites pass; the console has 61 tests and a type-checked build.
- Browser (Playwright, `127.0.0.1:5173`), English and Arabic, light and dark: queue, case card, live feed, campaigns, helplines, takedowns, chain and audit log render with the dev data and with empty data (empty lists returned by request interception, nothing deleted). Arabic sets `dir="rtl"`. No console errors or warnings.
- A page title and a report note containing HTML render as text; no element is created from them.
- Confirm with C then Enter, checked on the reserved domain `restyle-tamm-pay.example`: it reached `/v1/blocklist`, was then rejected as `test_or_internal`, and left the blocklist. The review and audit rows remain.
- Undo of an auto-confirm, the proxy hosting line, the lead-time lines, the AI summary panel and the median figure were checked against intercepted responses, because the dev database has no auto-confirmed case, no proxied case, no Safe Browsing or VirusTotal key and no summary field. With the keys unset, lead time is absent on the card and in the strip.
- Median lead time: 35 watched targets produced exactly 30 case requests, started after the queue request; a second load made none.
- Not checked in a browser with real data: a campaign, the campaign graph, a fake helpline row, a real screenshot in the new frame.

### Known limits

- `brands.yaml` has no category, so there is no category chip.
- The API sends no AI summary; the panel stays hidden until `summary: {en, ar}` exists on the case detail.
- The queue response lacks campaign status and domain count, the data a page requests, and the proxy flag, so the row tag shows only the report count or the discovery source today. `rowTag()` already handles the other three.
- Reports carry no per-report channel; the card shows the case-level `sources` only. Gatekeeper, share and paste are translated if the API ever sends them.
- Median lead time samples at most the 30 most recently watched cases and is computed once per browser session.
- Auto-confirmed today reads the newest 500 audit entries.
- The review independent of the authors found a confirm that could reach the previously selected case while the next one loaded, a reject reason carried between cases, and a double post on a double click. All three are fixed and tested.
- The dev database now also holds `restyle-uaepass-verify.example` and `restyle-plain-shop.example` (open) and `restyle-tamm-pay.example` (rejected), created for this verification.

## Stage 2 (2026-11-24)

Scope: `console/` only, on `feat/console-stage2` from `main` after the feat/app merge. Six screens from feat/app's older console, rebuilt in the restyled design. No backend change.

1. Foundation first: grouped side menu (Review, Detection, Insights, System), types, adapters with fixtures from the running API, and all i18n keys. One owner for `router.ts`, `App.vue`, `nav.ts`, `i18n.ts`, `types.ts`, `adapt.ts`, `style.css`.
2. Then one package per screen with its own files: Impact, Model quality, Hunter watchlist (on the feed page), Campaign actions, Health (page and top-bar strip), Takedown extras. A screen gets its route and menu entry only after its browser check.
3. Impact: totals, an inline SVG chart (no chart library is installed) with the same numbers in a table, and lead time only for cases whose Safe Browsing or VirusTotal lookup really ran (`lead_time.state` of `ahead` or `hit` on the case), worded "at least N h, K cases".
4. Model quality: per-band table from `/v1/admin/stats`, a disagreement list derived from the newest 500 audit entries (system said block and the officer rejected, or allow and confirmed), and URL-model metrics with row counts. Dataset name, dataset date and held-out show "not stated": the API does not send them.
5. Watchlist: attempts, page state, next re-check. The API has no credential-form flag, so `live` rows are looked up on the case (`page.asks_for`) and `watchlist.woke` events highlight at once.
6. Campaign actions: merge and exclude need a reason and a confirm step and are audited by the backend. Pivot is a read-only search (the route writes nothing); official and allowlisted domains show as refused.
7. Health: `/v1/admin/health` on a page and a compact strip, a single dot under 700px. Only the AI key state is reported by the API; other keys show "not stated".
8. Takedown extras: stats, states after "sent", a detail panel with the request's audit rows, and "Check now". "Verifying, N of 2" until the backend closes the request; the 2 mirrors `TAKEDOWN_OFFLINE_CHECKS`, which the API does not expose.
9. No drawer or modal exists in the design: detail panels use the two-column `.split` layout, confirmations use the armed-button pattern with a reason field.
10. Tests: one vitest file per package, run once. One review pass, one round of fixes, then `make test` once.
