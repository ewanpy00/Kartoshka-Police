# Test dataset and sources

Built on 24 November 2026 for the ScamShield AI hackathon (42 Abu Dhabi x Abu Dhabi Police). It is separate from the evaluation sets that `make eval` uses (`data/eval/test.csv` and `holdout.csv`, see the README); use it as a second, larger check.
Use it to test the **fast score** and the **batch endpoint**. Don't use it to train the final scorer.

## Files

| File | What it is |
|---|---|
| `scamshield_test_dataset.csv` | The combined labelled dataset (2,221 URLs) |
| `build_dataset.py` | Script that rebuilt the CSV from the raw downloads (re-run to refresh) |
| `DATASET_SOURCES.md` | This file |

## Columns

| Column | Meaning |
|---|---|
| `url` | The URL to score |
| `label` | `1` = phishing, `0` = benign |
| `category` | `phishing` or `benign` (same as label, in words) |
| `subset` | `general` (worldwide) or `uae` (UAE brands and official UAE sites) |
| `brand` | UAE brand impersonated (UAE phishing rows only) |
| `source` | Where the row came from (see Sources) |
| `synthetic` | `1` = invented lookalike made up for testing, `0` = real data |
| `registered_domain` | Registrable domain (e.g. `emiratesnbd.com`), for domain-level tests |
| `split` | `dev` (tune rules here) or `test` (report final numbers here only) |
| `collected` | Date downloaded |
| `note` | Extra notes |

## Contents

| Subset | Category | Source | Rows |
|---|---|---|---|
| general | phishing | OpenPhish public feed | 265 |
| general | phishing | Phishing.Database (ACTIVE links) | 735 |
| general | benign | Chrome UX Report top origins (rank ≤ 1000) | 723 |
| uae | phishing | Phishing.Database, filtered for UAE brands | 195 |
| uae | phishing | Synthetic lookalikes (invented) | 25 |
| uae | benign | Chrome UX Report, official UAE origins | 278 |
| **Total** | | | **2,221** |

The real UAE phishing rows cover these brands: Aramex 110, e& (Etisalat) 41, Emirates Post 27, Emirates NBD 8, DEWA 4, Mashreq 4, ADCB 1.

The splits are 50/50 within each subset and label (1,111 dev / 1,110 test). There are no duplicate URLs, and no registered domain appears as both benign and phishing.

## Sources

### 1. OpenPhish public feed (phishing, general)
- **Link:** https://github.com/openphish/public_feed (file `feed.txt`); also https://openphish.com
- **What:** About 300 currently active phishing URLs, refreshed regularly by OpenPhish.
- **How used:** All entries with `http`/`https`, at most one URL per host. None matched UAE brands in today's snapshot.
- **Note:** The URLs were live when downloaded, so they're good for testing the full pipeline, including the sandbox, inside the locked-down container only. Check OpenPhish's terms before any commercial use.

### 2. Phishing.Database (phishing, general and UAE)
- **Link:** https://github.com/mitchellkrogza/Phishing.Database (file `phishing-links-ACTIVE.txt`)
- **What:** About 789k phishing links that the project lists as active, gathered from several public feeds.
- **How used:**
  - **General:** a random sample (seed 42), one URL per host, to bring the general phishing total to 1,000.
  - **UAE:** URLs whose words match a UAE brand (e.g. `emiratespost`, `emiratesnbd`, `aramex`, `etisalat`, `mashreq`, `dewa`). Max 2 URLs per host. False matches were removed (UUID fragments, ADIB Egypt, Netflix clones, email addresses in paths).
- **Note:** "Active" is the project's label. Many entries are old and may be offline now. Use these for the fast score only, not the sandbox. Check the repository's license before reuse.

### 3. Chrome UX Report top lists (benign, general and UAE)
- **Link:** https://github.com/zakird/crux-top-lists (file `data/global/current.csv.gz`), built from Google's Chrome UX Report
- **What:** About 1M of the most-visited website origins, grouped into rank buckets (1k, 5k, 10k, 50k…).
- **How used:**
  - **General benign:** origins in the top-1,000 bucket, minus adult, gambling, piracy, and random-looking names, and minus any domain that also appears in the phishing lists.
  - **UAE benign:** every origin under `.gov.ae` and the official domains of UAE brands (TAMM, UAE PASS, u.ae, Emirates NBD, ADCB, FAB, ADIB, DIB, RAKBANK, Mashreq, Emirates Post, Aramex, e&, du, Salik, ADNOC, Emirates, Etihad, Dubai and Abu Dhabi government portals).
- **Note:** "Benign" means popular and not phishing. It isn't a quality judgement. Some general sites may still be ones you wouldn't want on a slide. Check the repository's license before reuse.

### 4. Synthetic UAE lookalikes (phishing, UAE)
- **Made by:** the ScamShield team (generated in `build_dataset.py`).
- **What:** 25 invented lookalike URLs for TAMM, UAE PASS, Abu Dhabi Police, Dubai Police, banks, couriers, Salik, Darb, DEWA, ICP, MOHRE, ADNOC, and RTA, plus one punycode and one subdomain trick.
- **Note:** These are **not real reports**. Domains may not exist or may be registered by someone else later. Use them only to test lookalike and brand rules. Report their results separately from the real data.

## Known traps (read before reporting numbers)

1. **Format difference.** Benign rows are bare origins (`https://www.example.com/`), while phishing rows often have long paths and query strings. A rule like "long URL means phishing" will look better here than in real life. To check, also score on `registered_domain` only and report both results.
2. **Age.** The Phishing.Database rows may be months or years old. Domain age and reputation lookups can look different now than when the URLs were reported.
3. **Brand coverage.** Real UAE phishing is mostly Aramex, e&, and Emirates Post. TAMM, UAE PASS, and police fines appear only in the synthetic rows.
4. **Tune on `dev`, report on `test`.** Don't look at test results while tuning.

## Safety

- Never open these URLs on a personal device or browser.
- Open phishing URLs only in the sandbox container (non-root, network-restricted, destroyed after each visit).
- Don't send real data to any of these sites.

## Quick use

```python
import pandas as pd
df = pd.read_csv("scamshield_test_dataset.csv")
test = df[df.split == "test"]
general = test[test.subset == "general"]
uae_real = test[(test.subset == "uae") & (test.synthetic == 0)]
uae_synth = test[(test.subset == "uae") & (test.synthetic == 1)]
# score each group with your batch endpoint and report precision, recall and false-positive rate separately
```

## Sources not included (couldn't be downloaded from the build environment)

Add these from your own machine if you want more coverage:

| Source | Link | Use |
|---|---|---|
| Tranco top sites list | https://tranco-list.eu | Alternative benign list |
| URLhaus (abuse.ch) | https://urlhaus.abuse.ch | Malware URLs, fast score only, never open |
| PhiUSIIL phishing URL dataset | https://archive.ics.uci.edu (search "PhiUSIIL") | Large labelled set with raw URLs |
| PhishTank | https://phishtank.org | Verified phishing URLs (registration may be required) |
| DeepURLBench | https://arxiv.org/abs/2501.00356 | Newer curated multi-class dataset |

To refresh: download the raw files again into `raw/` (`openphish.txt`, `pdb_links_active.txt`, `crux.csv.gz`) and run `python3 build_dataset.py`.
