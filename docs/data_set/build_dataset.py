"""Build the ScamShield test dataset from downloaded raw sources.

Usage: python3 build_dataset.py   (run from docs/data_set/, with the raw downloads in docs/data_set/raw/)
"""
import gzip, random, re, csv, datetime
import tldextract

random.seed(42)
TODAY = datetime.date.today().isoformat()
RAW = "raw"
ext = tldextract.TLDExtract(suffix_list_urls=())  # offline, bundled suffix list

def host(u):
    m = re.match(r"^[a-z]+://([^/:?#]+)", u, re.I)
    return m.group(1).lower() if m else ""

def regdom(u):
    e = ext(u)
    return ".".join(p for p in [e.domain, e.suffix] if p).lower() or host(u)

def ok_http(u):
    return u.lower().startswith(("http://", "https://")) and len(u) < 2000 and " " not in u

rows = []
def add(url, label, source, subset, brand="", synthetic=0, note=""):
    rows.append(dict(url=url.strip(), label=label,
                     category="phishing" if label else "benign",
                     subset=subset, brand=brand, source=source, synthetic=synthetic,
                     registered_domain=regdom(url.strip()), collected=TODAY, note=note))

# ---------- UAE brand map (used to tag real phishing from feeds) ----------
BRANDS = {
    "emiratesnbd": "Emirates NBD", "enbd": "Emirates NBD", "emiratespost": "Emirates Post",
    "mashreq": "Mashreq", "adcb": "ADCB", "bankfab": "FAB", "adib": "ADIB",
    "rakbank": "RAKBANK", "aramex": "Aramex", "etisalat": "e& (Etisalat)", "uaepass": "UAE PASS",
    "uae-pass": "UAE PASS", "tamm": "TAMM", "salik": "Salik", "dewa": "DEWA", "adnoc": "ADNOC",
    "dubaipolice": "Dubai Police", "adpolice": "Abu Dhabi Police", "mohre": "MOHRE",
}
OFFICIAL_SUFFIXES = ("emiratesnbd.com", "emiratespost.ae", "mashreq.com", "adcb.com", "bankfab.com",
    "adib.ae", "rakbank.ae", "rakbankonline.ae", "aramex.com", "etisalat.ae", "eand.ae", "uaepass.ae",
    "tamm.abudhabi", "salik.ae", "dewa.gov.ae", "adnoc.ae", "adnocdistribution.ae",
    "dubaipolice.gov.ae", "adpolice.gov.ae", "mohre.gov.ae")

EXCLUDE = re.compile(r"[0-9a-f]{4}-(adcb|dewa|adib)-[0-9a-f]{4}|adib[.-]eg|netflix|@mashreq\.com", re.I)

def uae_brand(u):
    if EXCLUDE.search(u):
        return ""
    h = host(u)
    if h.endswith(OFFICIAL_SUFFIXES) and not any(h.endswith(s + ".") for s in OFFICIAL_SUFFIXES):
        # exact official host -> not an impersonation (e.g. real aramex.com)
        if any(h == s or h.endswith("." + s) for s in OFFICIAL_SUFFIXES):
            return ""
    tokens = re.split(r"[^a-z0-9]+", u.lower())
    joined = "-".join(tokens)
    for k, b in BRANDS.items():
        if "-" in k:
            if k in joined:
                return b
        elif len(k) >= 6:
            if any(t == k or (t.startswith(k) and len(t) <= len(k) + 3) for t in tokens):
                return b
        elif k in tokens:
            return b
    return ""

# ---------- 1. Phishing: OpenPhish public feed (all of today's entries) ----------
op = [l.strip() for l in open(f"{RAW}/openphish.txt") if ok_http(l.strip())]
op = list(dict.fromkeys(op))
seen_hosts = set()

# ---------- 2. Phishing: Phishing.Database ACTIVE links ----------
pdb = [l.strip() for l in open(f"{RAW}/pdb_links_active.txt", errors="ignore") if ok_http(l.strip())]
pdb = list(dict.fromkeys(pdb))

# 2a. UAE-brand phishing from both feeds (real, max 2 URLs per host)
uae_phish, per_host = [], {}
for src, lst in (("OpenPhish public feed", op), ("Phishing.Database (ACTIVE links)", pdb)):
    for u in lst:
        b = uae_brand(u)
        if not b:
            continue
        h = host(u)
        if per_host.get(h, 0) >= 2:
            continue
        per_host[h] = per_host.get(h, 0) + 1
        uae_phish.append((u, b, src))
for u, b, src in uae_phish:
    add(u, 1, src, "uae", brand=b)
uae_urls = {u for u, _, _ in uae_phish}

# 2b. General phishing: all OpenPhish + Phishing.Database sample, 1 URL per host
gen_phish = []
for u in op:
    if u in uae_urls or host(u) in seen_hosts:
        continue
    seen_hosts.add(host(u)); gen_phish.append((u, "OpenPhish public feed"))
random.shuffle(pdb)
for u in pdb:
    if len(gen_phish) >= 1000:
        break
    if u in uae_urls or host(u) in seen_hosts:
        continue
    seen_hosts.add(host(u)); gen_phish.append((u, "Phishing.Database (ACTIVE links)"))
