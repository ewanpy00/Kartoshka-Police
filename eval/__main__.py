import csv
import os
import sys

import httpx

CORE_URL = os.environ.get("CORE_URL", "http://127.0.0.1:8000")


def ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def main(path: str) -> None:
    with open(path, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    response = httpx.post(
        f"{CORE_URL}/v1/batch",
        json={"urls": [row["url"] for row in rows]},
        timeout=max(60.0, len(rows)),
    )
    response.raise_for_status()
    blocked = {result["url"]: result["verdict"] == "block" for result in response.json()["results"]}

    tp = sum(1 for row in rows if row["label"] == "phish" and blocked[row["url"]])
    fn = sum(1 for row in rows if row["label"] == "phish" and not blocked[row["url"]])
    fp = sum(1 for row in rows if row["label"] == "benign" and blocked[row["url"]])
    tn = sum(1 for row in rows if row["label"] == "benign" and not blocked[row["url"]])

    print("                 predicted block  predicted allow")
    print(f"actual phish     {tp:>15}  {fn:>15}")
    print(f"actual benign    {fp:>15}  {tn:>15}")
    print(f"precision {ratio(tp, tp + fp):.3f}  recall {ratio(tp, tp + fn):.3f}  fpr {ratio(fp, fp + tn):.3f}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python -m eval <urls.csv>")
    main(sys.argv[1])
