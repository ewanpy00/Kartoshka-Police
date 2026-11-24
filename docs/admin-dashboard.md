# Kartoshka-Police admin dashboard: build plan

Status: approved and built on 2026-11-24, and merged into `main`. The build log, including later changes, is in `docs/admin-plan.md`.

The admin dashboard is the Officer Console (`console/`), slice 5 of `docs/app-plan.md`, extended with campaigns, a takedown tracker and operational pages. The design rationale is in the proposal on the `docs` branch (`docs/admin-panel.md`); this file holds the build contract. ARCHITECTURE.md section 5 summarises it.

## Context

What already exists on `feat/app` and is reused, not rebuilt:

| Piece | Where | State |
|---|---|---|
| Write-token gate | `core/app/auth.py:require_write_token` | constant-time compare; an unset token rejects everything |
| Review route | `POST /v1/review/{evidence_id}` in `core/app/main.py` | records `decision` and `reviewer`; no reason field, no blocklist delta yet |
| Live events | `WS /v1/events` in `core/app/main.py` | accepts and sends `hello`; nothing is published yet |
| Console proxy | `console/vite.config.ts` | `/api` to core with `ws: true`; the prefix is stripped |
| Tables | `core/app/models.py` | `checks`, `domains`, `evidence`, `entities`, `edges`, `campaigns`, `watchlist`, `reviews`, `feed_entries`, `reports`, `hits`, `model_state` |
| Campaign boost | `core/app/fast/intel.py:campaign_links` | already counts only campaigns with `confirmed_count > 0` |
| RDAP | `core/app/fast/rdap.py` | registry server from the IANA bootstrap; parses `registrar`, `abuse_emails`, `nameservers`, `status` |
| URL model (A1) | `core/app/ai/url_model.py` | optional LightGBM, stored in `model_state` |

Not there yet and owned by other slices of `docs/app-plan.md`: the deep path, evidence writing and graph edges (slice 2), the page LLM (slice 4). Dashboard slices that need them say so.

## Slices

Each slice is verified in the running stack and committed on its own. D1 is the slice-5 deliverable; the rest are ordered by judging weight and demo value.

| # | Slice | Main paths | Done when |
|---|---|---|---|
| D1 | Review queue: mock sign-in, unified queue of cases, case card, confirm and reject with a reason and a blocklist delta, live Hunter feed, chain check | `core/app/api/admin.py`, `core/app/admin/queue.py`, `console/src/pages/{Login,Queue,Case,Hunter}.vue` | An officer confirms a domain from the queue and `GET /v1/blocklist?since=` returns it within a minute; "Verify chain" reports the record count and `ok` |
| D2 | Campaigns, backend: entity extraction, strong and weak links, hub rule, incremental clustering, rebuild job | `core/app/graph/{entities,cluster,rules}.py` | Two test domains sharing a phone number land in one campaign; two sharing only a Cloudflare IP do not |
| D3 | Campaigns, console: list, detail with graph and domain table, node pivot, confirm all, exclude, merge | `core/app/api/admin_campaigns.py`, `console/src/pages/{Campaigns,Campaign}.vue`, `console/src/components/CampaignGraph.vue` | The console shows one campaign as a graph, and "Confirm all" writes one review per ticked domain |
| D4 | Takedown, backend: recipients, pack, request states, watchlist offline detection | `core/app/takedown/{contacts,pack,tracker}.py`, `core/app/jobs.py` | A pack zip downloads with a manifest whose hashes match; deleting a test domain's DNS record moves its request to `closed` after two checks |
| D5 | Takedown, console: tracker board, detail drawer, "mark as sent", "check now", stats | `core/app/api/admin_takedowns.py`, `console/src/pages/Takedowns.vue` | The demo in section "Demo" runs end to end |
| D6 | Impact and health: KPI page with lead time (incl. against GSB and VirusTotal), model-quality page, system health strip | `core/app/admin/stats.py`, `console/src/pages/{Impact,Quality}.vue` | The KPI page shows lead time for every confirmed domain that has a CT sighting |
| D7 | Stretch: campaign PDF, registrar ranking, lists and appeals with audit, fake-helpline export, manual check page | various | each item works on its own; anything unfinished goes on the next-steps slide |

## Fixed interfaces

### Auth

- Every `/v1/admin/*` route depends on `require_write_token`, reads included. Reads expose score weights and Hunter internals, which residents never see (ARCHITECTURE section 3.1).
- The console sends the token through its one fetch wrapper. The resident app (`resident/`) never calls `/v1/admin/*` and never holds the token.
- The reviewer name comes from the mock sign-in session and is sent in each write body. The console stays on `127.0.0.1` (`docs/app-plan.md` decision 8), because the token ships in the client bundle (`docs/devops-plan.md` decision 4).

