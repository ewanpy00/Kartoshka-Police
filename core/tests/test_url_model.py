import random

from app.ai import url_model

REAL_PREDICT = url_model.predict  # bound at import, before the offline fixture stubs it


def test_featurize_returns_every_model_feature():
    features = url_model.featurize("https://tamm-fines.top/pay?id=1")
    assert set(url_model.FEATURES) <= set(features)
    assert features["risky_tld"] == 1
    assert features["query_params"] == 1


def test_augment_gives_benign_homepages_paths_and_subdomains():
    rng = random.Random(1)
    urls = [url_model.augment("https://example.com/", rng) for _ in range(50)]
    assert any(u.count("/") > 3 for u in urls)
    assert any(not u.startswith("https://example.com") for u in urls)
    assert all("example.com" in u for u in urls)


def test_predict_is_none_without_a_model(monkeypatch):
    monkeypatch.setattr(url_model, "load", lambda: url_model._state.update(booster=None, loaded_at=1e12))
    url_model._state["loaded_at"] = 0.0
    assert REAL_PREDICT({}) is None
