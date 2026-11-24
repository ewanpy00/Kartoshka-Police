"""Backtest the Hunter filters on a labelled URL set (the eval CSVs: url,label,brand,origin).

    python -m app.backtest /srv/data/eval/test.csv [/srv/data/eval/holdout.csv]

Reports, per set: how many UAE-brand phishing URLs the name filter would have flagged (the share of known
UAE scams Hunter catches from CT or NRD), how many phishing URLs either filter flags, and how many benign
URLs would have become candidates (the load on core). Lead time needs CT timestamps per domain and is
measured live on the console's Impact page instead.
"""
import csv
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

import yaml

from app import filters
from app.certstream_consumer import DATA_DIR


def run(path: Path, prepared) -> dict:
    counts: Counter = Counter()
    missed = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            host = filters.clean_host(urlsplit(row["url"]).hostname or "")
            if host is None:
                continue
            phish = row["label"] == "phish"
            uae = phish and (row.get("origin", "").startswith("uae") or bool(row.get("brand")))
            name = filters.name_match(host, prepared)
            any_hit = name or filters.infra_match(host)
            counts["phish" if phish else "benign"] += 1
            counts["uae_phish"] += uae
            counts["uae_named"] += bool(uae and name)
            counts["uae_any"] += bool(uae and any_hit)
            counts["phish_flagged"] += bool(phish and any_hit)
            counts["benign_flagged"] += bool(not phish and any_hit)
            if uae and not any_hit:
                missed.append(host)
    rate = lambda a, b: round(counts[a] / counts[b], 3) if counts[b] else None  # noqa: E731
    return {"file": path.name, **counts, "uae_recall": rate("uae_named", "uae_phish"), "uae_any_recall": rate("uae_any", "uae_phish"),
            "phish_flag_rate": rate("phish_flagged", "phish"), "benign_flag_rate": rate("benign_flagged", "benign"),
            "uae_missed": missed[:15]}


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    prepared = filters.prepare(yaml.safe_load((DATA_DIR / "brands.yaml").read_text(encoding="utf-8")))
    for name in argv:
        result = run(Path(name), prepared)
        print(f"{result['file']}: UAE-brand phishing flagged by name {result['uae_named']}/{result['uae_phish']} "
              f"({result['uae_recall']}), by either filter {result['uae_any']} ({result['uae_any_recall']}); any phishing flagged {result['phish_flagged']}/{result['phish']} "
              f"({result['phish_flag_rate']}); benign flagged {result['benign_flagged']}/{result['benign']} "
              f"({result['benign_flag_rate']})")
        if result["uae_missed"]:
            print("  missed:", ", ".join(result["uae_missed"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
