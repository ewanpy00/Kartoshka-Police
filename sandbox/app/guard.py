import asyncio
import ipaddress
import logging
import re
import socket
from collections.abc import Collection
from urllib.parse import urlsplit

from playwright.async_api import BrowserContext, Error as PlaywrightError, Page, Route, WebSocketRoute

log = logging.getLogger("sandbox.guard")

INTERNAL_SUFFIXES = (".internal", ".local", ".localhost")
GUARDED_SCHEMES = ("http", "https", "ws", "wss")
DEFAULT_PORTS = {"http": 80, "https": 443}
HTTP_EQUIVALENT = {"ws": "http", "wss": "https"}


class Unresolvable(Exception):
    pass


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
    except socket.gaierror as exc:
        raise Unresolvable(host) from exc
    return any(not _is_global(address) for address in addresses)


def origin(url: str) -> tuple[str, str, int]:
    parts = urlsplit(url)
    scheme = HTTP_EQUIVALENT.get(parts.scheme, parts.scheme)
    return scheme, parts.hostname, parts.port or DEFAULT_PORTS[scheme]


class Guard:
    def __init__(self, job_url: str, allowed_origins: Collection[str] = ()):
        self.job_url = job_url
        self.allowed = {origin(allowed) for allowed in allowed_origins}
        self.blocked_count = 0
        self.blocked_hosts: list[str] = []
        self.main_blocked: dict[Page, str] = {}
        self._internal_hosts: set[str] = set()
        self._attached: dict[Page, asyncio.Future] = {}

    async def blocks(self, url: str) -> bool:
        parts = urlsplit(url)
        if parts.scheme not in GUARDED_SCHEMES or not parts.hostname:
            return False
        if origin(url) in self.allowed:
            return False
        host = parts.hostname
        if host not in self._internal_hosts:
            if not await is_internal(host):
                return False
            self._internal_hosts.add(host)
        self.blocked_count += 1
        if host not in self.blocked_hosts:
            self.blocked_hosts.append(host)
        log.warning("blocked internal request job=%s url=%s", self.job_url, url)
        return True

    async def aborts(self, url: str) -> tuple[bool, bool]:
        try:
            internal = await self.blocks(url)
        except Unresolvable:
            log.info("aborted unresolvable request job=%s url=%s", self.job_url, url)
            return True, False
        return internal, internal

    async def install(self, context: BrowserContext) -> None:
        await context.route("**/*", self._on_route)
        await context.route_web_socket(re.compile(".*"), self._on_web_socket)
        context.on("page", self.attach)

    def attach(self, page: Page) -> asyncio.Future:
        if page not in self._attached:
            self._attached[page] = asyncio.ensure_future(self._attach(page))
        return self._attached[page]

    async def _on_route(self, route: Route) -> None:
        if (await self.aborts(route.request.url))[0]:
            await route.abort("blockedbyclient")
        else:
            await route.continue_()

    async def _on_web_socket(self, ws: WebSocketRoute) -> None:
        if (await self.aborts(ws.url))[0]:
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
                abort, internal = await self.aborts(url)
            except Exception:
                log.exception("guard failed closed job=%s url=%s", self.job_url, url)
                abort, internal = True, False
            if internal and event["resourceType"] == "Document" and event["frameId"] == main_frame_id:
                self.main_blocked.setdefault(page, url)
            try:
                if not abort:
                    await session.send("Fetch.continueRequest", {"requestId": event["requestId"]})
                else:
                    await session.send(
                        "Fetch.failRequest",
                        {"requestId": event["requestId"], "errorReason": "BlockedByClient"},
                    )
            except PlaywrightError:
                # The page closed while the request was paused. Nothing is left to continue or fail, and a
                # request whose continue did not go through stays paused, so this still fails closed.
                pass

        session.on("Fetch.requestPaused", on_paused)
        await session.send("Fetch.enable", {"patterns": [{"urlPattern": "*"}]})
