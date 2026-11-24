"""Sends candidates to core in batches (`POST /v1/intel/feeds`), at most once per host and source a day.

CT is high volume, so its batches use `check_mode: screen`: core scores every candidate on the fast path
and sends only scores of 30 or more to the sandbox. Feed entries are known phishing and go deep.
"""
import asyncio
import logging
import os
import time
from dataclasses import dataclass

import httpx

log = logging.getLogger("hunter")
CORE_URL = os.environ.get("CORE_URL", "http://core:8000").rstrip("/")
TOKEN = os.environ.get("CORE_WRITE_TOKEN", "")
BATCH = 100
FLUSH_S = 5.0
SEEN_FOR_S = 24 * 3600
MAX_PENDING = 5000


@dataclass(frozen=True)
class Entry:
    source: str
    url: str
    brand_id: str | None
    detail: str
    deep: bool = False


class Submitter:
    def __init__(self, post=None) -> None:
        self.pending: list[Entry] = []
        self.seen: dict[tuple[str, str], float] = {}
        self.sent = 0
        self.dropped = 0
        self._post = post or self._http_post
        if post is None and not TOKEN:
            log.warning("CORE_WRITE_TOKEN is empty, submission to core will be refused")

    def fresh(self, source: str, host: str, now: float) -> bool:
        key = (source, host)
        return key not in self.seen or now - self.seen[key] >= SEEN_FOR_S

    def add(self, entry: Entry, now: float | None = None) -> bool:
        """Queue an entry unless the same host was queued from this source in the last day."""
        now = now if now is not None else time.time()
        host = httpx.URL(entry.url).host
        key = (entry.source, host)
        if key in self.seen and now - self.seen[key] < SEEN_FOR_S:
            return False
        if len(self.pending) >= MAX_PENDING:
            self.dropped += 1
            return False
        self.seen[key] = now
        if len(self.seen) > 200_000:
            cutoff = now - SEEN_FOR_S
            self.seen = {k: t for k, t in self.seen.items() if t > cutoff}
        self.pending.append(entry)
        return True

    async def flush(self) -> int:
        sent = 0
        while self.pending:
            chunk, self.pending = self.pending[:BATCH], self.pending[BATCH:]
            groups = [g for g in ([e for e in chunk if e.deep], [e for e in chunk if not e.deep]) if g]
            for index, group in enumerate(groups):
                body = {"entries": [{"source": e.source, "url": e.url, "brand_id": e.brand_id, "detail": e.detail}
                                    for e in group],
                        "check": True, "check_mode": "deep" if group[0].deep else "screen"}
                try:
                    await self._post(body)
                except Exception as error:  # core restarting: keep what was not sent for the next flush
                    unsent = [e for g in groups[index:] for e in g]
                    log.warning("submit failed (%s); %d entries kept", error, len(unsent))
                    self.pending = unsent + self.pending
                    self.sent += sent
                    return sent
                sent += len(group)
        self.sent += sent
        return sent

    async def _http_post(self, body: dict) -> dict:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(f"{CORE_URL}/v1/intel/feeds", json=body, headers={"Authorization": f"Bearer {TOKEN}"})
            response.raise_for_status()
            result = response.json()
        log.info("submitted %d (%s): new=%d checked=%d", len(body["entries"]), body["check_mode"], result["new"], len(result["checked"]))
        return result

    async def run(self) -> None:
        while True:
            await asyncio.sleep(FLUSH_S)
            await self.flush()


async def core_post(path: str) -> dict | None:
    """A token-authenticated POST with no body (the watchlist ticker)."""
    try:
        async with httpx.AsyncClient(timeout=300) as client:
            response = await client.post(f"{CORE_URL}{path}", headers={"Authorization": f"Bearer {TOKEN}"})
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as error:
        log.warning("%s failed: %s", path, error)
        return None
