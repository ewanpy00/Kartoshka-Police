# Kartoshka-Police: architecture

One core (link analysis), many entry points. Every client (the Gatekeeper browser, DNS Shield, the
share button, the Hunter, the judges' batch route) calls the same core API and gets the same verdict
format. Confirmed verdicts flow back out to every client.

This is the design. Most of it is built; parts that are still planned are marked **(planned)**, and
places where the build chose a simpler method say so. For how to run the system, see the
[README](README.md); for the build decisions behind each part, see [docs/README.md](docs/README.md).

```
                        ┌────────────────────── PROACTIVE ──────────────────────┐
                        │  HUNTER                                                │
                        │  certstream (CT) · NRD daily · Search/Ads/Maps sweep   │
                        │  OpenPhish/URLhaus · pivot from confirmed · watchlist  │
                        └───────────────┬────────────────────────────────────────┘
                                        │ candidates (source=hunter)
   ┌──────── REACTIVE (residents) ──────┼───────────────────────┐
   │ Gatekeeper browser (Android)       │                       │
   │ Share / paste link / paste SMS     ▼                       │
   │ DNS Shield (unknown domains) ─► ┌───────────────────────────────────────────┐
   └────────────────────────────────►│  CORE — Link Intelligence Engine (FastAPI) │
                                     │                                           │
   Judges CLI / batch ──────────────►│  1 Normalize  2 Fast score  3 Deep analyze │
                                     │  4 Verdict    5 Evidence    6 Campaign graph│
                                     └──────┬──────────────┬──────────────┬───────┘
                                            │              │              │
                                   blocklist delta   review queue    takedown pack
                                            ▼              ▼              ▼
                              DNS Shield + Browser   Officer Console   Registrar / host / GSB
```

---

## 1. CORE — Link Intelligence Engine

### 1.1 Normalize (always, <50 ms + network for redirects)
- `urllib.parse` → scheme / host / path / query / fragment.
- `tldextract` → registrable domain, subdomain, TLD.
- IDN: punycode → Unicode; flag mixed scripts (Arabic + Latin, Cyrillic look-alikes).
- Unshorten (bit.ly, t.ly, tinyurl, cutt.ly …) and follow the redirect chain (HEAD/GET, max 10 hops,
  mobile UA). Keep the whole chain — every hop is scored, the final URL is the main target.
- Output: `NormalizedURL {original, final, chain[], domain, subdomain, tld, path, params}`.

### 1.2 Fast score (target <300 ms, used inline by the browser)
Checks in this order, first decisive hit wins:
1. **Allowlist** (official UAE domains from `data/brands.yaml` + Tranco top-10k) → `allow`.
2. **Blocklist** (confirmed by Core / officer) → `block`.
3. **Verdict cache** (Redis, keyed by final URL and by domain) → cached verdict.
4. **Feature score** (deterministic, explainable):
   - lexical: brand-in-domain/subdomain, action words (pay, fine, verify, renew, refund),
     edit distance to official domains, homoglyphs, punycode, length/entropy, digits, hyphens;
   - domain: age (RDAP, cached), registrar, TLD risk, NS / IP / ASN seen in known campaigns;
   - lookups: VirusTotal + Google Safe Browsing (only if cached or answered within budget,
     otherwise async and merged later);
   - small ML model (LightGBM on the same features) → probability (used when a trained model exists).
   Each feature contributes points with a reason code → `score 0–100` + `reasons[]`.
5. Bands: `<30 allow` · `30–70 warn + deep` · `>70 block + deep (confirm)`.

### 1.3 Deep analyze (async, seconds–minutes, Redis queue → sandbox workers)
- Playwright in a disposable, non-root, network-restricted container.
- Profile: Arabic mobile phone (UA, viewport, `ar-AE` locale, Asia/Dubai TZ).
  **UAE exit IP** if possible (scam kits geofence to UAE IPs + mobile).
- Visit twice (bot profile vs. phone profile) → different content = cloaking signal.
- Capture: redirect chain, final HTML, page text, full-page screenshot, form fields, TLS cert,
  favicon, external scripts, phone numbers / WhatsApp links / payment endpoints.
- Signals:
  - **form asks for** card / CVV / OTP / Emirates ID / UAE PASS credentials;
  - **visual similarity** of the screenshot to brand reference screens: "looks like the UAE PASS
    login but the domain is not official" = strong reason. Built with a perceptual hash (pHash) of the
    phone screenshot; CLIP needs PyTorch, which doesn't fit next to the stack in 4 GB, so it is
    **(planned)** behind the same interface;
  - **kit fingerprint**: hash of DOM skeleton, favicon hash, script paths → matches known kits;
  - brand/domain mismatch (logo or name of brand X on a non-X domain).
- **LLM verdict** (no tools, structured JSON): input = features + capture text + screenshot;
  output = label, confidence, reasons in AR + EN. Numeric score stays deterministic
  (the LLM can lift a score only inside the 30–70 band and never past 70, or add reasons), so
  precision/recall are stable.
- Parked / empty page → NOT safe: put the domain on the **watchlist** (re-check every 6 h for 14 days).

### 1.4 Verdict
```json
{
  "check_id": "c_01H...",
  "url": "https://uaepass-verify.top/login",
  "final_url": "https://uaepass-verify.top/login",
  "verdict": "block",            // allow | warn | block | pending
  "score": 92,
  "stage": "deep",               // fast | deep | officer
  "brand": "UAE PASS",
  "safe_action": {
    "label_en": "Continue in the official UAE PASS app",
    "label_ar": "المتابعة في تطبيق الهوية الرقمية الرسمي",
    "url": "https://uaepass.ae"
  },
  "reasons": [
    {"code": "BRAND_IN_DOMAIN", "weight": 30, "source": "kartoshka",
     "en": "Domain uses 'uaepass' but is not an official UAE PASS domain",
     "ar": "النطاق يستخدم اسم 'uaepass' لكنه ليس نطاقًا رسميًا"},
    {"code": "DOMAIN_AGE", "weight": 20, "source": "rdap",
     "en": "Registered 2 days ago", "ar": "تم تسجيله قبل يومين"},
    {"code": "VISUAL_MATCH", "weight": 35, "source": "sandbox",
     "en": "Page looks 91% like the UAE PASS login page", "ar": "..."}
  ],
  "sources": [
    {"id": "allowlist", "status": "clean"},
    {"id": "police_blocklist", "status": "clean"},
    {"id": "gsb", "status": "unknown", "detail": "timeout"},
    {"id": "virustotal", "status": "hit", "detail": "7/94 engines"},
    {"id": "feeds", "status": "clean"},
    {"id": "rdap", "status": "hit", "detail": "registered 2 days ago"},
    {"id": "ct", "status": "hit", "detail": "first certificate 26 h ago"},
    {"id": "campaign", "status": "hit", "detail": "cmp_17, 14 domains"},
    {"id": "sandbox", "status": "hit", "detail": "asks for OTP"},
    {"id": "ai", "status": "skipped"}
  ],                             // status: hit | clean | unknown | skipped
  "preview": {"screenshot": "/v1/preview/ev_....png", "asks_for": ["card", "cvv", "otp"]},
  "campaign_id": "cmp_17",
  "evidence_id": "ev_..."
}
```

### 1.5 Evidence store
- One record per analysed URL: identity, capture, reasons, infrastructure (RDAP, IP, ASN, NS, cert),
  scam details (brand, phones, payment endpoints), discovery source, integrity.
- Every artifact SHA-256 hashed; records written to an append-only table (hash-chained:
  each row stores the hash of the previous row).
- Export: PDF (officer / court), JSON (machine), takedown email to RDAP abuse contacts, GSB report.
- Privacy: no user identity, no browsing history — only "seen via browser/dns/share" counters.

### 1.6 Campaign graph
- Nodes: domain, IP, ASN, NS, registrar, cert, kit_hash, favicon_hash, phone, payment endpoint.
- Edges from every analysed record. Connected components with ≥1 confirmed scam = campaign.
- New node attached to a known campaign → score boost + immediate deep analysis.
- Stored in Postgres (edges table); rendered in the Officer Console.

---

## 2. HUNTER — proactive discovery (Criterion 2)

| Source | How | Latency | Status |
|---|---|---|---|
| Certificate Transparency | self-hosted `certstream-server-go` (Docker) → Python consumer | minutes after cert | Built |
| Newly registered domains | WhoisDS free daily list | ~1 day | Built |
| Search + Ads + Maps | scheduled AR/EN queries ("دفع مخالفات", "tamm fine payment", "emirates id renewal") via SERP API; Maps: listing name = brand but phone not in official registry | hours | Planned (fake helpline numbers found on scam pages are collected instead) |
| Threat feeds | OpenPhish; URLhaus with a free abuse.ch key (filter by UAE brands) | 30 min | Built |
| DNS Shield | unknown domains resolved by protected devices (anonymised, domain only) | real time | Planned |
| Pivot | from a campaign: same IP / NS / cert SAN / kit hash → new candidates | on demand | Built as the officer's related-site search on the campaign page |
| Watchlist | re-check parked / empty suspicious domains | every 6 h, 14 days | Built |

Two filters before Core:
- **Name filter** — brand keywords (+ transliterations, Arabic), action words, dnstwist permutations,
  edit distance, homoglyphs. Catches look-alike names.
- **Infrastructure filter** — fresh + risky TLD + risky registrar + IP/ASN/NS seen in campaigns.
  Catches random-name domains (e.g. Smishing Triad style `dwu6.top`).
Candidates → `POST /v1/check {source:"hunter", mode:"deep"}`.

Hunter metric for the pitch: **% of known UAE scams we would have flagged, and how many hours
before the first public report** (CT timestamp vs. feed first-seen).

---

## 3. GATEKEEPER BROWSER — the layer between the user and their apps

Android app registered as the default browser (handles `VIEW` intents for http/https).
Every link tapped in SMS, WhatsApp, Gmail, etc. lands here first, with the FULL URL.

```
tap link in SMS
   │
   ▼
Gatekeeper receives intent ──► local check (on-device, <10 ms)
   │                            · blocklist Bloom filter (synced delta)
   │                            · allowlist
   │                            · tiny lexical scorer (same features, no network)
   ▼
POST /v1/check {mode:"fast"}  (timeout 400 ms)
   │
   ├─ allow  ─► forward to the user's real browser (explicit intent to Chrome/Samsung Internet)
   ├─ warn   ─► interstitial: score, reasons AR/EN, [Go to the real service]
   │            [Go back] [Open anyway] [Report]
   │            deep analysis keeps running; if it turns "block", push a notification
   ├─ block  ─► block page AR-first: "⚠️ Suspected scam", reasons, brand being impersonated,
   │            [Go to the real service] (TAMM / UAE PASS), [Report to police]
   └─ timeout ─► local score low → forward; otherwise "Checking link…" screen up to 3 s,
                 then warn with what we have
```

Go to the real service (on the warn interstitial and the block page):
- The page does not only say "dangerous". It offers the official service the scam was imitating, so the user still finishes the task safely.
- Example: a fake "pay your traffic fine" link → "⚠️ Suspected scam" and **Check your real fines in TAMM**, which opens `https://www.tamm.abudhabi/wb/adp/pay-traffic-fines`. A fake UAE PASS login → **Continue in the official UAE PASS app** (`https://uaepass.ae`, or the installed app).
- Which button: verdict `brand` + keywords in the URL or pasted SMS, matched against `services[]` in `data/brands.yaml`. No keyword hit → that brand's homepage (`official_domains[0]`).
- The button is a normal link (or an Android view intent if the official app is installed). No TAMM API and no UAE PASS API.
- `safe_action` is filled by Core from `brands.yaml` and returned on `/v1/check`. Offline, Gatekeeper uses the same list bundled in the app.
- The catalog is collected by opening the public site and copying each service URL. Confirmed seed: pay traffic fines, from [tamm.abudhabi](https://www.tamm.abudhabi/wb/adp/pay-traffic-fines). More TAMM services (renewal, licensing, …) are added the same way. UAE PASS stays the official homepage / app.

Extra entry points in the same app:
- **Share target** "Check with Kartoshka" (links from any app, incl. in-app browsers).
- **Paste SMS text** → extract all URLs → check each.
- **Report** → sends URL to Core as a candidate (source=user_report).
- **Protection setup**: one tap to set Private DNS (DNS Shield) + set as default browser.

Privacy:
- The police blocklist is matched on the phone (a Bloom filter synced from `/v1/blocklist`), and
  official domains are forwarded with no network call.
- The full URL goes to core only when the domain is not official. No account, no device ID stored
  with checks.

Limits (say them in the pitch):
- iOS cannot do this with a check-and-redirect app: the default-browser entitlement requires a real
  browser. The iPhone route (a real browser plus extensions) is in
  [docs/apple-development-plan.md](docs/apple-development-plan.md); until then iPhone users get the
  resident web app.
- In-app browsers (Instagram, Telegram, TikTok) bypass the default browser → share button.
- Users can switch the default back.

### 3.1 Resident app screens (the "wow" layer)

Four screens on top of the same `/v1/check` response. Built once as shared web screens
(same component library as the Officer Console): shown in a WebView inside Gatekeeper and
reachable from iPhone as a PWA, so iOS users get the manual check, preview, reports and radar
even without link interception.

#### Link X-ray — an animation, not a new engine
- Replaces the "Checking link…" spinner, and plays on the manual "Check a link" screen.
- A column of source cards ticks in one by one (~150 ms each): Official list → Police-confirmed list →
  Google Safe Browsing → VirusTotal → Phishing feeds → Domain age → First certificate (CT) →
  Campaign link → Safe preview → AI explanation. Then the verdict card lands (allow / suspected / blocked)
  with reasons AR/EN and the `safe_action` button.
- Timing is cosmetic; results are not. Every card's final state comes from `sources[]` in the real
  response: `hit` (red), `clean` (green), `unknown` (grey, e.g. timeout), `skipped` (grey "not checked").
  Never a green tick for a source that was not queried.
- Never slows the verdict: if the response arrives first, the animation fast-forwards; the 1.5 s
  budget of section 3 still holds. Deep-path cards (preview, AI) show "running…" and fill in when
  `GET /v1/check/{id}` returns.

#### Safe preview
- Shows the page behind the link WITHOUT the user opening it: the sandbox screenshot (Arabic phone
  profile) as a static image, plus a strip "This page asks for: card number · CVV · OTP" from the
  captured form fields, the domain, the verdict and the `safe_action` button.
- Image only: a resized PNG served from our domain; no HTML, no scripts, nothing on it is clickable.
- Available when deep analysis ran (score ≥30). For a lower score the user can tap "Show safe preview"
  to queue a deep run on demand.
- Abuse limits: per-device rate limit (e.g. 10 previews/hour), same query-stripped URL as every check;
  residents see the preview and reasons, never the score weights or Hunter internals
  (otherwise the screen becomes a free testing tool for scammers).

#### My reports
- "Report" from the block page, the X-ray screen or the share button creates a report with a random
  `report_id` and a secret token kept only on the device. No account, no identity.
- Timeline per report: Sent → Analysed (verdict) → In police review → Confirmed / Rejected →
  Site taken down (watchlist re-check sees it offline) → Impact: "blocked N times for other residents".
- Rejected shows a plain reason ("Reviewed: looks legitimate").
- Status is pulled with `GET /v1/reports/{id}` + token; optional push on status change (the push token is
  stored with the report only and deleted at the final status).
- Impact count = aggregated block counters for that domain (Gatekeeper + DNS), never per-user data.

#### Scam radar
- Home-screen card + full list of what is active right now in the UAE, grouped by brand:
  "37 fake fine-payment sites active — imitating RTA, TAMM", "New today: 9", trend vs. yesterday.
- Each brand row: a one-line tip in AR/EN ("TAMM never asks for card details by SMS") and the
  brand's `safe_action` button.
- Data from Hunter + campaigns via `GET /v1/radar` (cached, refreshed every minute, no personal data).
- Counts include confirmed and high-score suspected sites, labelled as such. Domains appear only when
  officer-confirmed, defanged (`tamm-pay[.]xyz`) and never clickable, so the radar never advertises
  a live scam.
- On stage it is the visible proof of Criterion 2: the radar moves while Hunter finds new domains.

---

## 4. DNS SHIELD — always-on, domain-level

- AdGuard Home (DoH / DoT) — router for the home, Private DNS for phones on mobile data.
- Pulls `GET /v1/blocklist?since=` every minute: **only confirmed** domains (DNS cannot show warnings).
- **(planned)** Send unknown, never-seen domains (no client IP) to the Hunter as candidates.
- **(planned)** Family / community mode: one resolver per household / compound, simple admin page
  (blocked count, top blocked brands). Today block counts go back to core and show in My reports and
  on the console's Impact page.

---

## 5. OFFICER CONSOLE (web, RTL)

Sign in with UAE PASS — **mock, no real API** (buys the integration time):
- The console opens on a UAE PASS button. One tap creates a local demo session `{name: "Demo Officer", role: "officer"}`.
- No OAuth, no client id, no call to `id.uaepass.ae` or any UAE PASS endpoint. A small banner says "Demo login — not connected to UAE PASS".
- Confirm / Reject still records that demo name as the reviewer. Residents never sign in; Gatekeeper stays account-free.
- Later the same button can call real UAE PASS. The queue, evidence, and review API stay as they are.

- Ranked queue: score × reach (how many devices/reports hit it) × freshness.
- Card: screenshot left, reasons right (AR/EN), infrastructure, discovery source, campaign link.
- One click **Confirm / Reject** → verdict `stage:"officer"`, reviewer + time logged
  → blocklist delta → DNS + browsers within a minute.
- Campaign view: graph, domain count, first seen, brand, where victims meet it.
- Export: PDF evidence, takedown pack, campaign report.

The console is also the admin dashboard. Build contract: `docs/admin-dashboard.md`.

- **One review queue, one case per domain.** Resident reports, Hunter candidates and warn/block checks
  share one ranked list: `score × ln(1 + reports + hits) × freshness`, with a boost for the 30–70 band
  (those labels teach the model most). Reject needs a reason; it becomes the resident's report status.
- **Early detection.** Live Hunter feed, brand spikes (many new look-alikes for one brand within an hour),
  watchlist wake-ups (a parked domain starts serving a form), lead time against feeds, GSB, VirusTotal
  and the first resident report.
- **Campaigns.** Only strong links merge domains: phone, WhatsApp, payment endpoint, kit hash, favicon hash,
  shared multi-SAN certificate, dedicated IP. ASN, registrar, big name servers and CDN IPs are shown but
  never merge, and any entity shared by more than ~50 domains becomes weak (hub rule). "Confirm all" writes
  one review per domain and never touches official or allowlisted domains.
- **Takedown tracker.** One request per recipient (registrar, host, Cloudflare, aeDA for `.ae`, GSB), a
  hashed pack per recipient, states `pack_ready → sent → offline_pending → closed / reopened`, overdue after
  an SLA. An officer sends; nothing is sent automatically. Offline needs two consecutive checks with both
  profiles, so cloaking cannot fake a takedown.
- **Operations.** KPI page (exposure window, time to block, lead time), model quality (officer agreement per
  band, disagreements), hash-chain check, system health.
- **AI here explains and ranks, never decides.** A2 facts and AR/EN reasons on the case card, A1 in ranking,
  officer decisions stored as labels (A7). Confirm, reject, merges and sending are human or deterministic.
- Attacker-controlled text (titles, page text, URLs, report notes) is rendered as plain text; domains are
  defanged and never clickable.

---

## 6. API

| Method | Path | Used by |
|---|---|---|
| POST | `/v1/check` `{url, source, mode: fast\|deep}` | browser, share, DNS, hunter |
| GET | `/v1/check/{id}` | browser (poll deep result), console |
| POST | `/v1/batch` `{urls[]}` → CSV/JSON | judges, eval |
| POST | `/v1/report` `{url, note}` | browser |
| POST | `/v1/sms` `{text}` | resident app: paste an SMS, every link in it is checked |
| POST | `/v1/hits` | DNS Shield, Gatekeeper: aggregated block counts (no client address) |
| GET | `/v1/blocklist?since=ts` | DNS Shield, browser Bloom sync (`/v1/blocklist.txt` in adblock syntax) |
| GET | `/v1/preview/{evidence_id}.png` | resident app: safe preview (image only, rate-limited) |
| POST | `/v1/preview` `{url}` | resident app: "Show safe preview" for a low-score link |
| GET | `/v1/reports/{id}` (+ device token) | resident app: My reports timeline |
| GET | `/v1/radar` | resident app: Scam radar (aggregated, cached) |
| POST | `/v1/review/{evidence_id}` `{decision}` | console |
| GET | `/v1/evidence/{id}.pdf` / `.json` | console, takedown |
| WS | `/v1/events` | console live feed |
| GET/POST | `/v1/admin/*` (queue, cases, hunter feed, campaigns, takedowns, stats, health) | console only, write token on every route; full list in `docs/admin-dashboard.md` |

Evaluation: `make eval` → precision, recall, FPR, confusion matrix, per brand, ablation (see the README).
The full, current route list is at http://127.0.0.1:8000/docs when the stack runs.

---

## 7. Data

Postgres tables: `checks`, `domains`, `verdicts`, `evidence` (append-only, hash-chained),
`artifacts` (hashes + paths), `entities`, `edges`, `campaigns`, `watchlist`, `reviews`,
`takedown_requests`, `audit_log` (append-only).
Redis: job queue, verdict cache, rate limits. Object storage (local dir for the demo): screenshots, HTML.

`data/brands.yaml` — the UAE brand registry, used by every layer:
```yaml
- id: uaepass
  names: [UAE PASS, "الهوية الرقمية", uaepass, uae-pass]
  official_domains: [uaepass.ae]
  official_phones: ["<fill from the official website>"]
  reference_screens: [refs/uaepass_login_ar.png, refs/uaepass_login_en.png]
  keywords: [verify, login, update]
  services:
    - id: continue
      keywords: [verify, login, update, pass, هوية]
      label_en: "Continue in the official UAE PASS app"
      label_ar: "المتابعة في تطبيق الهوية الرقمية الرسمي"
      url: "https://uaepass.ae"
- id: tamm
  names: [TAMM, "تم", tamm]
  official_domains: [tamm.abudhabi]
  services:
    - id: traffic_fines
      keywords: [fine, fines, traffic, pay, مخالفة, مخالفات]
      label_en: "Check your real fines in TAMM"
      label_ar: "تحقق من مخالفاتك الحقيقية في تم"
      url: "https://www.tamm.abudhabi/wb/adp/pay-traffic-fines"  # copied from the public catalog
      collected_from: "https://www.tamm.abudhabi"
  ...
```

---

## 8. Repo layout

See the repository layout table in the [README](README.md#repository-layout).

---

## 9. Demo flow (≈3 min, as planned for the pitch)
1. Hunter live feed: CT shows `uaepass-verify[.]top` seconds after its cert.
2. Core: sandbox screenshot, visual match to UAE PASS, form asks for OTP → score 92.
3. Console: officer is already in through the mock UAE PASS button (no real API) → clicks Confirm → evidence PDF with hashes.
4. Phone: SMS with a fake fine link → tap → Gatekeeper block page in Arabic ("⚠️ Suspected scam") → **Check your real fines in TAMM** opens the official service. A fake UAE PASS link shows **Continue in the official UAE PASS app** instead.
5. Hand the phone to a judge: "paste any link" → Link X-ray cards tick in → safe preview shows the page
   and what it asks for → verdict in Arabic. Tap Report → My reports shows the timeline; Scam radar on the
   home screen has just gone up by one.
6. Same domain on home Wi-Fi → blocked by DNS Shield (optional `stretch` profile).
7. Metrics slide: precision / recall / FPR on eval set; "X% of last month's UAE scams caught N h before first report".
8. Limits slide: iOS, in-app browsers, geofencing, free-tier APIs.

---

## 10. AI layer

Principle: **AI extracts facts and explains; a calibrated model decides; an officer confirms.**
The LLM never outputs the final score directly → stable precision/recall, auditable verdicts,
and an attacker-controlled page cannot talk its way to "safe".

```
                 ┌────────── fast path (<300 ms) ──────────┐
URL ──► features ┤ A1 URL model (LightGBM / char-CNN)       ├──┐
                 └──────────────────────────────────────────┘  │
                 ┌────────── deep path (async) ─────────────┐  │     ┌──────────────┐
capture ────────►┤ A3 Visual brand matcher (CLIP/SigLIP)    ├──┼───► │ A0 FUSION     │──► score + bands
(screenshot,     │ A2 Page understanding LLM (vision, AR/EN)├──┤     │ calibrated LR │──► reasons (SHAP → AR/EN
 text, DOM)      │ A5 Kit / campaign embeddings             ├──┘     └──────────────┘     templates + LLM text)
                 └──────────────────────────────────────────┘
SMS text ──────► A4 Scam-text classifier (AR/EN) ──► URLs extracted ──► same pipeline
Officer ───────► A6 Copilot (campaign summary, takedown drafts)   A7 labels → nightly retrain
```

| # | Component | What it does | Hackathon implementation | Criterion | Status |
|---|---|---|---|---|---|
| A0 | Fusion | Calibrated model over all signals → probability → 30/70 bands. Reasons = top feature contributions mapped to AR/EN templates | Built more simply: the score is the sum of reason weights; the AI adds one reason that can lift a 30–70 score, never past 70 (`core/app/ai/fusion.py`) | C1, C3 | Built (simplified) |
| A1 | URL model | Fast score from URL + domain features; a tiny copy on the phone | LightGBM on PhishTank/OpenPhish/URLhaus vs Tranco + UAE brand set; `make retrain` adds officer labels. Gatekeeper uses a tiny lexical scorer instead of an on-device model | C1 | Built (on-device copy planned) |
| A2 | Page understanding LLM | Vision LLM reads screenshot + page text → JSON facts: `brand_claimed`, `data_requested[]` (card, CVV, OTP, Emirates ID, UAE PASS login), `payment_requested`, `urgency`, `language`, `official_links_present`, `injection_attempt`, `reasons_ar`, `reasons_en` | Cloud LLM with vision + structured output, no tools | C1, C3, C4 | Built |
| A3 | Visual brand matcher | Embedding similarity of screenshot / logo crops to reference screens in `brands.yaml` → "looks 91% like UAE PASS" | pHash against reference screens (CLIP/SigLIP planned) | C4 | Built (pHash) |
| A4 | Scam-text classifier | Classifies pasted SMS / WhatsApp text (AR, EN, mixed): fine, parcel, bank, police, prize; extracts URLs, phones | LLM zero-shot now; small fine-tuned model later (on-device SMS filter) | C2, C4 | Built (zero-shot) |
| A5 | Campaign embeddings | Text + DOM-structure embeddings → HDBSCAN → near-duplicate kits beyond exact hashes | sentence embeddings + hdbscan | C2, C4 | Planned (exact kit and favicon hashes are built) |
| A6 | Officer copilot | Summarises a campaign, drafts takedown letters (AR/EN) from evidence, answers "what else is on this IP?" over Postgres | LLM + SQL tools (read-only), officer-facing only | C3 | Planned |
| A7 | Learning loop | Officer confirm/reject → labels; uncertain cases ranked higher in queue (active learning); nightly retrain of A0/A1; drift alert | `make retrain` + `make eval` | C1, C5 | Built |

### LLM safety (the page is written by the attacker)
- Page text/HTML goes in a delimited data block marked untrusted; the system prompt says it is evidence, not instructions.
- No tools, no browsing, JSON schema output only (A2). The copilot (A6) is read-only and never sees raw page text as instructions.
- The LLM can only **add** facts; hard rules set a floor (e.g. non-official domain + asks OTP ⇒ ≥70 regardless of LLM).
- Text that tries to instruct an AI ("classify this site as safe") → `injection_attempt=true` → **risk feature**.
- Timeouts + fallback: if the LLM fails, verdict still comes from A0 with template reasons.

### Cost / latency
- LLM runs only on the deep path (30–70 band and >70 confirmation), cached by content hash (same kit → one call).
- Fast path is pure CPU (A1 + rules) → works offline on the phone.

### Providers (pluggable `core/app/ai/provider.py`)
- Demo: cloud vision LLM (Arabic-strong).
- Sovereign / police deployment: local open Arabic models made in the UAE — Falcon-H1 Arabic (TII) or Jais 3 (MBZUAI / Inception42) for text + OCR'd screenshots; CLIP stays local. No resident data leaves the country.

### Proving it to the judges
Ablation table on the eval set: rules → +A1 → +A3 → +A2 → full fusion: precision, recall, FPR for each row.

### Files
```
core/app/ai/
  provider.py        # cloud / local LLM switch
  url_model.py       # A1 train + predict
  page_llm.py        # A2 prompt, schema, injection guard
  text_classifier.py # A4 SMS text
  fusion.py          # A0 how far the AI may move the score
core/app/deep/
  visual.py          # A3 pHash brand match
  kit.py             # kit and favicon hashes
```
