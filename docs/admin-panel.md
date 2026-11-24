# Kartoshka-Police admin panel: proposal

Status: proposal, not built. Written 2026-11-24.

This proposal extends the Officer Console (`console/`, slice 5 in `docs/app-plan.md` on `feat/app`). Code references such as `core/app/fast/score.py` point at the uncommitted `feat/app` work, not at `main`.

## Contents

1. Where it lives
2. Review queue
3. Early detection
4. Campaign page
5. Takedown tracker
6. Other pages
7. Security
8. How this improves detection and reduces fraud
9. Why Google Safe Browsing and VirusTotal are not enough
10. Metrics and limits
11. Build order

---

## 1. Where it lives

The admin panel is the Officer Console, not a separate app. The console is already in compose, Vite proxies `/api` to core, and the write token is wired. Most data already exists in the models: `reports`, `feed_entries`, `checks`, `watchlist`, `campaigns`, `entities`, `edges`, `reviews`, `hits`, `evidence`.

- **Frontend.** Vue 3 with vue-router and the pages below. The campaign graph uses cytoscape.js with the fcose layout. Charts use Chart.js. The UI has an AR/EN switch with an RTL layout.
- **Backend.** A new router, `core/app/api/admin.py`. Every `/v1/admin/*` route sits behind the same `require_write_token` dependency. Today the token guards writes only, but the queue reveals score weights and Hunter internals, which residents must never see (ARCHITECTURE section 3.1).
- **Live updates.** Core and Hunter publish events to Redis pub/sub, and `WS /v1/events` (already in the API plan) pushes them to the console. The `/api` proxy in `vite.config.ts` needs `ws: true`.
- **Database.** Migration `0003` adds the tables and columns listed in sections 4 and 5. The review queue is a SQL query over `checks` grouped by domain, not a table.

```
GET  /v1/admin/queue?source=&brand=&band=   ranked cases
GET  /v1/admin/cases/{domain}               checks, reports, evidence, campaign, hits
POST /v1/review/{evidence_id}               exists: confirm or reject, with a reason
POST /v1/admin/cases/{domain}/recheck       queue a new deep analysis
GET  /v1/admin/hunter/feed · /watchlist · /stats · /health
GET  /v1/admin/evidence/verify              hash-chain check
WS   /v1/events
```

---

## 2. Review queue

There is no separate "user reports" page. There is **one queue of cases, and one case is one domain**. It takes resident reports, Hunter candidates, checks with a warn or block verdict, and auto-confirmed domains. Fifty reports about one domain become one case, not fifty rows.

- **Ranking:** `score × log(1 + reports + hits) × freshness`, as in ARCHITECTURE section 5. Cases in the 30–70 band get a boost, because officer decisions on them are the most useful labels for retraining (A7).
- **Filters:** source, brand, band, "has reports", "auto-confirmed, awaiting review".
- **Case card:**
  - left: the screenshot from the Arabic phone profile;
  - right: reasons in Arabic and English, and `sources[]`;
  - infrastructure: RDAP, IP and ASN, name servers, certificate;
  - discovery source, campaign, notes from reports, block counters.
- **Actions:**
  - Confirm;
  - Reject, with a reason picked from a list. The same reason appears on the resident's "My reports" timeline;
  - run deep analysis again;
  - add to the watchlist.
- **Keyboard shortcuts** J/K/C/R, so triage looks fast in the demo.
- **Auto-confirmed** domains (deep score above 90 with a credential form) have their own filter and an undo button.

```
┌ Queue · 127 ────────────────────┐ ┌ tamm-pay[.]xyz · 92 · block · TAMM ────────────┐
│ ▸ tamm-pay[.]xyz    92  CT    4 │ │ [screenshot] BRAND_IN_DOMAIN           +30     │
│   uaepass-ver[.]top 88  user 12 │ │ [AR phone  ] DOMAIN_AGE 2 days         +20     │
│   adcb-secure[.]co  64  maps  1 │ │              asks for: card · CVV · OTP        │
│   …                             │ │ found CT 14:02 · 4 reports · campaign cmp_17   │
└─────────────────────────────────┘ │ [C] Confirm  [R] Reject ▾  [D] Deep  [W] Watch │
                                    └────────────────────────────────────────────────┘
```

