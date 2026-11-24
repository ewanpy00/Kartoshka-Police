import asyncio
import json
import logging
import os
import re
import sys
from pathlib import Path

import websockets
import yaml

from app.health import HEARTBEAT_PATH
from app.matcher import match_domains
from app.submitter import Submitter

CERTSTREAM_URL = os.environ.get("CERTSTREAM_URL", "ws://certstream:8080/")
DATA_DIR = Path(os.environ.get("DATA_DIR", "/srv/data"))
STATS_INTERVAL_SECONDS = 30
MAX_BACKOFF_SECONDS = 60
CORE_URL = os.environ.get("CORE_URL", "http://core:8000")
CORE_WRITE_TOKEN = os.environ.get("CORE_WRITE_TOKEN", "")
SUBMIT_PER_MIN = int(os.environ.get("HUNTER_SUBMIT_PER_MIN", "6"))
HOSTNAME = re.compile(r"[A-Za-z0-9*._-]+")

log = logging.getLogger("hunter")


class Counters:
    def __init__(self) -> None:
        self.certificates = 0
        self.matches = 0


async def log_stats(counters: Counters) -> None:
    while True:
        await asyncio.sleep(STATS_INTERVAL_SECONDS)
        log.info(
            "stats window=%ds certificates=%d matches=%d",
            STATS_INTERVAL_SECONDS,
            counters.certificates,
            counters.matches,
        )
        counters.certificates = 0
        counters.matches = 0


def certificate_domains(raw: str | bytes) -> list[str] | None:
    message = json.loads(raw)
    if message["message_type"] != "certificate_update":
        return None
    domains = message["data"]["leaf_cert"]["all_domains"]
    if not isinstance(domains, list):
        raise ValueError("all_domains is not a list")
    return [
        domain
        for domain in domains
        if isinstance(domain, str) and HOSTNAME.fullmatch(domain)
    ]


def handle_message(raw: str | bytes, brands: list[dict], counters: Counters) -> list[str]:
    try:
        domains = certificate_domains(raw)
        if domains is None:
            return []
        found = match_domains(domains, brands)
    except Exception as error:
        log.warning("skipping malformed message: %r", error)
        return []
    counters.certificates += 1
    for brand_id, domain in found:
        counters.matches += 1
        log.info("match brand=%s domain=%s", brand_id, domain)
    return [domain for _, domain in found]


async def consume(ws, brands: list[dict], counters: Counters, submitter: Submitter) -> None:
    loop = asyncio.get_running_loop()
    last_beat = 0.0
    async for raw in ws:
        now = loop.time()
        if now - last_beat >= 1:
            HEARTBEAT_PATH.touch()
            last_beat = now
        for domain in handle_message(raw, brands, counters):
            await asyncio.to_thread(submitter.submit, domain)


async def main() -> None:
    brands = yaml.safe_load((DATA_DIR / "brands.yaml").read_text(encoding="utf-8"))
    counters = Counters()
    submitter = Submitter(CORE_URL, CORE_WRITE_TOKEN, SUBMIT_PER_MIN)
    stats_task = asyncio.create_task(log_stats(counters))
    backoff = 1
    while True:
        try:
            async with websockets.connect(CERTSTREAM_URL) as ws:
                log.info("connected to %s", CERTSTREAM_URL)
                backoff = 1
                await consume(ws, brands, counters, submitter)
            log.warning("stream closed, reconnecting in %ds", backoff)
        except (OSError, websockets.WebSocketException) as error:
            log.warning("stream failed (%s), reconnecting in %ds", error, backoff)
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, MAX_BACKOFF_SECONDS)


if __name__ == "__main__":
    logging.basicConfig(
        stream=sys.stdout,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    asyncio.run(main())