for u, src in gen_phish:
    add(u, 1, src, "general")

# ---------- 3. Benign: Chrome UX Report top origins (rank bucket <= 1000) ----------
crux = []
with gzip.open(f"{RAW}/crux.csv.gz", "rt") as f:
    r = csv.DictReader(f)
    for row in r:
        crux.append((row["origin"], int(row["rank"])))
BLOCK_WORDS = re.compile(r"porn|xxx|sex|escort|bet|casino|satta|matka|dpboss|gambl|torrent|crawler|hentai|nsfw|onlyfans|xhamster|xnxx|xvideo|jav|bunny|nude|adult|18|desi|bingo|lotto|slot|togel|movie|film|anime|manga|hdtoday|watch|stream|tube|leak|cam|hub|tits|flix|fap|erot|xh|annunci|beboo|milf|sukebei|nhentai|eporn|spank|[0-9][a-z0-9]{6,}\.", re.I)
top = [o for o, rk in crux if rk <= 1000 and not BLOCK_WORDS.search(o)]
phish_regdoms = {regdom(u) for u, _ in gen_phish} | {regdom(u) for u in uae_urls}
benign_gen = [o for o in top if regdom(o) not in phish_regdoms]
random.shuffle(benign_gen)
for o in benign_gen[:1000]:
    add(o + "/", 0, "Chrome UX Report top origins (rank <= 1000)", "general")

# ---------- 4. Benign UAE: official UAE origins found in the CrUX list ----------
UAE_OK = re.compile(r"\.gov\.ae$|(^|\.)(u\.ae|tamm\.abudhabi|uaepass\.ae|emiratesnbd\.com|adcb\.com|"
                    r"mashreq\.com|bankfab\.com|dib\.ae|adib\.ae|rakbank\.ae|rakbankonline\.ae|emiratespost\.ae|"
                    r"aramex\.com|eand\.ae|du\.ae|salik\.ae|adnocdistribution\.ae|adnoc\.ae|"
                    r"emirates\.com|etihad\.com|visitabudhabi\.ae|abudhabi\.ae|dubai\.ae)$")
uae_benign = sorted({o for o, rk in crux if UAE_OK.search(host(o))}, key=lambda o: o)
for o in uae_benign:
    add(o + "/", 0, "Chrome UX Report (official UAE origins)", "uae")

# ---------- 5. Synthetic UAE lookalikes (clearly marked) ----------
SYN = [
    ("tamm-abudhabi-pay.com", "TAMM", "/fines/pay"), ("tamm-gov-ae.net", "TAMM", "/login"),
    ("uaepass-verify.net", "UAE PASS", "/auth"), ("uae-pass-login.com", "UAE PASS", "/signin"),
    ("adpolice-fines-pay.com", "Abu Dhabi Police", "/violations"), ("dubaipolice-fine.com", "Dubai Police", "/pay"),
    ("emiratesnbd-secure.com", "Emirates NBD", "/update"), ("emirates-nbd-online.net", "Emirates NBD", "/login"),
    ("adcb-verify.com", "ADCB", "/otp"), ("mashreq-alert.com", "Mashreq", "/unlock"),
    ("bankfab-support.net", "FAB", "/card"), ("emiratespost-parcel.com", "Emirates Post", "/redelivery"),
    ("emirates-post-ae.info", "Emirates Post", "/fee"), ("aramex-delivery-ae.com", "Aramex", "/track"),
    ("salik-toll-pay.com", "Salik", "/balance"), ("darb-toll-ae.com", "Darb (ITC)", "/pay"),
    ("dewa-bill-refund.com", "DEWA", "/refund"), ("etisalat-points-ae.com", "e& (Etisalat)", "/redeem"),
    ("du-rewards-uae.com", "du", "/claim"), ("icp-visa-ae.com", "ICP", "/visa-renew"),
    ("mohre-ae-portal.com", "MOHRE", "/permit"), ("adnoc-fuel-gift.com", "ADNOC", "/gift"),
    ("rta-dubai-fines.com", "RTA", "/fines"), ("xn--tmm-vla.com", "TAMM", "/login"),
    ("uaepass.ae-login.co", "UAE PASS", "/"),
]
for d, b, p in SYN:
    add(f"https://{d}{p}", 1, "Synthetic lookalike (made up for testing; not a real report)", "uae",
        brand=b, synthetic=1, note="Invented name; may not exist. Never open in sandbox expecting content.")

# ---------- split: 50/50 dev/test, stratified by subset+label ----------
groups = {}
for r_ in rows:
    groups.setdefault((r_["subset"], r_["label"]), []).append(r_)
for g in groups.values():
    random.shuffle(g)
    for i, r_ in enumerate(g):
        r_["split"] = "dev" if i % 2 == 0 else "test"

cols = ["url", "label", "category", "subset", "brand", "source", "synthetic",
        "registered_domain", "split", "collected", "note"]
with open("scamshield_test_dataset.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)

from collections import Counter
c = Counter((r_["subset"], r_["category"], r_["source"]) for r_ in rows)
for k, v in sorted(c.items()):
    print(v, *k, sep=" | ")
print("TOTAL", len(rows))
print("UAE brands (real):", Counter(b for _, b, _ in uae_phish).most_common())
