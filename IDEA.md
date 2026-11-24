Engine - VirusTotal/Google/urllib.parse.html.  
    Detection Accuracy - ✅


IDEAS:

    DNS for house router
        IDEA: Usage for families and closed communities

    set up a default browser on the phone that can define the threat and then call a normal browser if there is nothing dangerous.


---

## Review of the ideas above against the judging criteria (24 Nov)

### Engine (VirusTotal / Google Safe Browsing / urllib.parse) — Detection Accuracy: partial, not ✅
- VT can scan a NEW URL live (~70 engines, some heuristic/ML), so it is not only a known-list. But on brand-new, UAE-targeted pages detections often lag (0/70 in the first hours), and a live scan takes seconds to minutes. GSB is list-based.
- urllib.parse only SPLITS the URL (scheme/host/path/query). Signals must be built on top: registrable domain (tldextract), IDN/punycode decode, brand-in-subdomain, lookalike distance, keywords, domain age (RDAP).
- AI model on top of engine output (VT verdicts + parsed URL features + RDAP + page capture) = good plan. Use it for the gray zone (30-70%) and for AR/EN reasons; keep the numeric score deterministic so precision/recall are stable and reproducible.
- Decide by numbers: build a labelled set (incl. fresh UAE-brand phish) and compare VT alone / VT+features / VT+features+LLM before claiming ✅.
- Own scorer = rules (lookalike, brand-in-subdomain, mixed Arabic/Latin, punycode, scam keywords) + small ML model on URL features (LightGBM / char-CNN; train on PhishTank/OpenPhish/URLhaus vs Tranco).
- Allowlist of official UAE domains (*.gov.ae, tamm.abudhabi, uaepass.ae, all UAE banks, Tranco top-10k) → keeps false positives low (explicitly judged).
- Evasion: follow full redirect chain, expand shorteners, normalize IDN/homoglyphs, anti-cloaking (visit as bot AND as Arabic mobile phone, compare).
- Dead URLs in test set must NOT default to "safe" — URL features + domain age (RDAP) must work without the page.
- VT free tier ≈ 4 req/min → cache + work without it.
- Need `POST /score` (batch) + `scamshield eval test.csv` → precision / recall / FPR for the judges.

### DNS for home router (families, closed communities) — good, keep
- Covers every device at home incl. kids' tablets / smart TVs with zero setup per device.
- Does NOT cover mobile data → pair with phone Private DNS (Android DoT hostname / iOS DoH .mobileconfig). Same AdGuard Home resolver.
- Closed communities (compounds, schools, elderly residences) = strong pilot story for Criterion 5.
- Limit: DNS can only allow/block. Cannot show a "warning" for 30–70% (HTTPS sinkhole → cert error). So DNS hard-blocks only confirmed domains; warnings live in the app.
- Domain-only: cannot see the page, cannot block scams on Google Sites / GitHub Pages / shorteners.

### "Default browser" link interceptor — strong idea, Android-first
- This is the answer to the DNS gap: it sees FULL URLs from SMS / WhatsApp / email taps — exactly where UAE scams start. Can replace native SMS filtering in the MVP.
- Android: feasible in 24h. App registers as default browser (VIEW intent for http/https) → fast score (<300 ms) → <30% forward to Chrome via explicit intent; 30–70% interstitial with reasons in AR/EN; >70% block page + "report".
- iOS: NOT feasible. Default browser needs Apple's managed entitlement (request form) and the app must be a real browser that navigates directly to the destination — a check-and-redirect app is rejected. iOS fallback: share-sheet "Check this link" + Safari Web Extension.
- Limits: in-app browsers (Instagram, Telegram, TikTok webviews) bypass the default browser; user can untick it. Say this honestly in the pitch.

### Missing pieces (by weight)
- C2 Early Detection (25%): Certificate Transparency stream (certstream) filtered by UAE brand keywords; daily newly-registered-domain lists; dnstwist permutations of each brand domain; sponsored ads in search results; Maps "fake helpline" check (listing name = bank/TAMM/RTA but phone not in official registry).
- C3 Explainability (20%): per-feature score contributions, RDAP abuse contacts, one-click takedown pack (PDF + JSON + email to registrar/host + GSB report).
- C4 UAE & Innovation (15%): UAE brand registry (official domains, logos, reference login screenshots, official phone numbers) → visual page similarity (CLIP / perceptual hash vs reference); campaign graph (domains ↔ phones ↔ IPs ↔ payment endpoints); Arabic queries, Arabic homoglyphs, transliterations (tamm-pay, abudhabi-fines), RTL UI.
- C5 Feasibility (10%): live demo flow — certstream catches uaepass-verify[.]com → sandbox → 91% visual match to UAE PASS → officer queue → Confirm → blocked on phone via DNS → takedown PDF. Pilot: shadow mode → volunteer families/compounds → TDRA/ISP.

### Product surfaces
1. Detection Engine (intake → fast score → sandbox → verdict → evidence)
2. Officer Console (ranked queue, screenshot + reasons, confirm/reject, campaign graph, export)
3. Resident side: Android link-interceptor app + "check this link" + DNS setup (router + phone)
4. Scoring API / CLI for judges

### 24h priorities
- Must: URL scorer + allowlist, /score + eval, sandbox screenshot, evidence PDF, dashboard confirm, check-link.
- High value: certstream + brand filter, Maps helpline check, visual similarity, Android interceptor.
- If time: campaign graph, AdGuard Home on a real router/phone, native SMS filter.



---
Architecture & integration plan: see ARCHITECTURE.md