---

## 3. Early detection

- **Live Hunter feed.** `feed_entries` in real time from CT, Search, ads, Maps and threat feeds, filtered by brand and source. Each row shows its path: candidate → fast score → deep → verdict.
- **Brand spikes.** For example, 15 new domains containing `tamm` within an hour almost certainly mean a campaign launch, and should raise an alert.
- **Watchlist wake-ups.** The most valuable signal: a parked domain suddenly serves a login form. That case goes straight to the top of the queue, often before the first SMS is sent.
- **Lead time.** For each confirmed domain, how many hours the CT `first_seen` came before OpenPhish or URLhaus, before Google Safe Browsing (section 9), or before the first resident report. The deck needs this number (slice 7), and the dashboard computes it live.

---

## 4. Campaign page

### 4.1 How campaigns are built (backend)

This is the main part; the page only displays the result. `core/app/graph/` and `core/app/evidence/` are still empty, so this is new code.

1. **Entity extraction** (`graph/entities.py`). After a deep analysis, extract nodes from the capture and the infrastructure data: domain, ip, asn, ns, registrar, cert, kit_hash, favicon_hash, phone, whatsapp, payment. Each domain gets edges to its nodes.
2. **Strong and weak links.** Without this split everything merges into one giant campaign through Cloudflare, Let's Encrypt and NameCheap.
   - **Strong** links merge domains into a campaign: the same phone number, payment endpoint, kit_hash or favicon_hash, a shared multi-SAN certificate, a dedicated IP.
   - **Weak** links are shown but never merge: ASN, registrar, name servers of large providers, IPs in CDN ranges.
   - **Hub rule:** a node shared by more than about 50 domains becomes weak automatically.
3. **Clustering** (`graph/cluster.py`). A new domain looks up existing campaigns through its strong nodes:
   - none found: a new candidate cluster is created;
   - one found: the domain joins it;
   - several found: the campaigns merge, the oldest id is kept, and the merge is written to the audit log.

   A "rebuild from scratch" job repairs any drift.
4. **Campaign status.** A cluster with no confirmed domain is a suspected campaign; after the first officer confirm it is a campaign. `campaign_links` in `core/app/fast/intel.py` already filters on `confirmed_count > 0`, so only confirmed campaigns raise the score of a new domain.
5. **Name** from a template: brand, pattern, start date, for example "TAMM · tamm-pay-*.xyz · 18 Nov". An LLM summary (officer copilot, A6) is deferred in the brief.

### 4.2 Campaign list

Columns: name, brand, domains (confirmed / suspected / offline), first domain seen, latest new domain (an "active" badge if one appeared in the last 24 hours), takedown progress.

### 4.3 Campaign detail

```
┌ cmp_17 · TAMM · fine payment · active ──────────────────────────────────────┐
│ 14 domains: 9 confirmed · 3 suspected · 2 offline · since 18 Nov · new 2h   │
│ [Confirm 3] [Pivot] [Takedown packs] [Campaign PDF]                          │
├────────────────────────────────────────┬────────────────────────────────────┤
│  graph (cytoscape + fcose)             │ Shared infrastructure              │
│  ● tamm-pay[.]xyz ──■ 185.x.x.x        │  IP 185.x.x.x       11/14 domains  │
│  ● tamm-fine[.]top ─┘                  │  phone +971 5x…      6/14          │
│  ◐ tamm-ae[.]cc ──☎ +971 5x…           │  kit a3f9…          14/14          │
│                                        │  NS Cloudflare      weak link      │
├────────────────────────────────────────┴────────────────────────────────────┤
│ domain            status     score  found      source  takedown             │
│ tamm-pay[.]xyz    confirmed  92     18 Nov     CT      sent 26h ago ⚠       │
└─────────────────────────────────────────────────────────────────────────────┘
```