### Review route change

`POST /v1/review/{evidence_id}` gains a required `reason` on reject and an optional `note`:

```json
{"decision": "confirm" | "reject", "reviewer": "Demo Officer",
 "reason": "legitimate_site" | "not_a_scam" | "insufficient_evidence" | "duplicate" | null,
 "note": "free text, officer-only"}
```

- Confirm sets `domains.status = confirmed`, `source = officer`, `brand_id` from the check, and bumps `updated_at`, so the blocklist feed picks it up. Reject sets `cleared` only when the reason is `legitimate_site` or `not_a_scam`.
- Both write a `verdicts` row with `stage: "officer"` and an `audit_log` row, and publish `case.reviewed`.
- The reject reason maps to the resident's "My reports" text ("Reviewed: looks legitimate"). The free-text note never leaves the console.
- If `docs/app-plan.md` slice 3 has already added the blocklist delta, D1 only adds `reason`, `note` and the audit row.

### Admin routes

```
GET  /v1/admin/queue?source=&brand=&band=&has_reports=&auto=&cursor=
GET  /v1/admin/cases/{domain}
POST /v1/admin/cases/{domain}/recheck
POST /v1/admin/cases/{domain}/watch
GET  /v1/admin/hunter/feed?since=&brand=&source=
GET  /v1/admin/watchlist
GET  /v1/admin/evidence/verify
GET  /v1/admin/campaigns?status=&brand=&active=
GET  /v1/admin/campaigns/{id}
GET  /v1/admin/campaigns/{id}/graph
POST /v1/admin/campaigns/{id}/confirm      {domains[], reviewer, note}
POST /v1/admin/campaigns/{id}/pivot
POST /v1/admin/campaigns/{id}/exclude      {domain, reviewer, reason}
POST /v1/admin/campaigns/merge             {ids[], reviewer, reason}
GET  /v1/admin/entities/{kind}/{value}
GET  /v1/admin/takedowns?status=&recipient=
POST /v1/admin/takedowns                   {domains[]}
GET  /v1/admin/takedowns/{id}/pack.zip
POST /v1/admin/takedowns/{id}/sent         {reviewer}
POST /v1/admin/takedowns/{id}/recheck
GET  /v1/admin/takedowns/stats
GET  /v1/admin/stats?range=24h|7d
GET  /v1/admin/health
GET  /v1/evidence/campaign/{id}.pdf        (D7)
```

Lists are cursor-paginated, 50 rows per page. Every domain in every response carries both the raw value and a `display` value defanged by the server (`tamm-pay[.]xyz`).

### Queue

A case is a registrable domain. The queue is a SQL query, not a table: `checks` with verdict `warn` or `block`, plus every domain with a resident report or a Hunter feed entry, minus domains whose `domains.status` is `official`, `allowlisted`, `confirmed` or `cleared` (confirmed domains stay visible under the `auto` filter until reviewed).

```
priority = score × ln(1 + reports + hits) × freshness × band_boost
freshness  = 0.5 ^ (hours since the latest sighting / 24)
band_boost = 1.3 for scores 30–70, else 1.0
```

`reports` counts `reports` rows for the domain; `hits` sums `hits.count` across channels. The 30–70 boost puts the cases whose labels teach the model most at the top (A7).

The case payload holds: the latest check (verdict, score, reasons, `sources[]`, features), the preview screenshot path, RDAP and infrastructure, discovery (first `feed_entries` row per source), report count and report notes, hits per channel, campaign id and size, previous reviews.

### Live events

Core publishes JSON on the Redis channel `kp:events`; `WS /v1/events` subscribes and forwards. Types:

| Type | When | Payload |
|---|---|---|
| `hunter.candidate` | a `feed_entries` row is inserted | source, domain, brand_id, first_seen |
| `check.verdict` | a check reaches warn or block, fast or deep | check_id, domain, verdict, score, stage |
| `case.reviewed` | review written | domain, decision, reviewer |
| `watchlist.woke` | a parked watchlist domain now serves a form | domain, check_id |
| `brand.spike` | 10 or more new candidates for one brand within an hour | brand_id, count |
| `campaign.new_domain` | a domain joins a campaign | campaign_id, domain |
| `takedown.offline` | a request moves to `closed` or `reopened` | request id, domain, offline_reason |

The WS endpoint checks the token passed as the `token` query parameter, because browsers cannot set headers on a WebSocket.

