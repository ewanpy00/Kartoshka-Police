# Kartoshka-Police application build: plan

Status: in progress on branch `feat/app`. Builds the application described in `ARCHITECTURE.md` on top of the DevOps skeleton (`docs/devops-plan.md`). Progress notes are at the bottom.

## Slices

Each slice is verified in the running stack and committed on its own.

| # | Slice | Main paths |
|---|---|---|
| 1 | Core fast path: normalize, lexical and domain features, RDAP, GSB, VirusTotal, feed and campaign lookups, verdict cache, bands, reasons in Arabic and English, `sources[]`, batch on the fast score | `core/app/normalize`, `core/app/fast`, `core/app/verdict` |
| 2 | Deep path: extended sandbox capture (Arabic phone profile, forms, text, HTML, favicon, scripts, phones, TLS, server IP, cloaking visit), signals, visual match, infrastructure (DNS, ASN, crt.sh), evidence store with hash chain and artifacts, campaign graph, watchlist | `sandbox/app`, `core/app/deep`, `core/app/evidence`, `core/app/graph` |
| 3 | Officer and resident API: review with blocklist delta, ranked queue, campaigns, evidence PDF and takedown pack, safe preview, reports with device token, radar, live events, SMS paste, hunter intake | `core/app/api` |
| 4 | AI layer: provider switch, page-understanding LLM (A2), visual matcher (A3), SMS text classifier (A4), kit clustering (A5), fusion (A0), officer copilot (A6), URL model (A1), retrain loop (A7) | `core/app/ai` |
| 5 | Officer console: mock UAE PASS sign-in, ranked queue, case card, confirm or reject, campaign graph, live feed, exports | `console/` |
| 6 | Resident screens (PWA): Link X-ray, safe preview, my reports, scam radar, paste SMS | `resident/` |
| 7 | Hunter: name filter, infrastructure filter, CT, newly registered domains, feeds, search sweep, watchlist ticker, submission to core, backtest | `hunter/` |
| 8 | DNS Shield: blocklist in AdGuard format and a minute-level sync service | `dns/`, `core/app/api` |
| 9 | Gatekeeper Android source (not built here: no Android SDK on the build machine) | `gatekeeper/` |
| 10 | Eval with per-brand metrics and ablation, docs, full verification | `eval/`, `README.md` |

## Decisions

1. **The score stays deterministic.** Every signal adds points under a reason code; the sum is capped at 100 and mapped to the bands `<30 allow`, `30-70 warn`, `>70 block`. The LLM can add reasons and move a score only inside the 30-70 band; hard floors (a non-official domain that claims a brand and asks for an OTP, a card or UAE PASS credentials) lift it to at least 75.
2. **`/v1/check` now always returns a definite verdict from the fast path.** `pending` stays in the schema for clients but the fast path no longer produces it. A warn or block verdict, `mode: deep`, a hunter candidate and a user report each queue a deep analysis; the response's `sandbox` and `ai` sources say `running` until it finishes.
3. **External lookups are optional.** GSB, VirusTotal, the search API and the LLM run only when their key is set in `.env`; otherwise their source is `skipped`. RDAP, DNS, ASN (Team Cymru) and crt.sh need no key.
4. **Fast-path network lookups run inside a budget** (`FAST_LOOKUP_BUDGET_MS`). A lookup that misses the budget is `unknown` in the response and is filled in by the deep path.
5. **Core follows redirects for shorteners only**, with the same internal-address test as the sandbox guard on every hop, and reads headers only. The sandbox records the full chain on the deep path.
6. **Visual similarity uses a perceptual hash** of the phone screenshot against the brand reference screens in `data/refs/`. CLIP needs PyTorch, which does not fit the 4 GB Docker VM next to the rest of the stack; the matcher is pluggable so CLIP can replace it.
7. **The LLM is Claude through the official SDK** (`AI_MODEL`, default `claude-opus-5-5`), structured JSON output, no tools for page understanding, page text inside a delimited untrusted block, server-side refusal fallback on.
8. **Resident screens are a separate Vite app** (`resident/`, port 5174, published on `BIND_ADDR` so the demo phone can open it). It never receives the write token. The console stays on localhost.
9. **Evidence is append-only.** A database trigger rejects updates and deletes on `evidence`; each row stores the SHA-256 of the previous row.
10. **Privacy.** No user identity is stored. Reports get a random id and a secret token whose hash is kept; the device keeps the token. Block counters are per domain and channel only.
11. **`BATCH_CUTOFF` is 40**, chosen on the development set (`data/eval/test.csv`) and checked once on the untouched hold-out set. Batch answers are binary, so the cutoff sits at the knee of the sweep rather than at the resident `block` band: on the dev set 70 gives recall 0.42 at precision 1.0, 40 gives 0.76 at 0.996. The resident bands do not change.
12. **The scorer knows global brands too** (`data/global_brands.yaml`: PayPal, Microsoft, Apple, banks, couriers and others that kits imitate). They are used for brand-in-domain and look-alike tests only; they are not on the radar and are not seeded as official domains. Official domains in that file are the sites people sign in to, not CDN hosts.
13. **The URL model (A1) is stored in the database** (`model_state`, key `url_model`), because `data/` is mounted read-only. Core and worker reload it every 5 minutes. The benign training URLs are bare Tranco domains, so training gives about two thirds of them a realistic subdomain and path; without that the model learned "has a path" as a phishing signal and rated `dubaimall.com/` 95% phishing. Tests stub the model out, so their scores do not depend on whichever model is in the shared database.

## Progress

- 2026-11-24: plan written; branch `feat/app` created.
- 2026-11-24: slice 1 done. Fast path, migration `0002_engine`, global brands, URL model, eval set and eval CLI. `make test` 68 passed. Results at `BATCH_CUTOFF=40`, no GSB or VirusTotal key, so those rows add nothing yet:

  | Set | Rows | Precision | Recall | FPR |
  |---|---|---|---|---|
  | dev (`test.csv`, tuned on) | 611 | 0.996 | 0.767 | 0.004 |
  | hold-out (`holdout.csv`, not tuned on) | 450 | 0.983 | 0.763 | 0.027 |

  These are second runs, with the RDAP cache warm. On a cold cache some lookups miss the 700 ms budget, and recall is up to 0.03 lower (hold-out 0.737).

  - Hold-out recall by source: OpenPhish 0.96, PhishTank 0.49. Most PhishTank misses are pages on compromised old domains with plain paths; nothing in a URL gives them away, so they need the deep path.
  - The 60 synthetic UAE-brand rows score recall 1.0. The scorer was written with these patterns in mind, so that number is not evidence; it only shows that each pattern is covered.
  - Ablation on the hold-out: rules alone give recall 0.11, domain age adds 0.01, the URL model brings it to 0.74. The deep row equals the fast path because batch does not run deep analysis; slice 2 adds the deep numbers through `/v1/check?mode=deep`.
  - The remaining hold-out false positives are new domains on `.xyz`, `.shop` and `.site` that the URL model rates above 90%, and `assoc-amazon.com`, an Amazon-owned domain that reads exactly like an impersonation.
  - RDAP now goes to the registry's own server from the IANA bootstrap file. The rdap.org redirector was the reason most lookups missed the 700 ms budget.
  - `eval/build_set.py` rebuilds both sets and the training lists from feed snapshots; the snapshots themselves are not committed.
  - The committed sets and training lists contain URLs from the OpenPhish community feed and PhishTank, whose terms allow non-commercial use with attribution. Check those terms before the repository is made public or used commercially.
