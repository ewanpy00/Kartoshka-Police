"""A1 URL model: LightGBM over the lexical features. Optional: used only when a trained model exists.

The trained model lives in the database (model_state, key `url_model`), so the read-only data mount is not
a problem and every core and worker process loads the same one.

Train:  python -m app.ai.url_model train /srv/data/train/phish.txt /srv/data/train/benign.txt
Each input file has one URL per line. Labels come from the files, never from the model's own output.
"""
import argparse
import logging
import random
import sys
import time

from app.config import get_settings

log = logging.getLogger("core.url_model")

KEY = "url_model"
RELOAD_S = 300
FEATURES = [
    "brand_in_domain", "brand_in_subdomain", "brand_in_path", "lookalike_distance", "homoglyph", "mixed_scripts",
    "punycode", "action_words_host", "action_words_path", "risky_tld", "gov_lookalike", "ip_host", "userinfo",
    "free_hosting", "redirect_hops", "host_length", "subdomain_depth", "hyphens", "digits", "entropy",
    "random_name", "non_standard_port", "https", "path_length", "query_params", "path_depth", "path_php",
    "path_html", "host_dots", "label_length", "subdomain_length", "tld_length", "brand_any",
    "query_length",
]

_state: dict = {"booster": None, "loaded_at": 0.0, "features": FEATURES}


def vector(features: dict, names: list[str] = FEATURES) -> list[float]:
    return [float(features.get(name, 0) or 0) for name in names]


def load() -> None:
    _state["loaded_at"] = time.monotonic()
    try:
        import lightgbm
        from sqlalchemy.orm import Session

        from app.db import get_engine
        from app.models import ModelState

        with Session(get_engine()) as session:
            row = session.get(ModelState, KEY)
        if row is None:
            _state["booster"] = None
            return
        _state["booster"] = lightgbm.Booster(model_str=row.value["model"])
        _state["features"] = row.value.get("features", FEATURES)
    except Exception as error:
        log.warning("url model not loaded: %r", error)
        _state["booster"] = None


def predict(features: dict) -> float | None:
    if time.monotonic() - _state["loaded_at"] > RELOAD_S or _state["loaded_at"] == 0.0:
        load()
    booster = _state["booster"]
    if booster is None:
        return None
    return float(booster.predict([vector(features, _state["features"])])[0])


def featurize(url: str) -> dict:
    from app.brands import scoring_brands
    from app.fast.lexical import lexical
    from app.normalize.url import normalize

    return lexical(normalize(url), scoring_brands(get_settings().data_dir))[1]


BENIGN_PATHS = [
    "/about", "/en/", "/ar/home", "/contact-us", "/news/{year}/{month}/{slug}", "/products/{slug}", "/blog/{slug}",
    "/en-ae/shop/{slug}?ref=nav", "/search?q={word}", "/help/articles/{num}", "/careers", "/privacy-policy",
    "/category/{word}/{slug}", "/wp-content/uploads/{year}/{month}/{word}.jpg", "/account/login", "/login",
    "/user/{word}", "/watch?v={id}", "/p/{id}", "/docs/{word}/{slug}.html", "/index.php?page={word}",
]
WORDS = ["travel", "sports", "dubai", "offers", "summer", "phones", "garden", "health", "music", "recipes", "cars"]


SUBDOMAINS = ["www", "www", "www", "shop", "blog", "m", "en", "app", "news", "support", "my", "store", "help", "docs", "ar"]


def augment(url: str, rng: random.Random) -> str:
    """Give bare homepages the subdomains and paths real benign links have, so neither alone separates
    the classes (the benign list is registrable domains; phishing URLs come with both)."""
    if rng.random() < 0.75:
        url = url.replace("://", f"://{rng.choice(SUBDOMAINS)}.", 1)
    if rng.random() < 0.65:
        slug = "-".join(rng.sample(WORDS, rng.randint(1, 4)))
        path = rng.choice(BENIGN_PATHS).format(
            year=rng.randint(2015, 2026), month=f"{rng.randint(1, 12):02d}", slug=slug, word=rng.choice(WORDS),
            num=rng.randint(100, 999999), id="".join(rng.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(11)),
        )
        url = url.rstrip("/") + path
    return url


