# Kartoshka / ScamShield — Architecture

One core (link analysis), many entry points. Every client — the Gatekeeper browser, DNS, the
share button, the Hunter, the judges' CLI — calls the same Core API and gets the same verdict
format. Confirmed verdicts flow back out to every client.

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
   - small ML model (LightGBM on the same features) → probability.
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
  - **visual similarity** of the screenshot to brand reference screens (CLIP embedding + pHash);
    "looks 91% like UAE PASS login but domain is not official" = strong reason;
  - **kit fingerprint**: hash of DOM skeleton, favicon hash, script paths → matches known kits;
  - brand/domain mismatch (logo or name of brand X on a non-X domain).
- **LLM verdict** (no tools, structured JSON): input = features + capture text + screenshot;
  output = label, confidence, reasons in AR + EN. Numeric score stays deterministic
  (LLM can move a case only inside the 30–70 band or add reasons), so precision/recall are stable.
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
  "reasons": [
    {"code": "BRAND_IN_DOMAIN", "weight": 30, "source": "kartoshka",
     "en": "Domain uses 'uaepass' but is not an official UAE PASS domain",
     "ar": "النطاق يستخدم اسم 'uaepass' لكنه ليس نطاقًا رسميًا"},
    {"code": "DOMAIN_AGE", "weight": 20, "source": "rdap",
     "en": "Registered 2 days ago", "ar": "تم تسجيله قبل يومين"},
    {"code": "VISUAL_MATCH", "weight": 35, "source": "sandbox",
     "en": "Page looks 91% like the UAE PASS login page", "ar": "..."}
  ],
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

| Source | How | Latency |
|---|---|---|
| Certificate Transparency | self-hosted `certstream-server-go` (Docker) → Python consumer | minutes after cert |
| Newly registered domains | WhoisDS / WhoisFreaks free daily list | ~1 day |
| Search + Ads + Maps | scheduled AR/EN queries ("دفع مخالفات", "tamm fine payment", "emirates id renewal") via SERP API; Maps: listing name = brand but phone not in official registry | hours |
| Threat feeds | OpenPhish, URLhaus (filter by UAE brands) | hours |
| DNS Shield | unknown domains resolved by protected devices (anonymised, domain only) | real time |
| Pivot | from each confirmed scam: same IP / NS / cert SAN / kit hash → new candidates | real time |
| Watchlist | re-check parked / empty suspicious domains | every 6 h, 14 days |

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
   ├─ warn   ─► interstitial: score, reasons AR/EN, [Go back] [Open anyway] [Report]
   │            deep analysis keeps running; if it turns "block", push a notification
   ├─ block  ─► block page AR-first: reasons, brand being impersonated, official site link,
   │            [Report to police] button
   └─ timeout ─► local score low → forward; otherwise "Checking link…" screen up to 3 s,
                 then warn with what we have
