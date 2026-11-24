"""Build the labelled evaluation set and the URL-model training set from downloaded feeds.

Usage (run on the host, feeds downloaded first):
    python eval/build_set.py <feeds_dir>

<feeds_dir> must hold openphish.txt (https://openphish.com/feed.txt), phishtank.csv.bz2
(http://data.phishtank.com/data/online-valid.csv.bz2), phishing-army.txt
(https://phishing.army/download/phishing_army_blocklist.txt) and top-1m.csv (Tranco).

Writes data/eval/test.csv (url,label,brand,origin), data/eval/holdout.csv and data/train/{phish,benign}.txt.
None of them share a URL or a domain. test.csv is the development set: weights and the cutoff were tuned on
it. holdout.csv was not looked at while tuning; report it as the honest number. Origins:
  openphish, phishtank   real phishing URLs from public feeds, labelled phish
  uae_synthetic          UAE-brand smishing patterns written from public reporting, labelled phish;
                         the scorer was designed with these patterns in mind, so report them separately
  uae_official           official UAE service URLs, labelled benign
  uae_benign             UAE businesses and media not on any allowlist, labelled benign
  brand_trap             benign sites whose names contain a brand token, labelled benign
  tranco_listed          sites in the allowlisted Tranco top 10k, labelled benign
  tranco_unlisted        Tranco ranks 10,001-20,000 (not allowlisted), labelled benign
"""
import bz2
import csv
import random
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
RNG = random.Random(20261124)

UAE_SYNTHETIC = [
    ("uaepass", "https://uaepass-verify.top/login"),
    ("uaepass", "https://uaepass-update.xyz/auth"),
    ("uaepass", "https://uae-pass-login.com/ar/"),
    ("uaepass", "https://uaepass.ae-verify.info/"),
    ("uaepass", "https://id-uaepass.online/otp"),
    ("uaepass", "https://uaepas.com/login"),
    ("uaepass", "https://verify-uaepass.web.app/"),
    ("uaepass", "https://uаepass.com/login"),
    ("uaepass", "https://uaepass-renew.cyou/account"),
    ("tamm", "https://tamm-fines-pay.top/"),
    ("tamm", "https://tamm-gov.com/pay"),
    ("tamm", "https://tamm-abudhabi-fines.info/"),
    ("tamm", "https://tammservices-ae.cc/payment"),
    ("tamm", "https://tamm.abudhabi.pay-fines.top/"),
    ("tamm", "https://mytamm-fine.shop/"),
    ("tamm", "https://tamm-fіnes.com/pay"),
    ("rta", "https://rta-ae-fines.top/pay"),
    ("rta", "https://rta-dubai-parking.com/fine"),
    ("rta", "https://rtadubai-salik.xyz/"),
    ("rta", "https://rta-gov.cc/"),
    ("dubaipolice", "https://dubaipolice-fines.online/"),
    ("dubaipolice", "https://dubai-police-gov.com/pay"),
    ("dubaipolice", "https://dubaip0lice.com/fines"),
    ("adpolice", "https://adpolice-fines.top/"),
    ("emiratespost", "https://emiratespost-redelivery.info/track"),
    ("emiratespost", "https://emiratespost-ae.cc/parcel"),
    ("emiratespost", "https://emirates-post-delivery.top/"),
    ("emiratespost", "https://emiratespost.parcel-fee.com/"),
    ("emiratespost", "https://emiratespostt.com/track"),
    ("salik", "https://salik-tolls.info/pay"),
    ("salik", "https://salik-topup.top/"),
    ("salik", "https://salik-ae.xyz/recharge"),
    ("icp", "https://icp-renew-id.com/"),
    ("icp", "https://emiratesid-renewal.top/"),
    ("icp", "https://icp-gov-ae.info/visa"),
    ("etisalat", "https://etisalat-rewards.icu/points"),
    ("etisalat", "https://etisalat-smiles.top/claim"),
    ("etisalat", "https://eand-rewards.xyz/"),
    ("dewa", "https://dewa-refund.top/"),
    ("dewa", "https://dewa-bill-pay.com/"),
    ("dewa", "https://dewa-gov.info/refund"),
    ("emiratesnbd", "https://emiratesnbd-secure.com/login"),
    ("emiratesnbd", "https://enbd-verify.top/"),
    ("adcb", "https://adcb-secure-login.com/"),
    ("adcb", "https://adcb-card-update.xyz/"),
    ("mashreq", "https://mashreq-otp.top/"),
    ("fab", "https://bankfab-verify.info/"),
    ("fab", "https://fabbank-update.online/"),
    ("darb", "https://darb-toll-fine.top/"),
    ("moi", "https://moiuae-fines.com/pay"),
    ("", "https://uae-traffic-fines.top/pay"),
    ("", "https://abudhabi-fines-pay.com/"),
    ("", "https://dubai-gov-fines.com/"),
    ("", "https://uae-customs-parcel.top/"),
    ("", "https://ae-post-track.info/"),
    ("tamm", "https://kd8x.top/tamm/pay"),
    ("uaepass", "https://qwz3.cyou/uaepass/login"),
    ("emiratespost", "https://bit-parcel.sbs/emiratespost"),
    ("", "http://185.220.101.4/uae/fines/pay.php"),
    ("uaepass", "https://sites.google.com/view/uaepass-verify-account"),
]

