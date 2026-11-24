"""Scheduled Hunter sources besides CT (ARCHITECTURE.md section 2).

| Source                   | Every       | Filter                                    | Core check |
|--------------------------|-------------|-------------------------------------------|------------|
| OpenPhish, URLhaus (key) | 30 minutes  | a UAE brand in the host or in the path    | deep       |
| WhoisDS newly registered | 24 hours    | name filter (look-alike names only)       | screen     |
| Watchlist ticker         | 5 minutes   | none: asks core to re-check due domains   | core does  |

Each source can be turned off with `HUNTER_SOURCES` (comma list of ct, feeds, nrd, watchlist).
"""
import asyncio
import base64
import io
import logging
import os
import re
import zipfile
from datetime import UTC, datetime, timedelta

import httpx

from app import filters
from app.submit import Entry, Submitter, core_post

log = logging.getLogger("hunter")
FEEDS = {"openphish": "https://openphish.com/feed.txt"}
# URLhaus needs a free abuse.ch Auth-Key since its public text lists were retired (410 Gone).
URLHAUS_API = "https://urlhaus-api.abuse.ch/v1/urls/recent/"
FEED_EVERY_S = 30 * 60
NRD_EVERY_S = 24 * 3600
WATCHLIST_EVERY_S = 5 * 60
NRD_URL = "https://www.whoisds.com/whois-database/newly-registered-domains/{key}/nrd"
WORD = re.compile(r"[a-z0-9]+")
USER_AGENT = "kartoshka-hunter/0.1"


def enabled(name: str) -> bool:
    wanted = os.environ.get("HUNTER_SOURCES", "ct,feeds,nrd,watchlist")
    return name in {item.strip() for item in wanted.split(",")}


def path_brand(url: str, prepared) -> str | None:
    """A UAE brand named in the path of a feed URL (kits often live on hacked sites: /tamm/pay.php)."""
    try:
        path = httpx.URL(url).path.lower()
    except Exception:
        return None
    words = set(WORD.findall(path))
    squashed = "".join(WORD.findall(path))
    for brand_id, tokens, _ in prepared:
        for token in tokens:
            if (len(token) >= 5 and token in squashed) or token in words:
                return brand_id
    return None


def feed_entries(source: str, text: str, prepared) -> list[Entry]:
    found = []
    for line in text.splitlines():
        url = line.strip()
        if not url or url.startswith("#") or not url.lower().startswith(("http://", "https://")):
            continue
        try:
            host = httpx.URL(url).host
        except Exception:
            continue
        hit = filters.name_match(filters.clean_host(host) or host, prepared)
        brand_id = hit.brand_id if hit else path_brand(url, prepared)
        if brand_id:
            found.append(Entry(source, url, brand_id, hit.kind if hit else "brand in path", deep=True))
    return found


def nrd_key(day: datetime) -> str:
    return base64.b64encode(f"{day:%Y-%m-%d}.zip".encode()).decode()


def nrd_entries(archive: bytes, prepared) -> list[Entry]:
    with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
        names = [n for n in zipped.namelist() if n.endswith(".txt")]
        text = zipped.read(names[0]).decode(errors="replace") if names else ""
    found = []
    for line in text.splitlines():
        hit = filters.name_match(filters.clean_host(line) or "", prepared) if line.strip() else None
        if hit:
            found.append(Entry("nrd", f"https://{hit.host}/", hit.brand_id, f"{hit.kind}: {hit.detail}"))
    return found


async def fetch(url: str) -> bytes:
    async with httpx.AsyncClient(timeout=60, follow_redirects=True, headers={"User-Agent": USER_AGENT}) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.content


async def poll_feeds(submitter: Submitter, prepared) -> None:
    while True:
        for source, url in FEEDS.items():
            try:
                entries = feed_entries(source, (await fetch(url)).decode(errors="replace"), prepared)
                queued = sum(submitter.add(e) for e in entries)
                log.info("feed %s: %d UAE-brand URLs, %d new", source, len(entries), queued)
            except Exception as error:
                log.warning("feed %s failed: %s", source, error)
        key = os.environ.get("URLHAUS_AUTH_KEY", "")
        if key:
            try:
                async with httpx.AsyncClient(timeout=60, headers={"User-Agent": USER_AGENT, "Auth-Key": key}) as client:
                    response = await client.get(URLHAUS_API)
                    response.raise_for_status()
                urls = "\n".join(item.get("url", "") for item in response.json().get("urls") or [])
                entries = feed_entries("urlhaus", urls, prepared)
                queued = sum(submitter.add(e) for e in entries)
                log.info("feed urlhaus: %d UAE-brand URLs, %d new", len(entries), queued)
            except Exception as error:
                log.warning("feed urlhaus failed: %s", error)
        await asyncio.sleep(FEED_EVERY_S)


async def poll_nrd(submitter: Submitter, prepared) -> None:
    while True:
        day = datetime.now(UTC) - timedelta(days=1)
        try:
            entries = nrd_entries(await fetch(NRD_URL.format(key=nrd_key(day))), prepared)
            queued = sum(submitter.add(e) for e in entries)
            log.info("nrd %s: %d look-alike names, %d new", f"{day:%Y-%m-%d}", len(entries), queued)
        except Exception as error:
            log.warning("nrd %s failed: %s", f"{day:%Y-%m-%d}", error)
        await asyncio.sleep(NRD_EVERY_S)


async def tick_watchlist() -> None:
    while True:
        await asyncio.sleep(WATCHLIST_EVERY_S)
        result = await core_post("/v1/watchlist/run")
        if result and result.get("queued"):
            log.info("watchlist: %d re-checks queued", result["queued"])