- **Graph:**
  - domain colour shows status (confirmed, suspected, offline, cleared);
  - strong edges are solid; weak edges are dashed and hidden by default;
  - above about 200 nodes the server collapses nodes by kind.
- **Clicking a node:**
  - a domain opens a mini case card;
  - an IP or a phone opens a pivot: "N more domains on this node", including domains outside the campaign.
- **Where victims meet it** (required by the brief's campaign report): a breakdown by source, from `checks.source` (SMS, share, Gatekeeper), `feed_entries` (CT, Maps, ads) and `hits` per channel.
- **Actions:**
  - **Confirm all.** Shows a checklist; domains scoring below 70 are unticked by default. Each domain gets its own `reviews` row pointing at its own evidence, never one bulk decision. Official and allowlisted domains and the Tranco list are excluded outright, so a legitimate site on the same shared host can never reach the blocklist.
  - **Pivot** queues a search through crt.sh and DNS for the same IP, name servers and certificate. Results enter the queue as Hunter candidates.
  - **Exclude a domain** sets `excluded` on its edges. **Merge campaigns** joins two campaigns by hand.
  - **Campaign PDF:** domain count, start date, brand, shared infrastructure, where victims meet it.

### 4.4 API

```
GET  /v1/admin/campaigns?status=&brand=&active=
GET  /v1/admin/campaigns/{id}              header, domains, infrastructure, timeline
GET  /v1/admin/campaigns/{id}/graph        {nodes[], edges[]} in cytoscape format
POST /v1/admin/campaigns/{id}/confirm      {domains[], note}
POST /v1/admin/campaigns/{id}/pivot
POST /v1/admin/campaigns/{id}/exclude      {domain}
POST /v1/admin/campaigns/merge             {ids[]}
GET  /v1/admin/entities/{kind}/{value}     every domain on a node
GET  /v1/evidence/campaign/{id}.pdf
```

---

## 5. Takedown tracker

The brief says Kartoshka-Police prepares the pack and an officer sends it; automatic submission is deferred. So the tracker is a status log plus an automatic check that the site really went down.

### 5.1 Recipients: one request per recipient

`takedown/contacts.py` collects the recipients:
- **Registrar:** `abuse_emails` from the domain's RDAP record (`core/app/fast/rdap.py` already parses them).
- **Hosting provider:** RDAP for the IP (`rdap.org/ip/{ip}`), the contact with the abuse role.
- **Cloudflare:** when the site is behind it (IP in its ranges or name servers `*.ns.cloudflare.com`), the real host is hidden, so the recipient is Cloudflare's abuse form, which forwards to the host.
- **`.ae` domains:** aeDA (TDRA).
- **Always:** a report to Google Safe Browsing. It puts a warning in every major browser even while the site is still up.

### 5.2 The pack

`takedown/pack.py` builds a zip:
- `evidence.pdf`, `evidence.json`, `screenshot.png`;
- `email.txt` with recipient, subject and body in Arabic and English, from a template;
- `manifest.sha256`.

The SHA-256 of the pack is stored on the request, so it is clear exactly what was sent. Resident report notes are **never** included, because they can hold personal data.

Packs are grouped by recipient. If 12 domains in a campaign share a registrar, that registrar gets one email listing all 12.

### 5.3 States

```
pack_ready → sent → offline_pending → closed
               │                         │
               └→ overdue (> SLA, 48h)   └→ reopened (site came back)
```

- `overdue` is not stored; it is derived from `sent_at` and `TAKEDOWN_SLA_H`.
- "Send" opens a `mailto:` link with subject and body and downloads the zip, since mailto cannot attach files. Form-based recipients (Cloudflare, GSB) get a link to the form and copy buttons.
- "Mark as sent" records `sent_by`, `sent_at` and the pack hash.
- Packs are generated only for officer-confirmed domains. Auto-confirmed domains go through review first: the brief requires takedown requests to come from the police after review.

### 5.4 Detecting that a site is down (watchlist)

After a request is sent, the domain is re-checked hourly instead of every 6 hours. Offline signals:
- NXDOMAIN or SERVFAIL;
- RDAP status `client hold` or `server hold`, meaning the registrar suspended the domain. This is a strong signal and shows who acted;
- HTTP 404 or 410, connection refused;
- a parking page, or Cloudflare's "suspected phishing" interstitial;
- the form is gone from the page.

A site counts as offline only after **two consecutive** failed checks at least one hour apart, with both profiles (bot and phone). Otherwise geofencing or cloaking would produce a false takedown. After closing, the domain stays on the blocklist and on the watchlist for another 30 days in case it comes back.

### 5.5 Tracker page

```
Pack ready (4) │ Sent (7)         │ Overdue (2)      │ Offline, verifying (1) │ Closed (12) │ Came back (1)
tamm-pay[.]xyz │ uaepass-v[.]top  │ adcb-sec[.]co    │ tamm-fine[.]top        │ …           │ …
NameCheap · CF │ 26h / SLA 48h    │ 52h · Hostinger  │ 1 of 2 checks          │             │
```

- **Metrics at the top:**
  - open requests and overdue requests;
  - median time from sending to offline;
  - sites taken down this week;
  - exposure window: from the first certificate to offline, and how many blocks happened in that time.
- **Detail drawer:**
  - recipients, each with its own status;
  - event timeline: pack created, sent, each watchlist check with its result, offline confirmed;
  - "Check now" and "Send again" buttons.
- **Registrar and host ranking:** requests sent, median response time, share with no response. In a pilot this gives the police a concrete argument with slow providers.

### 5.6 API

```
GET  /v1/admin/takedowns?status=&recipient=
POST /v1/admin/takedowns                    {domains[]}  builds packs, grouped by recipient
GET  /v1/admin/takedowns/{id}/pack.zip
POST /v1/admin/takedowns/{id}/sent
POST /v1/admin/takedowns/{id}/recheck
GET  /v1/admin/takedowns/stats
```

### 5.7 How the two pages connect, and migration `0003`

- The campaign page shows "N of M offline", and its "Takedown packs" button creates requests for every confirmed domain at once.
- WS events `campaign.new_domain` and `takedown.offline` update the console live.
- Migration `0003`:
  - new table `takedown_requests`: domain, campaign_id, recipient_kind, recipient, status, pack_sha256, generated_at, sent_at, sent_by, offline_at, offline_reason, note;
  - new table `audit_log`: actor, action, target, before, after, reason, created_at;
  - `entities.domain_count` for the hub rule;
  - `edges.strength` and `edges.excluded`;
  - `campaigns.last_activity_at`;
  - `gsb_first_hit_at` and `vt_first_hit_at` per domain for the lead-time metric (section 9).

---

## 6. Other pages

Judging criteria: C1 detection accuracy 30%, C2 early detection and coverage 25%, C3 explainability and actionability 20%, C4 UAE relevance and innovation 15%, C5 feasibility and presentation 10%.

| Page | What it gives | Criterion |
|---|---|---|
| Impact / KPIs | Blocks per channel (Gatekeeper, DNS), confirmations per day, median "certificate → detection → confirm → blocked on devices", lead time | C2, C5 |
| Model quality | Officer confirm rate per score band (shows calibration) and a disagreement list: rejected cases scoring 70 or more, confirmed cases below 30. Ready-made labels and input for tuning `BATCH_CUTOFF` | C1 |
| Integrity | A "Verify chain" button that answers "1,234 records, chain intact" or names the first broken record. Very clear for the judges | C3 |
| System health | Certstream rate, Hunter heartbeat, RQ queue length, sandbox, VirusTotal and GSB quotas, LLM errors. Also a safety net during the demo | C5 |
| Lists and audit | Edit the allowlist, the blocklist, and brands' official domains and phone numbers; appeals for false positives. Every change goes to `audit_log` with a reason and an author | C1 |
| Fake helpline numbers | Phone numbers from Maps listings and pages that are not in the brand registry, exported for the operators (e&, du) | C4 |
| Manual check | An officer pastes a URL and gets the full X-ray with deep analysis. Nearly free, since `/v1/check` exists | — |

---

## 7. Security

The admin panel shows content an attacker controls: page titles, page text, URLs, report notes.

- Never render these fields with `v-html`; use normal Vue interpolation only.
- Show domains defanged (`tamm-pay[.]xyz`) and not clickable, so an officer cannot open a phishing site by accident. The only way to see a site is the sandbox screenshot.
- Serve screenshots as PNG from our own origin.
- Keep the console on `127.0.0.1`: the write token ships in the client bundle (decision 4 in `docs/devops-plan.md`).

---

## 8. How this improves detection and reduces fraud

The admin panel does not reduce crime by itself. It shortens the cycle "found → confirmed → blocked → taken down", and it turns each officer decision into data that makes detection more accurate.

### 8.1 Detection gets better

Every action in the panel feeds back into detection:

```
Hunter finds → Core scores → officer decides → the decision flows back:
   ├─ into the graph: confirmed domains strengthen the campaign's links
   ├─ into labels: score and cutoff calibration
   └─ into Hunter: which sources and queries produce real findings
```

- **A confirmed campaign catches new domains by infrastructure, not by name.** A name filter cannot see domains like `dwu6.top`. But if a new domain shares an IP, a kit_hash or a phone number with a confirmed campaign, its score rises at once (`campaign_links` in `core/app/fast/intel.py` already does this). More confirmations in the graph mean more coverage.
- **Pivot finds domains nobody has clicked yet.** The search goes from a confirmed site to its neighbours by certificate, IP and name servers. That is early detection, not a reaction to a complaint.
- **Watchlist wake-ups.** Fraudsters register domains in advance and keep them empty. We see the moment a form appears, before the first SMS campaign.
- **Officer–model disagreements are training data.** Rejected cases scoring 70 or more show which rule produces false positives. Confirmed cases below 30 show what the model misses. They drive the weights, `BATCH_CUTOFF` and, per the brief, the future trained scorer. This directly affects detection accuracy (30% of the score).
- **Per-source statistics.** We see how many confirmations come from CT, Maps, ads, feeds and reports. Queries that only produce noise can be dropped; keywords that work can be extended.
- **Sites that come back after a takedown** are linked to the campaign through their new infrastructure, so the next domain is caught faster.

### 8.2 How this hurts fraud operations

- **Shorter site lifetime means fewer victims.** A fraud site pays off in its first hours. The chain "certificate → detection → confirm → blocklist on phones and DNS within a minute → takedown" shrinks that window. The tracker shows it in numbers: how many hours the site was live and how many blocks happened in that time.
- **Hitting the expensive part of the operation, not the cheap part.** A domain costs about $1 and is replaced in minutes. Phone numbers, payment details, kits and hosting accounts cost more. The campaign view exposes exactly those:
  - phone numbers go to the operators (e&, du);
  - payment endpoints go to the banks;
  - all 14 domains of a campaign are taken down together, not one at a time.
- **One case instead of twenty scattered complaints.** An investigation needs linked incidents: one phone, one wallet, one kit. The campaign report with its hash chain remains evidence even after the sites are gone. That is the basis for identifying and arresting suspects, although the arrest itself is police work, not the system's.
- **Pressure on registrars and hosts.** The response-time ranking gives the police an argument with slow providers.
- **Feedback for residents.** A resident sees that their report was confirmed and that the site has since been blocked N more times for others. That encourages reporting again, which gives the system more data.

---

## 9. Why Google Safe Browsing and VirusTotal are not enough

In our code GSB and VirusTotal are not a list of confirmed domains; they are score signals. In `core/app/fast/score.py` a GSB hit adds the reason `GSB_HIT`, and VirusTotal adds `VT_HIT` with weight 20 or 40 depending on the number of engines. The `confirmed` status in the `domains` table is set only by an officer. That is how it should be: VirusTotal is noisy, and 1–2 engines out of 90 sometimes flag legitimate sites.

| | GSB / VirusTotal | Our admin panel |
|---|---|---|
| **When** | Flag a site after someone has noticed it. Fresh phishing against UAE brands is often 0/70 in its first hours | CT catches the domain when its certificate is issued, before the first SMS |
| **UAE coverage** | Do not know fake TAMM helplines on Maps, Arabic phishing, local banks | Brand registry, Maps and ads sweep, Arabic queries |
| **Links** | A verdict on one URL | A campaign: phones, payment details, kit, hosting |
| **Evidence** | "VT 7/94" cannot be attached to a case | Screenshot, page capture, hash chain, all kept after the site is gone |
| **Action** | GSB shows a warning in Chrome, but the site keeps running | Takedown pack to registrar and host, blocking in Gatekeeper and DNS |
| **Learning** | Someone else's model; we cannot influence it | Officer decisions become labels for our scorer |
| **Limits** | VirusTotal free tier: 4 requests per minute, non-commercial use only | Our own engine, works without any keys |

GSB and VirusTotal answer "is this URL already known to be bad?". The admin panel answers different questions: "what is new that nobody knows about yet", "who is behind it" and "what have the police already done". If the product were a wrapper around GSB and VirusTotal, we would have almost nothing to show for early detection (25% of the score).

How to use them in the admin panel:
- **In the queue.** A GSB or VirusTotal hit is a strong argument, and the officer can confirm in one click. The real value is in cases where our score is high and GSB and VirusTotal are clean: nobody would have seen those without us.
- **Lead time against GSB.** On every watchlist re-check, query GSB and VirusTotal again and record when they first flagged the domain (`gsb_first_hit_at`, `vt_first_hit_at`). Every confirmed domain then gets a figure: "found N hours before Google". For the metrics slide this is the most convincing proof, and it comes from real data.
- **Takedown.** A report to GSB is one of the recipients of every takedown request. We tell Google about the site instead of waiting for it to find out.

---

## 10. Metrics and limits

These are hypotheses until the four-week pilot in the brief confirms them. Metrics for the pilot:

| Metric | What it shows |
|---|---|
| Median exposure window (first certificate to offline) | sites live for less time |
| Lead time against OpenPhish, URLhaus, GSB and the first resident report | how much earlier we are |
| Share of new domains linked automatically to a known campaign | the graph actually helps |
| Time from takedown request to offline, per provider | how well takedowns work |
| Share of sites that come back | how lasting the disruption is |
| Confirmation rate per source and per score band | search quality |

Honest limits:
- **Displacement.** Under pressure, fraudsters move to Telegram and WhatsApp, bulletproof hosting and registries that do not respond. The number of sites will fall, but not necessarily the number of frauds.
- **The officer is a bottleneck.** If the queue grows faster than it is cleared, the effect disappears. That is why ranking, bulk actions, and auto-confirm only above 90 with a credential form matter.
- **Graph errors are dangerous.** A false link through shared hosting could block a legitimate site. The safeguards are the hub rule, the hard allowlist and mandatory review before a takedown.
- **Arrests are not our part.** The system provides linked evidence; the police and prosecutors decide.

For the pitch, the claim is not "less crime". It is: sites live for less time, we see them earlier, and twenty domains become one case with evidence.

---

## 11. Build order

1. **Slice 5 (required):** mock sign-in, unified queue, case card, Confirm and Reject with blocklist update, live Hunter feed, chain-check button.
2. **Campaigns:** entity extraction and clustering with the hub rule, then `/graph` and the detail page with graph and domain table, then "Confirm all". Campaign PDF if time allows.
3. **Takedown:** contacts and pack, then "Mark as sent", then offline detection through the watchlist and a status table. Kanban and registrar ranking if time allows.
4. **Slice 7 (if time allows):** KPI page with lead time (including `gsb_first_hit_at`), system health strip.
5. **Pitch as next steps:** lists with appeals, registrar ranking, fake-helpline export, alerts to Telegram or email, officer copilot (A6).

For the demo: no real takedown will happen overnight, and faking data is not an option. The honest version uses the team's own test lookalike domain from slice 3: delete its DNS record, press "Check now", and the card moves to "Offline" on screen.
