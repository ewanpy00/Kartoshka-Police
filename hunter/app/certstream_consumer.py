"""Hunter main process: Certificate Transparency consumer plus the scheduled sources (app.sources).

Every certificate's names go through the name filter and the infrastructure filter (app.filters); the
candidates go to core in batches (app.submit). Infrastructure-only candidates are capped per minute.
"""
import asyncio
import json
import logging
import os
import re
import sys
import time
from pathlib import Path

import websockets
import yaml

from app import filters, sources
from app.health import HEARTBEAT_PATH
from app.submit import Entry, Submitter

CERTSTREAM_URL = os.environ.get("CERTSTREAM_URL", "ws://certstream:8080/")
DATA_DIR = Path(os.environ.get("DATA_DIR", "/srv/data"))
STATS_INTERVAL_SECONDS = 30
MAX_BACKOFF_SECONDS = 60
# Infrastructure-only candidates (random names on risky TLDs) are plentiful and each one lands in the
# officer queue, so they are capped; core's fast score decides which of them are worth a deep look.
INFRA_PER_MINUTE = int(os.environ.get("HUNTER_INFRA_PER_MINUTE", "5"))
HOSTNAME = re.compile(r"[A-Za-z0-9*._-]+")

log = logging.getLogger("hunter")


class Counters:
    def __init__(self) -> None:
        self.certificates = 0
        self.matches = 0
        self.infra = 0
        self.infra_window = 0.0
        self.infra_in_window = 0

    def infra_allowed(self, now: float) -> bool:
        if now - self.infra_window >= 60:
            self.infra_window, self.infra_in_window = now, 0
        if self.infra_in_window >= INFRA_PER_MINUTE:
            return False
        self.infra_in_window += 1
        return True


async def log_stats(counters: Counters, submitter: Submitter | None = None) -> None:
    while True:
        await asyncio.sleep(STATS_INTERVAL_SECONDS)
        log.info("stats window=%ds certificates=%d matches=%d infra=%d submitted=%d",
                 STATS_INTERVAL_SECONDS, counters.certificates, counters.matches, counters.infra,
                 submitter.sent if submitter else 0)
        counters.certificates = counters.matches = counters.infra = 0


def certificate_domains(raw: str | bytes) -> list[str] | None:
    message = json.loads(raw)
    if message["message_type"] != "certificate_update":
        return None
    domains = message["data"]["leaf_cert"]["all_domains"]
    if not isinstance(domains, list):
        raise ValueError("all_domains is not a list")
    return [domain for domain in domains if isinstance(domain, str) and HOSTNAME.fullmatch(domain)]


def handle_message(raw: str | bytes, prepared, counters: Counters, submitter: Submitter | None = None,
                   now: float | None = None) -> list[filters.Candidate]:
    try:
        domains = certificate_domains(raw)
        if domains is None:
            return []
    except Exception as error:
        log.warning("skipping malformed message: %r", error)
        return []
    counters.certificates += 1
    now = now if now is not None else time.time()
    found, hosts = [], set()
    for domain in domains:
        host = filters.clean_host(domain)
        if host is None or host in hosts:
            continue
        hosts.add(host)
        if submitter is not None and not submitter.fresh("ct", host, now):
            continue
        candidate = filters.name_match(host, prepared)
        if candidate is None:
            candidate = filters.infra_match(host)
            if candidate is None or not counters.infra_allowed(now):
                continue
            counters.infra += 1
        else:
            counters.matches += 1
        found.append(candidate)
        log.info("candidate kind=%s brand=%s domain=%s", candidate.kind, candidate.brand_id, candidate.host)
        if submitter is not None:
            submitter.add(Entry("ct", f"https://{candidate.host}/", candidate.brand_id,
                                f"{candidate.kind}: {candidate.detail}"), now)
    return found


async def consume(ws, prepared, counters: Counters, submitter: Submitter) -> None:
    loop = asyncio.get_running_loop()
    last_beat = 0.0
    async for raw in ws:
        now = loop.time()
        if now - last_beat >= 1:
            HEARTBEAT_PATH.touch()
            last_beat = now
        handle_message(raw, prepared, counters, submitter)


async def stream(prepared, counters: Counters, submitter: Submitter) -> None:
    backoff = 1
    while True:
        try:
            async with websockets.connect(CERTSTREAM_URL, max_size=2**22) as ws:
                log.info("connected to %s", CERTSTREAM_URL)
                backoff = 1
                await consume(ws, prepared, counters, submitter)
            log.warning("stream closed, reconnecting in %ds", backoff)
        except (OSError, websockets.WebSocketException) as error:
            log.warning("stream failed (%s), reconnecting in %ds", error, backoff)
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, MAX_BACKOFF_SECONDS)


def load_prepared() -> list:
    brands = yaml.safe_load((DATA_DIR / "brands.yaml").read_text(encoding="utf-8"))
    return filters.prepare(brands)


async def main() -> None:
    prepared = load_prepared()
    counters = Counters()
    submitter = Submitter()
    tasks = [log_stats(counters, submitter), submitter.run()]
    if sources.enabled("ct"):
        tasks.append(stream(prepared, counters, submitter))
    else:
        tasks.append(heartbeat())
    if sources.enabled("feeds"):
        tasks.append(sources.poll_feeds(submitter, prepared))
    if sources.enabled("nrd"):
        tasks.append(sources.poll_nrd(submitter, prepared))
    if sources.enabled("watchlist"):
        tasks.append(sources.tick_watchlist())
    await asyncio.gather(*tasks)


async def heartbeat() -> None:
    while True:
        HEARTBEAT_PATH.touch()
        await asyncio.sleep(10)


if __name__ == "__main__":
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    asyncio.run(main())