UAE_OFFICIAL = """https://uaepass.ae/
https://www.tamm.abudhabi/wb/adp/pay-traffic-fines
https://www.rta.ae/wps/portal/rta/ae/home
https://www.dubaipolice.gov.ae/wps/portal/home
https://www.adpolice.gov.ae/
https://www.emiratespost.ae/
https://icp.gov.ae/
https://www.salik.ae/
https://www.dewa.gov.ae/
https://www.addc.ae/
https://www.emiratesnbd.com/en
https://www.adcb.com/
https://www.bankfab.com/
https://www.mashreq.com/
https://www.dib.ae/
https://www.etisalat.ae/
https://www.du.ae/
https://u.ae/
https://www.mohre.gov.ae/
https://www.moi.gov.ae/
https://darb.itc.gov.ae/
https://www.dubai.ae/
https://www.smartdubai.ae/
https://gdrfad.gov.ae/
https://www.ajmanpolice.gov.ae/
https://www.shjpolice.gov.ae/""".split()

UAE_BENIGN = """https://www.dubaimall.com/
https://www.emaar.com/
https://www.damacproperties.com/
https://www.carrefouruae.com/
https://www.luluhypermarket.com/
https://www.sharafdg.com/
https://www.aldar.com/
https://www.yasisland.com/
https://www.visitdubai.com/
https://visitabudhabi.ae/
https://www.dubaiairports.ae/
https://www.etihad.com/
https://www.flydubai.com/
https://www.dubaiholding.com/
https://www.mallofthemirates.com/
https://www.gulfnews.com/uae/how-to-check-tamm-fines
https://www.khaleejtimes.com/uae/transport/salik-new-gates
https://www.thenationalnews.com/uae/government/uae-pass-update
https://www.zomato.com/dubai
https://www.bayut.com/
https://www.propertyfinder.ae/
https://www.dubizzle.com/
https://www.noon.com/uae-en/
https://www.talabat.com/uae
https://www.careem.com/""".split()

BRAND_TRAPS = """https://www.tammam-restaurant.com/
https://www.dewan-architects.com/
https://www.salikhan-photography.com/
https://www.rtaxi-booking.com/
https://www.darbar-indian-cuisine.com/
https://www.eandersen.dk/
https://www.icpdas.com/
https://www.fabric-store.com/
https://www.mashreqia-cafe.com/
https://www.post-and-parcel.com/""".split()


def host(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


def read_tranco(path: Path) -> list[str]:
    with path.open() as handle:
        return [line.strip().split(",")[1] for line in handle if "," in line]


def main(feeds: Path) -> None:
    tranco = read_tranco(feeds / "top-1m.csv")
    openphish = [u.strip() for u in (feeds / "openphish.txt").read_text().splitlines() if u.startswith("http")]
    with bz2.open(feeds / "phishtank.csv.bz2", "rt", encoding="utf-8", errors="replace") as handle:
        phishtank = [row["url"] for row in csv.DictReader(handle) if row.get("url", "").startswith("http")]
    army = [line.strip() for line in (feeds / "phishing-army.txt").read_text().splitlines() if line and not line.startswith("#")]

    RNG.shuffle(openphish)
    RNG.shuffle(phishtank)
    RNG.shuffle(army)
    unlisted = tranco[10000:20000]
    RNG.shuffle(unlisted)

    rows = []
    rows += [(u, "phish", "", "openphish") for u in openphish[:150]]
    rows += [(u, "phish", "", "phishtank") for u in phishtank[:150]]
    rows += [(u, "phish", b, "uae_synthetic") for b, u in UAE_SYNTHETIC]
    rows += [(u, "benign", "", "uae_official") for u in UAE_OFFICIAL]
    rows += [(u, "benign", "", "uae_benign") for u in UAE_BENIGN]
    rows += [(u, "benign", "", "brand_trap") for u in BRAND_TRAPS]
    rows += [(f"https://{d}/", "benign", "", "tranco_listed") for d in RNG.sample(tranco[:10000], 40)]
    rows += [(f"https://{d}/", "benign", "", "tranco_unlisted") for d in unlisted[:150]]

    holdout = []
    holdout += [(u, "phish", "", "openphish") for u in openphish[150:300]]
    holdout += [(u, "phish", "", "phishtank") for u in phishtank[150:300]]
    holdout += [(f"https://{d}/", "benign", "", "tranco_unlisted") for d in unlisted[150:300]]

    test_hosts = {host(u) for u, *_ in rows + holdout}
    test_domains = {".".join(h.split(".")[-2:]) for h in test_hosts}

    def disjoint(url: str) -> bool:
        h = host(url)
        return h not in test_hosts and ".".join(h.split(".")[-2:]) not in test_domains

    train_phish = [u for u in phishtank[300:] if disjoint(u)][:3000]
    train_phish += [f"https://{d}/" for d in army[:2000] if disjoint(f"https://{d}/")]
    train_benign = [f"https://{d}/" for d in tranco[20000:26000] if disjoint(f"https://{d}/")]

    out = ROOT / "data" / "eval" / "test.csv"
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["url", "label", "brand", "origin"])
        writer.writerows(rows)
    with (ROOT / "data" / "eval" / "holdout.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["url", "label", "brand", "origin"])
        writer.writerows(holdout)
    train = ROOT / "data" / "train"
    train.mkdir(exist_ok=True)
    (train / "phish.txt").write_text("# PhishTank online-valid and Phishing Army, 2026-11-24. Disjoint from data/eval/.\n" + "\n".join(train_phish) + "\n")
    (train / "benign.txt").write_text("# Tranco ranks 20,001-26,000. Disjoint from data/eval/.\n" + "\n".join(train_benign) + "\n")
    print(f"test rows {len(rows)}, holdout rows {len(holdout)}; train phish {len(train_phish)}, benign {len(train_benign)}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python eval/build_set.py <feeds_dir>")
    main(Path(sys.argv[1]))