def train(phish: list[str], benign: list[str]) -> dict:
    import lightgbm
    import numpy as np
    from sqlalchemy.dialects.postgresql import insert
    from sqlalchemy.orm import Session

    from app.db import get_engine
    from app.models import ModelState

    rng = random.Random(11)
    benign = [augment(url, rng) for url in benign]
    rows = [(featurize(url), 1) for url in phish] + [(featurize(url), 0) for url in benign]
    random.Random(7).shuffle(rows)
    split = int(len(rows) * 0.8)
    x = np.array([vector(f) for f, _ in rows])
    y = np.array([label for _, label in rows])
    params = {"objective": "binary", "learning_rate": 0.08, "num_leaves": 15, "min_data_in_leaf": 20, "verbose": -1,
              "feature_fraction": 0.9, "seed": 7}
    model = lightgbm.train(params, lightgbm.Dataset(x[:split], y[:split], feature_name=FEATURES), num_boost_round=200)
    probabilities = model.predict(x[split:])
    metrics = {"train_rows": split, "holdout_rows": len(rows) - split}
    actual = y[split:] == 1
    for threshold in (0.5, 0.8, 0.9):
        predicted = probabilities >= threshold
        tp = int((predicted & actual).sum())
        fp = int((predicted & ~actual).sum())
        fn = int((~predicted & actual).sum())
        metrics[f"precision@{threshold}"] = round(tp / (tp + fp), 3) if tp + fp else 0.0
        metrics[f"recall@{threshold}"] = round(tp / (tp + fn), 3) if tp + fn else 0.0
    importance = sorted(zip(FEATURES, model.feature_importance("gain")), key=lambda item: -item[1])[:8]
    metrics["top_features"] = [name for name, _ in importance]
    value = {"model": model.model_to_string(), "features": FEATURES, "metrics": metrics}
    with Session(get_engine()) as session:
        statement = insert(ModelState).values(key=KEY, value=value, score=metrics["precision@0.8"])
        session.execute(statement.on_conflict_do_update(index_elements=[ModelState.key], set_={"value": value, "score": metrics["precision@0.8"]}))
        session.commit()
    load()
    return metrics


LABEL_WEIGHT = 3  # an officer label counts as this many feed rows


def officer_labels(session) -> tuple[list[str], list[str]]:
    """A7: every officer decision is a label. Confirm marks the checked URLs phishing; a reject for
    `legitimate_site` or `not_a_scam` marks them benign. Other rejects say nothing about the URL."""
    from sqlalchemy import select

    from app.models import Check, Evidence, Review
    from app.review import CLEARING

    phish, benign = [], []
    rows = session.execute(
        select(Review.decision, Review.reason, Check.url, Check.final_url)
        .join(Evidence, Evidence.id == Review.evidence_id).join(Check, Check.id == Evidence.check_id)
    ).all()
    for decision, reason_code, url, final_url in rows:
        target = phish if decision == "confirm" else benign if reason_code in CLEARING else None
        if target is not None:
            target.extend(dict.fromkeys(u for u in (url, final_url) if u))
    return phish, benign


def retrain(phish_path: str, benign_path: str) -> dict:
    from sqlalchemy.orm import Session

    from app.db import get_engine

    with Session(get_engine()) as session:
        phish, benign = officer_labels(session)
    metrics = train(read_urls(phish_path) + phish * LABEL_WEIGHT, read_urls(benign_path) + benign * LABEL_WEIGHT)
    return {**metrics, "officer_phish": len(phish), "officer_benign": len(benign)}


def read_urls(path: str) -> list[str]:
    with open(path, encoding="utf-8") as handle:
        return [line.strip() for line in handle if line.strip() and not line.startswith("#")]


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.ai.url_model")
    sub = parser.add_subparsers(dest="command", required=True)
    train_cmd = sub.add_parser("train")
    train_cmd.add_argument("phish")
    train_cmd.add_argument("benign")
    retrain_cmd = sub.add_parser("retrain", help="train again with officer decisions added as labels (A7)")
    retrain_cmd.add_argument("phish")
    retrain_cmd.add_argument("benign")
    args = parser.parse_args(argv)
    if args.command == "retrain":
        print(retrain(args.phish, args.benign))
    else:
        print(train(read_urls(args.phish), read_urls(args.benign)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