### Campaign graph rules (D2)

Entity kinds and link strength:

| Kind | Strength | Notes |
|---|---|---|
| phone, whatsapp, payment | strong | normalised: E.164 for phones, host plus path for payment endpoints |
| kit_hash, favicon_hash | strong | favicon hashes of common CMS and hosting defaults are on a deny list and count as weak |
| cert | strong only for a multi-SAN certificate shared by the domains | single-domain Let's Encrypt certificates link nothing |
| ip | strong when dedicated | weak when its ASN is a CDN or large cloud (13335 Cloudflare, 20940 and 16625 Akamai, 54113 Fastly, 16509 Amazon, 15169 Google, 8075 Microsoft) |
| asn, registrar, ns | weak | shown, never merge |

- **Hub rule:** an entity shared by more than `GRAPH_HUB_DEGREE` domains (default 50) is treated as weak from then on. `entities.domain_count` is kept up to date on every new edge.
- **Clustering** runs after each deep analysis, through strong edges only. No campaign found: a new campaign row once at least two domains share a strong entity. One found: join. Several found: merge into the oldest id, re-point edges, write `audit_log`.
- `excluded` edges are ignored by clustering. `python -m app.graph.cluster rebuild` recomputes all campaigns from scratch.
- A campaign with `confirmed_count = 0` is shown as suspected. Names come from a template: brand, the common domain pattern, start date.
- Official domains, allowlisted domains and the Tranco list never join a campaign.

Graph response for cytoscape:

```json
{"nodes": [{"id": "d:tamm-pay.xyz", "kind": "domain", "label": "tamm-pay[.]xyz", "status": "confirmed", "score": 92}],
 "edges": [{"source": "d:tamm-pay.xyz", "target": "ip:185.x.x.x", "strength": "strong"}],
 "collapsed": [{"kind": "ip", "count": 140}]}
```

Above 200 nodes the server collapses infrastructure nodes by kind; weak edges are present but hidden by default in the client.

### Bulk confirm (D3)

- The client sends the ticked domains; domains scoring below 70 arrive unticked.
- The server refuses any domain that is official, allowlisted or in the Tranco list, even if ticked, and says which.
- Each remaining domain gets its own `reviews` row against its latest evidence, its own `verdicts` row and its own blocklist update. The note records the campaign id.

### Takedown (D4, D5)

Recipients, one request each (`takedown/contacts.py`):

| Recipient | Source |
|---|---|
| registrar | `abuse_emails` from the domain's RDAP record |
| hosting provider | RDAP for the IP through the IANA IPv4 and IPv6 bootstrap, contact with the `abuse` role |
| Cloudflare | instead of the host when the IP is in AS13335 or the name servers end in `.ns.cloudflare.com`; a form link, not an email |
| aeDA (TDRA) | `.ae` domains |
| Google Safe Browsing | always; a form link |

Pack (`takedown/pack.py`), one zip per recipient covering every domain sent to that recipient:
- `evidence/<domain>.pdf`, `evidence/<domain>.json`, `screenshots/<domain>.png`;
- `email.txt`: To, Subject and body in Arabic and English from a template;
- `manifest.sha256` listing every file.

The zip's SHA-256 is stored on the request. Resident report notes are never included.

States: `pack_ready → sent → offline_pending → closed`, and `closed → reopened` when the site comes back. `overdue` is derived (`sent_at` older than `TAKEDOWN_SLA_H`), not stored. Packs are generated only for domains confirmed by an officer; an auto-confirmed domain must be reviewed first. Nothing is sent automatically: "Send" opens a `mailto:` link and downloads the zip, and the officer then presses "Mark as sent".

Offline detection (`jobs.takedown_recheck`, scheduled from the watchlist):
- After `sent`, the domain is re-checked every `TAKEDOWN_RECHECK_MIN` minutes (default 60) instead of every 6 hours.
- Offline signals, stored as `offline_reason`: `nxdomain`, `servfail`, `rdap_hold` (RDAP status `client hold` or `server hold`), `http_gone` (404 or 410), `refused`, `parked`, `cf_interstitial`, `form_removed`.
- `offline_pending` after the first offline result; `closed` after `TAKEDOWN_OFFLINE_CHECKS` consecutive offline results (default 2) at least one interval apart, each with both the bot and the phone profile.
- After `closed` the domain stays on the blocklist and on the watchlist for 30 more days; a live result moves the request to `reopened` and publishes `takedown.offline`.
- Each re-check also queries GSB and VirusTotal when their keys are set and records the first hit (`gsb_first_hit_at`, `vt_first_hit_at`).

### Migration `0003_admin`

