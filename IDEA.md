# Kartoshka-Police: the idea

Scam links reach UAE residents by SMS, WhatsApp and email, usually pretending to be TAMM, RTA, UAE PASS, a bank or a delivery company. Known-bad lists such as Google Safe Browsing and VirusTotal catch them late: a new page made for UAE residents often shows 0 detections in its first hours, which is when most victims open it.

Kartoshka-Police answers with one link-checking engine and several ways to reach it. This file records the starting ideas and how they were weighed against the ScamShield AI judging criteria on 24 November 2026. The design that came out of it is [ARCHITECTURE.md](ARCHITECTURE.md); what is built is listed in the [README](README.md).

## The three starting ideas

| Idea | Verdict | Why |
|---|---|---|
| A detection engine on top of VirusTotal, Google Safe Browsing and URL parsing | Keep, but add our own scoring | The lookups lag on new pages, and URL parsing only splits a link into parts. The signals have to be built on top (see below). |
| DNS blocking on the home router, for families and closed communities | Keep, as an extra layer | Covers every device at home with no setup per device. DNS can only allow or block a whole domain, so it blocks officer-confirmed domains only. |
| A default browser on the phone that checks every link first, then hands safe links to the normal browser | The strongest idea, Android first | It sees the full link from SMS, WhatsApp and email, exactly where UAE scams start. |

## The engine

- **Our own signals:** registrable domain, decoded international (punycode) names, a brand name in the subdomain, distance to the official domain, look-alike characters, scam words (pay, fine, verify), and domain age from RDAP.
- **A small model on top:** a LightGBM model over the same URL features, trained on public phishing feeds against popular legitimate sites.
- **AI explains, it doesn't decide.** The numeric score stays deterministic so precision and recall are stable and reproducible. AI is used for the uncertain middle band and for reasons in Arabic and English.
- **An allowlist of official UAE domains** (`*.gov.ae`, `tamm.abudhabi`, `uaepass.ae`, the UAE banks, the most popular sites) keeps false positives low, which is judged explicitly.
- **Evasion:** follow the full redirect chain, expand URL shorteners, normalise look-alike characters, and visit the page twice (as a bot and as an Arabic phone) to catch pages that hide from scanners.
- **A dead page is not a safe page.** URL features and domain age must work without loading the page.
- **Free API limits** (VirusTotal allows about 4 requests a minute) mean results are cached and every check works without the external lookups.
- **Judges need numbers:** a batch route and an evaluation tool that print precision, recall and false positive rate on a labelled set.

## DNS for homes and communities

- Covers children's tablets and smart TVs with no setup on each device.
- Doesn't cover mobile data on its own; phones use Private DNS pointing at the same resolver.
- Compounds, schools and residences for older people are a strong pilot story.
- Limits: DNS can't show a warning (a blocked HTTPS site shows a certificate error), so it blocks confirmed domains only and warnings stay in the app. It sees only the domain, so it can't block scams hosted on shared services such as Google Sites or GitHub Pages.

## The default browser

- On Android the app registers as the default browser. A safe link goes straight to Chrome; a suspicious one shows a warning with reasons in Arabic and English; a scam is blocked with a "Report" button.
- On iPhone, Apple only allows a real web browser to be the default, not a check-and-redirect app. The iPhone route is in [docs/apple-development-plan.md](docs/apple-development-plan.md).
- Limits to state openly: in-app browsers (Instagram, Telegram, TikTok) bypass the default browser, and users can switch the default back.

## What the judging criteria added

| Criterion | Weight | What it added |
|---|---|---|
| Early detection | 25% | The Hunter: certificate transparency logs filtered by UAE brand names, newly registered domain lists, look-alike variations of each brand domain, and fake helpline numbers |
| Explainability | 20% | Per-signal score contributions, abuse contacts from RDAP, and a one-click takedown pack (PDF, JSON and the email to the registrar or host) |
| UAE relevance and innovation | 15% | A UAE brand registry (official domains, reference screenshots, official phone numbers), visual similarity to the real login pages, a campaign graph linking domains, phones, servers and payment pages, and Arabic look-alikes and transliterations such as `tamm-pay` |
| Feasibility | 10% | A live end-to-end demo, and a pilot path: shadow mode, then volunteer families and compounds, then TDRA and the internet providers |

## Product surfaces

1. **Detection engine:** intake, fast score, sandbox, verdict, evidence.
2. **Officer console:** ranked queue, screenshot and reasons, confirm or reject, campaign graph, takedown packs.
3. **Resident side:** the Android app, "check this link", and DNS setup for the router and the phone.
4. **Scoring API and evaluation tool** for the judges.

## The 24-hour priorities, as planned

- **Must:** URL scorer and allowlist, batch scoring and evaluation, sandbox screenshot, evidence PDF, officer confirm, "check a link".
- **High value:** certificate transparency with a brand filter, fake helpline check, visual similarity, the Android app.
- **If time:** campaign graph, AdGuard Home on a real router or phone, a native SMS filter.

All "must" and "high value" items were built. Of the "if time" items, the campaign graph and DNS Shield were built (DNS Shield runs in the Docker stack, not yet on a real router); the native SMS filter was not.
