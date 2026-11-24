"""A3 baseline: perceptual hash of the phone screenshot against the official pages of each brand.

The reference hashes live in the database (model_state, key `visual_refs`). Build them with `make refs`,
which runs `python -m app.deep.visual refs` in the worker (only the worker can reach the sandbox) and
captures every brand's reference pages with the same phone profile the deep path uses. The images stay
in the captures volume; only their hashes are stored.

CLIP would see layout and logos better, but it needs PyTorch, which does not fit next to the stack in a
4 GB Docker VM (docs/app-plan.md, decision 6). `best_match` is the seam where it would plug in.
"""
import argparse
import sys
from datetime import UTC, datetime

import httpx
import numpy as np
from PIL import Image
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.brands import is_official, load_brands
from app.config import get_settings
from app.models import ModelState

REFS_KEY = "visual_refs"
MATCH_FROM = 0.875  # at most 8 of 64 bits differ
SIZE = 32


def _dct_matrix(n: int) -> np.ndarray:
    k = np.arange(n)[:, None]
    i = np.arange(n)[None, :]
    matrix = np.cos(np.pi * (2 * i + 1) * k / (2 * n)) * np.sqrt(2 / n)
    matrix[0] /= np.sqrt(2)
    return matrix


DCT = _dct_matrix(SIZE)


def load_gray(path: str) -> np.ndarray:
    with Image.open(path) as image:
        return np.asarray(image.convert("L").resize((SIZE, SIZE), Image.Resampling.LANCZOS), dtype=np.float64)


def phash(path: str) -> int:
    """64-bit pHash: the low 8x8 DCT coefficients of a 32x32 grey image, above or below their median."""
    low = (DCT @ load_gray(path) @ DCT.T)[:8, :8].flatten()
    bits = low > np.median(low)
    return int("".join("1" if bit else "0" for bit in bits), 2)


def is_blank(path: str) -> bool:
    """A near-uniform screenshot (blank, error or loading page) matches everything; skip it."""
    return float(load_gray(path).std()) < 6.0


def similarity(a: int, b: int) -> float:
    return 1.0 - bin(a ^ b).count("1") / 64


def load_refs(session: Session) -> list[dict]:
    row = session.get(ModelState, REFS_KEY)
    return list(row.value.get("refs", [])) if row else []


def best_match(session: Session, screenshot_path: str, host: str, brands: list[dict]) -> dict | None:
    """The closest reference of a brand whose official domains do not include host, if close enough."""
    refs = load_refs(session)
    if not refs or is_blank(screenshot_path):
        return None
    by_id = {brand["id"]: brand for brand in brands}
    value = phash(screenshot_path)
    best = None
    for ref in refs:
        brand = by_id.get(ref["brand_id"])
        if brand is None or is_official(host, brand):
            continue
        score = similarity(value, int(ref["hash"], 16))
        if best is None or score > best["similarity"]:
            best = {"brand": brand, "similarity": round(score, 3), "reference_url": ref["url"], "hash": f"{value:016x}"}
    if best is None or best["similarity"] < MATCH_FROM:
        return None
    return best


def reference_urls(brand: dict) -> list[str]:
    return brand.get("reference_urls") or [f"https://{brand['official_domains'][0]}/"]


def capture_one(url: str, sandbox_url: str) -> tuple[str | None, str | None]:
    """(screenshot path, error). Two attempts: slow official sites often time out or render blank once."""
    error = None
    for _attempt in range(2):
        try:
            response = httpx.post(f"{sandbox_url}/capture", timeout=90, json={"url": url, "timeout_ms": 40000, "settle_ms": 3000})
            response.raise_for_status()
            path = response.json().get("screenshot_path")
        except (httpx.HTTPError, ValueError) as caught:
            error = repr(caught)
            continue
        if path and not is_blank(path):
            return path, None
        error = "blank page"
    return None, error


def capture_refs(session: Session, missing_only: bool = False) -> list[dict]:
    settings = get_settings()
    refs = load_refs(session) if missing_only else []
    have = {ref["brand_id"] for ref in refs}
    for brand in load_brands(settings.data_dir):
        if brand["id"] in have:
            continue
        for url in reference_urls(brand):
            path, error = capture_one(url, settings.sandbox_url)
            if path is None:
                print(f"  {brand['id']:<14} {url}  skipped: {error}"[:160])
                continue
            refs.append({"brand_id": brand["id"], "url": url, "hash": f"{phash(path):016x}", "path": path,
                         "captured_at": datetime.now(UTC).isoformat()})
            print(f"  {brand['id']:<14} {url}  {refs[-1]['hash']}")
    value = {"refs": refs}
    statement = insert(ModelState).values(key=REFS_KEY, value=value, score=float(len(refs)))
    session.execute(statement.on_conflict_do_update(index_elements=[ModelState.key], set_={"value": value, "score": float(len(refs))}))
    session.commit()
    return refs


def main(argv: list[str]) -> int:
    from app.db import get_engine

    parser = argparse.ArgumentParser(prog="python -m app.deep.visual")
    parser.add_argument("command", choices=["refs"])
    parser.add_argument("--missing", action="store_true", help="keep stored hashes; capture only brands without one")
    args = parser.parse_args(argv)
    with Session(get_engine()) as session:
        refs = capture_refs(session, missing_only=args.missing)
    print(f"stored {len(refs)} reference hashes")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