| Change | Columns |
|---|---|
| new table `takedown_requests` | id, domain, campaign_id, recipient_kind, recipient, status, pack_sha256, generated_at, sent_at, sent_by, offline_at, offline_reason, checks_offline, note |
| new table `audit_log` | id, actor, action, target_kind, target, before (JSON), after (JSON), reason, created_at |
| `reviews` | add `reason` |
| `entities` | add `domain_count` |
| `edges` | add `strength`, `excluded` (default false) |
| `campaigns` | add `last_activity_at` |
| `domains` | add `gsb_first_hit_at`, `vt_first_hit_at` |

`audit_log` is append-only with the same kind of trigger as `evidence`.

### Configuration (`.env.example`)

| Variable | Default |
|---|---|
| `TAKEDOWN_SLA_H` | `48` |
| `TAKEDOWN_RECHECK_MIN` | `60` |
| `TAKEDOWN_OFFLINE_CHECKS` | `2` |
| `GRAPH_HUB_DEGREE` | `50` |
| `BRAND_SPIKE_PER_HOUR` | `10` |

### Console structure

Vue 3 with `vue-router`; `cytoscape` with `cytoscape-fcose` for the graph; `chart.js` for the KPI page. Pin exact versions at install time and commit `package-lock.json`.

```
console/src/
  api.ts                 the one fetch wrapper (token), plus the WS client
  router.ts
  session.ts             mock UAE PASS session
  pages/  Login Queue Case Hunter Campaigns Campaign Takedowns Impact Quality Health
  components/  CaseCard CampaignGraph StatusBadge DefangedDomain HealthStrip
  i18n/  en.ts ar.ts      RTL when Arabic is active
```

Queue shortcuts: J and K move, C confirms, R opens the reject reasons, D re-runs deep analysis, W adds to the watchlist.

## Decisions

1. **One queue, one case per domain.** Reports, Hunter candidates and warn or block checks share one ranked list instead of separate pages.
2. **AI never decides in the dashboard.** The page LLM (A2) fills the case card with extracted facts and bilingual reasons, marked "AI"; the URL model (A1) feeds ranking; officer decisions are stored as labels for A7. Confirm, reject, campaign merges and takedown sending are human or deterministic. Kit similarity by embeddings (A5) and the officer copilot (A6) stay deferred, as in the brief; when added, A5 suggests "looks like cmp_17" and never merges.
3. **Only strong links merge campaigns.** CDN IPs, ASNs, registrars and big name servers would otherwise join unrelated sites into one campaign, and a bulk confirm could block a legitimate site.
4. **Takedowns are prepared, not sent.** The brief requires the request to come from the police after review.
5. **Offline needs two checks with both profiles,** so geofencing and cloaking cannot fake a takedown.
6. **Attacker-controlled text is rendered as text.** Page titles, page text, URLs and report notes never go through `v-html`. Domains are shown defanged and are not links. Screenshots are served as PNG from core.
7. **GSB and VirusTotal stay score signals,** not a confirmed list. The dashboard records when they first flag a domain we already found, which gives the lead-time number for the deck.

## Tests

- Core (pytest, rolled back like the existing tests):
  - every `/v1/admin/*` route returns 401 without the token;
  - queue ranking order on a fixed fixture, and exclusion of official, allowlisted and decided domains;
  - review confirm updates `domains` and the blocklist feed; reject without a reason returns 422;
  - clustering: shared phone merges, shared Cloudflare IP does not, hub rule kicks in above the threshold, merge keeps the oldest id, excluded edges are ignored;
  - bulk confirm refuses an allowlisted domain and writes one review per domain;
  - pack manifest hashes match the files, and no report note appears in the zip;
  - takedown state machine: one offline result gives `offline_pending`, two give `closed`, a live result after `closed` gives `reopened`;
  - `audit_log` rejects updates and deletes.
- Console: `npm run build` passes (type check included).
- Manual, in the running stack: the D1 and D5 "done when" checks and the demo below.

## Demo

No real takedown will happen overnight, and the demo must not use invented data. It uses the team's own test look-alike domain from `docs/app-plan.md` slice 7 (Hunter):

1. The domain's certificate appears in the live Hunter feed, then in the queue.
2. The officer opens the case card and confirms; the blocklist feed shows the domain.
3. The campaign page shows it linked to the other test domain through the shared phone number.
4. "Takedown packs" builds the pack; the officer marks it sent.
5. The team deletes the domain's DNS record; "Check now" twice moves the card to `closed` with `offline_reason: nxdomain`.

## Progress

- 2026-11-24: plan written and approved.
