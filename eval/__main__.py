"""kartoshka eval: precision, recall, FPR, confusion matrix, per-brand and per-origin rows, ablation.

    python -m eval data/eval/test.csv [--cutoff 70] [--core http://127.0.0.1:8000]

Reads a CSV with `url,label` (labels `phish` or `benign`) and optional `brand` and `origin` columns,
sends the URLs to `/v1/batch?explain=true` and scores the answers. The ablation recomputes each score
from the returned reasons with only some signal groups switched on.
"""
import argparse
import csv
import os
import sys
from collections import defaultdict

import httpx

CORE_URL = os.environ.get("CORE_URL", "http://127.0.0.1:8000")
CHUNK = 100
LIST_CODES = {"ALLOWLISTED", "BLOCKLISTED", "OFFICER_CONFIRMED", "OFFICER_CLEARED"}
ABLATION = [
    ("rules (lexical)", {"kartoshka"}),
    ("+ domain age, CT", {"kartoshka", "rdap", "ct"}),
    ("+ GSB, VT, feeds", {"kartoshka", "rdap", "ct", "gsb", "virustotal", "feeds"}),
    ("+ campaign graph", {"kartoshka", "rdap", "ct", "gsb", "virustotal", "feeds", "campaign"}),
    ("+ URL model (full fast path)", {"kartoshka", "rdap", "ct", "gsb", "virustotal", "feeds", "campaign", "model"}),
    ("+ deep (sandbox, AI)", None),
]


def ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


class Counts:
    def __init__(self) -> None:
        self.tp = self.fp = self.fn = self.tn = 0

    def add(self, phish: bool, blocked: bool) -> None:
        if phish and blocked:
            self.tp += 1
        elif phish:
            self.fn += 1
        elif blocked:
            self.fp += 1
        else:
            self.tn += 1

    def line(self) -> str:
        return (f"precision {ratio(self.tp, self.tp + self.fp):.3f}  recall {ratio(self.tp, self.tp + self.fn):.3f}  "
                f"fpr {ratio(self.fp, self.fp + self.tn):.3f}  (tp {self.tp} fp {self.fp} fn {self.fn} tn {self.tn})")


def partial_score(reasons: list[dict], groups: set[str] | None) -> int:
    if any(r["code"] in LIST_CODES for r in reasons):
        return sum(r["weight"] or 0 for r in reasons)
    return min(100, sum((r["weight"] or 0) for r in reasons if groups is None or r["source"] in groups))


def fetch(core: str, urls: list[str]) -> dict[str, dict]:
    results = {}
    with httpx.Client(timeout=300) as client:
        for start in range(0, len(urls), CHUNK):
            response = client.post(f"{core}/v1/batch", params={"explain": "true"}, json={"urls": urls[start : start + CHUNK]})
            response.raise_for_status()
            for row in response.json()["results"]:
                results[row["url"]] = row
            print(f"  checked {min(start + CHUNK, len(urls))}/{len(urls)}", file=sys.stderr)
    return results


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m eval")
    parser.add_argument("csv")
    parser.add_argument("--cutoff", type=int, default=None, help="block at or above this score (default: core's BATCH_CUTOFF)")
    parser.add_argument("--core", default=CORE_URL)
    args = parser.parse_args(argv)

    with open(args.csv, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    results = fetch(args.core, [row["url"] for row in rows])
    with httpx.Client(timeout=30) as client:
        cutoff = args.cutoff if args.cutoff is not None else client.post(f"{args.core}/v1/batch", json={"urls": []}).json()["cutoff"]

    overall, by_origin, by_brand = Counts(), defaultdict(Counts), defaultdict(Counts)
    misses = []
    for row in rows:
        result = results[row["url"]]
        phish = row["label"] == "phish"
        blocked = result["score"] >= cutoff
        overall.add(phish, blocked)
        by_origin[row.get("origin") or "-"].add(phish, blocked)
        if row.get("brand"):
            by_brand[row["brand"]].add(phish, blocked)
        if phish != blocked:
            misses.append((row.get("origin", "-"), row["label"], result["score"], row["url"]))

    print(f"\ncutoff {cutoff}  rows {len(rows)}")
    print("                 predicted block  predicted allow")
    print(f"actual phish     {overall.tp:>15}  {overall.fn:>15}")
    print(f"actual benign    {overall.fp:>15}  {overall.tn:>15}")
    print(overall.line())

    print("\nper origin")
    for origin, counts in sorted(by_origin.items()):
        print(f"  {origin:<16} {counts.line()}")
    if by_brand:
        print("\nper brand (UAE rows)")
        for brand, counts in sorted(by_brand.items()):
            print(f"  {brand:<16} recall {ratio(counts.tp, counts.tp + counts.fn):.3f}  ({counts.tp}/{counts.tp + counts.fn})")

    print("\nablation (score rebuilt from the returned reasons)")
    for name, groups in ABLATION:
        counts = Counts()
        for row in rows:
            counts.add(row["label"] == "phish", partial_score(results[row["url"]].get("reasons") or [], groups) >= cutoff)
        print(f"  {name:<30} {counts.line()}")

    print("\ncutoff sweep (full fast path)")
    for value in (30, 40, 50, 60, 70, 80):
        counts = Counts()
        for row in rows:
            counts.add(row["label"] == "phish", results[row["url"]]["score"] >= value)
        print(f"  >= {value:<3} {counts.line()}")

    if misses:
        print(f"\nfirst misses ({len(misses)} total)")
        for origin, label, score, url in misses[:25]:
            print(f"  {origin:<16} {label:<6} {score:>3}  {url[:90]}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
