import asyncio
import ipaddress
import logging
import re
import socket
from urllib.parse import urlsplit

from playwright.async_api import BrowserContext, Page, WebSocketRoute

log = logging.getLogger("sandbox.guard")

INTERNAL_SUFFIXES = (".internal", ".local", ".localhost")
GUARDED_SCHEMES = ("http", "https", "ws", "wss")
DEFAULT_PORTS = {"http": 80, "https": 443}
HTTP_EQUIVALENT = {"ws": "http", "wss": "https"}


def _resolve(host: str) -> list[str]:
    return [info[4][0] for info in socket.getaddrinfo(host, None)]


def _is_global(address: str) -> bool:
    ip = ipaddress.ip_address(address.split("%")[0])
    if ip.version == 6 and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_global


async def is_internal(host: str) -> bool:
    host = host.lower().rstrip(".")
    try:
        return not _is_global(host)
    except ValueError:
        pass
    if "." not in host or host.endswith(INTERNAL_SUFFIXES):
        return True
    try:
        addresses = await asyncio.to_thread(_resolve, host)
    except socket.gaierror:
        return False
    return any(not _is_global(address) for address in addresses)


def origin(url: str) -> tuple[str, str, int]:
    parts = urlsplit(url)
    scheme = HTTP_EQUIVALENT.get(parts.scheme, parts.scheme)
    return scheme, parts.hostname, parts.port or DEFAULT_PORTS[scheme]


class Guard:
    def __init__(self, job_url: str, allowed_origin: str | None = None):
        self.job_url = job_url
        self.allowed = origin(allowed_origin) if allowed_origin else None
        self.blocked_count = 0
        self.blocked_hosts: list[str] = []
        self.main_blocked: dict[Page, str] = {}
        self._verdicts: dict[str, bool] = {}
        self._attached: dict[Page, asyncio.Future] = {}

    async def blocks(self, url: str) -> bool:
        parts = urlsplit(url)
        if parts.scheme not in GUARDED_SCHEMES or not parts.hostname:
            return False
        if origin(url) == self.allowed:
            return False
        host = parts.hostname
        if host not in self._verdicts:
            self._verdicts[host] = await is_internal(host)
        if not self._verdicts[host]:
            return False
        self.blocked_count += 1
        if host not in self.blocked_hosts:
            self.blocked_hosts.append(host)
        log.warning("blocked internal request job=%s url=%s", self.job_url, url)
        return True

    async def install(self, context: BrowserContext) -> None:
        await context.route_web_socket(re.compile(".*"), self._on_web_socket)
        context.on("page", self.attach)

    def attach(self, page: Page) -> asyncio.Future:
        if page not in self._attached:
            self._attached[page] = asyncio.ensure_future(self._attach(page))
        return self._attached[page]

    async def _on_web_socket(self, ws: WebSocketRoute) -> None:
        if await self.blocks(ws.url):
            await ws.close()
        else:
            ws.connect_to_server()

    async def _attach(self, page: Page) -> None:
        session = await page.context.new_cdp_session(page)
        tree = await session.send("Page.getFrameTree")
        main_frame_id = tree["frameTree"]["frame"]["id"]

        async def on_paused(event: dict) -> None:
            url = event["request"]["url"]
            try:
                blocked = await self.blocks(url)
            except Exception:
                log.exception("guard failed closed job=%s url=%s", self.job_url, url)
                blocked = True
            if not blocked:
                await session.send("Fetch.continueRequest", {"requestId": event["requestId"]})
                return
            if event["resourceType"] == "Document" and event["frameId"] == main_frame_id:
                self.main_blocked.setdefault(page, url)
            await session.send(
                "Fetch.failRequest",
                {"requestId": event["requestId"], "errorReason": "BlockedByClient"},
            )

        session.on("Fetch.requestPaused", on_paused)
        await session.send("Fetch.enable", {"patterns": [{"urlPattern": "*"}]})