```

Extra entry points in the same app:
- **Share target** "Check with Kartoshka" (links from any app, incl. in-app browsers).
- **Paste SMS text** → extract all URLs → check each.
- **Report** → sends URL to Core as a candidate (source=user_report).
- **Protection setup**: one tap to set Private DNS (DNS Shield) + set as default browser.

Privacy:
- Fast path first sends only a hash prefix of the domain to match the blocklist (Safe-Browsing style).
- Full URL is sent only when it's unknown and not allowlisted. No account, no device ID stored
  with checks.

Limits (say them in the pitch):
- iOS cannot do this: the default-browser entitlement requires a real browser that navigates directly.
  iOS gets the share extension + Safari Web Extension.
- In-app browsers (Instagram, Telegram, TikTok) bypass the default browser → share button.
- Users can switch the default back.

---

## 4. DNS SHIELD — always-on, domain-level

- AdGuard Home (DoH / DoT) — router for the home, Private DNS for phones on mobile data.
- Pulls `GET /v1/blocklist?since=` every minute: **only confirmed** domains (DNS cannot show warnings).
- Optional: sends unknown, never-seen domains (no client IP) to Hunter as candidates.
- Family / community mode: one resolver per household / compound, simple admin page
  (blocked count, top blocked brands).

---

## 5. OFFICER CONSOLE (web, RTL)

- Ranked queue: score × reach (how many devices/reports hit it) × freshness.
- Card: screenshot left, reasons right (AR/EN), infrastructure, discovery source, campaign link.
- One click **Confirm / Reject** → verdict `stage:"officer"`, reviewer + time logged
  → blocklist delta → DNS + browsers within a minute.
- Campaign view: graph, domain count, first seen, brand, where victims meet it.
- Export: PDF evidence, takedown pack, campaign report.

---

## 6. API

| Method | Path | Used by |
|---|---|---|
| POST | `/v1/check` `{url, source, mode: fast\|deep}` | browser, share, DNS, hunter |
| GET | `/v1/check/{id}` | browser (poll deep result), console |
| POST | `/v1/batch` `{urls[]}` → CSV/JSON | judges, eval |
| POST | `/v1/report` `{url, note}` | browser |
| GET | `/v1/blocklist?since=ts` | DNS Shield, browser Bloom sync |
| POST | `/v1/review/{evidence_id}` `{decision}` | console |
| GET | `/v1/evidence/{id}.pdf` / `.json` | console, takedown |
| WS | `/v1/events` | console live feed |

CLI: `kartoshka eval data/eval/test.csv` → precision, recall, FPR, confusion matrix, per-brand.

---

## 7. Data

Postgres tables: `checks`, `domains`, `verdicts`, `evidence` (append-only, hash-chained),
`artifacts` (hashes + paths), `entities`, `edges`, `campaigns`, `watchlist`, `reviews`.
Redis: job queue, verdict cache, rate limits. Object storage (local dir for the demo): screenshots, HTML.

`data/brands.yaml` — the UAE brand registry, used by every layer:
```yaml
- id: uaepass
  names: [UAE PASS, "الهوية الرقمية", uaepass, uae-pass]
  official_domains: [uaepass.ae]
  official_phones: ["<fill from the official website>"]
  reference_screens: [refs/uaepass_login_ar.png, refs/uaepass_login_en.png]
  keywords: [verify, login, update]
- id: tamm
  names: [TAMM, "تم", tamm]
  official_domains: [tamm.abudhabi]
  ...
```

---

## 8. Repo layout

```
kartoshka/
  core/            FastAPI app: api/, normalize/, fast/, deep/, verdict/, evidence/, graph/
  sandbox/         Dockerfile + Playwright worker
  hunter/          certstream_consumer.py, nrd.py, sweep.py, feeds.py, pivot.py, watchlist.py
  gatekeeper/      Android app (Kotlin): intent handler, interstitial, Bloom sync, share target
  dns/             AdGuard Home config + blocklist sync
  console/         web dashboard (RTL)
  data/            brands.yaml, allowlist.txt, refs/, eval/
  eval/            eval.py
  docker-compose.yml   postgres, redis, core, sandbox workers, certstream-server-go, hunter, adguard
```

---

## 9. 24h plan (by team role)

| Hours | Core / ML | Sandbox / Deep | Hunter | Android | Console / Pitch |
|---|---|---|---|---|---|
| 0–4 | normalize, allowlist, brands.yaml, /v1/check fast | Playwright container, capture | certstream-server-go up, name filter | intent handler + forward | eval set collection |
| 4–10 | features + LightGBM, VT/GSB cache, eval CLI | form/brand rules, screenshot | infra filter, NRD, queue to Core | interstitial + block page AR/EN | console queue + card |
| 10–16 | score fusion, reasons AR/EN | visual similarity, LLM verdict | pivot, watchlist, feeds | share target, Bloom sync | evidence PDF, confirm flow |
| 16–20 | batch API, metrics | kit fingerprint | backtest: % caught + hours earlier | DNS setup screen | campaign graph |
| 20–24 | freeze, run eval | — | — | demo device | demo rehearsal, limits slide |

## 10. Demo script (≈3 min)
1. Hunter live feed: CT shows `uaepass-verify[.]top` seconds after its cert.
2. Core: sandbox screenshot, 91% visual match to UAE PASS, form asks for OTP → score 92.
3. Console: officer clicks Confirm → evidence PDF with hashes.
4. Phone: SMS with that link → tap → Gatekeeper block page in Arabic.
5. Same domain on home Wi-Fi → blocked by DNS Shield.
6. Metrics slide: precision / recall / FPR on eval set; "X% of last month's UAE scams caught N h before first report".
7. Limits slide: iOS, in-app browsers, geofencing, free-tier APIs.
