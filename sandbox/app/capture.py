import os
import time
import uuid
from collections.abc import Collection
from pathlib import Path
from urllib.parse import urlsplit

from playwright.async_api import Browser, Error as PlaywrightError
from pydantic import BaseModel, Field

from app import collect
from app.guard import Guard, Unresolvable

CAPTURES_DIR = Path(os.environ.get("CAPTURES_DIR", "/captures"))
CAPTURE_TIMEOUT_MS = int(os.environ.get("CAPTURE_TIMEOUT_MS", "15000"))
SETTLE_MS = 800
MAX_TIMEOUT_MS = 45000
MAX_SETTLE_MS = 5000

SITE_ISOLATION_FLAG = "--disable-site-isolation-trials"
BLOCK_POPUPS_FLAG = "--block-new-web-contents"
BROWSER_ARGS = [SITE_ISOLATION_FLAG, BLOCK_POPUPS_FLAG]


class InvalidUrl(Exception):
    pass


class InternalHost(Exception):
    pass


class NavigationFailed(Exception):
    pass


class FileRef(BaseModel):
    path: str
    sha256: str
    bytes: int


class Favicon(FileRef):
    url: str
    content_type: str


class BotVisit(BaseModel):
    """The same URL opened as a desktop crawler. A different page here than on the phone means cloaking."""

    final_url: str | None = None
    title: str = ""
    text: str = ""
    navigation_blocked: bool = False
    error: str | None = None


class CaptureResponse(BaseModel):
    final_url: str
    title: str
    screenshot_path: str | None
    navigation_blocked: bool
    internal_requests_blocked: int
    internal_hosts_blocked: list[str]
    # Deep-path fields. Empty when the navigation was blocked.
    capture_id: str | None = None
    profile: str = "phone"
    status: int | None = None
    chain: list[str] = Field(default_factory=list)
    screenshot: FileRef | None = None
    full_screenshot: FileRef | None = None
    html: FileRef | None = None
    favicon: Favicon | None = None
    text: str = ""
    lang: str = ""
    forms: list[dict] = Field(default_factory=list)
    scripts: list[str] = Field(default_factory=list)
    links: list[str] = Field(default_factory=list)
    images: list[dict] = Field(default_factory=list)
    skeleton: str = ""
    request_hosts: list[str] = Field(default_factory=list)
    post_hosts: list[str] = Field(default_factory=list)
    tls: dict | None = None
    server_ip: str | None = None
    bot_visit: BotVisit | None = None
    load_complete: bool = True
    elapsed_ms: int = 0


def validate_url(url: str) -> None:
    try:
        parts = urlsplit(url)
        parts.port
    except ValueError as exc:
        raise InvalidUrl(f"malformed url: {exc}") from exc
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise InvalidUrl("url must be http or https with a host")


def write(path: Path, data: bytes) -> FileRef:
    path.write_bytes(data)
    return FileRef(path=str(path), sha256=collect.sha256(data), bytes=len(data))


async def bot_visit(browser: Browser, url: str, allowed_origins: Collection[str]) -> tuple[BotVisit, Guard]:
    guard = Guard(url, allowed_origins)
    context = await browser.new_context(service_workers="block", **collect.BOT)
    try:
        await guard.install(context)
        page = await context.new_page()
        await guard.attach(page)
        try:
            await page.goto(url, timeout=CAPTURE_TIMEOUT_MS, wait_until="domcontentloaded")
            await page.wait_for_load_state("load", timeout=5000)
        except PlaywrightError as exc:
            if guard.main_blocked.get(page) is None and page.url in ("", "about:blank"):
                return BotVisit(error=str(exc).splitlines()[0][:200]), guard
        blocked = guard.main_blocked.get(page)
        if blocked is not None:
            return BotVisit(final_url=blocked, navigation_blocked=True), guard
        data = await collect.read_page(page)
        return BotVisit(final_url=page.url, title=await page.title(), text=data["text"][:5000]), guard
    finally:
        await context.close()


async def capture(
    browser: Browser,
    url: str,
    allowed_origins: Collection[str] = (),
    profile: str = "phone",
    second_visit: bool = False,
    timeout_ms: int | None = None,
    settle_ms: int | None = None,
) -> CaptureResponse:
    started = time.monotonic()
    timeout_ms = min(timeout_ms or CAPTURE_TIMEOUT_MS, MAX_TIMEOUT_MS)
    settle_ms = min(SETTLE_MS if settle_ms is None else settle_ms, MAX_SETTLE_MS)
    validate_url(url)
    guard = Guard(url, allowed_origins)
    try:
        if await guard.blocks(url):
            raise InternalHost("host is internal")
    except Unresolvable as exc:
        raise NavigationFailed(f"host does not resolve: {exc}") from exc

    context = await browser.new_context(service_workers="block", **collect.PROFILES[profile])
    request_hosts: list[str] = []
    post_hosts: list[str] = []

    def on_request(request) -> None:
        host = urlsplit(request.url).hostname
        if not host:
            return
        if host not in request_hosts and len(request_hosts) < 200:
            request_hosts.append(host)
        if request.method == "POST" and host not in post_hosts:
            post_hosts.append(host)

    extra: dict = {}
    try:
        await guard.install(context)
        page = await context.new_page()
        await guard.attach(page)
        page.on("request", on_request)
        navigation_error = None
        response = None
        load_complete = True
        try:
            response = await page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
        except PlaywrightError as exc:
            navigation_error = exc
        if navigation_error is None:
            # Heavy pages keep loading trackers long after they render; capture what is there when the budget ends.
            remaining = max(1000, timeout_ms - round((time.monotonic() - started) * 1000))
            try:
                await page.wait_for_load_state("load", timeout=remaining)
            except PlaywrightError:
                load_complete = False
        blocked_url = guard.main_blocked.get(page)
        if blocked_url is None and navigation_error is not None:
            raise NavigationFailed(str(navigation_error)) from navigation_error
        if blocked_url is not None:
            final_url, title, screenshot_path = blocked_url, "", None
        else:
            await page.wait_for_timeout(settle_ms)
            final_url, title = page.url, await page.title()
            capture_id = uuid.uuid4().hex
            screenshot_path = str(CAPTURES_DIR / f"{capture_id}.png")
            await page.screenshot(path=screenshot_path)
            data = await collect.read_page(page)
            screenshot = Path(screenshot_path).read_bytes()
            extra["screenshot"] = FileRef(path=screenshot_path, sha256=collect.sha256(screenshot), bytes=len(screenshot))
            height = min(max(int(data["height"] or 0), 1), collect.FULL_PAGE_MAX_HEIGHT)
            width = collect.PROFILES[profile]["viewport"]["width"]
            try:
                full = await page.screenshot(full_page=True, clip={"x": 0, "y": 0, "width": width, "height": height})
                extra["full_screenshot"] = write(CAPTURES_DIR / f"{capture_id}.full.png", full)
            except PlaywrightError:
                pass
            try:
                html = (await page.content()).encode("utf-8", errors="replace")[: collect.HTML_LIMIT]
                extra["html"] = write(CAPTURES_DIR / f"{capture_id}.html", html)
            except PlaywrightError:
                pass
            icon = await collect.read_favicon(page, data["icons"])
            if icon:
                ref = write(CAPTURES_DIR / f"{capture_id}.ico", icon[0])
                extra["favicon"] = Favicon(**ref.model_dump(), url=icon[1], content_type=icon[2][:80])
            extra["tls"], extra["server_ip"] = await collect.connection(response)
            extra.update(
                capture_id=capture_id,
                status=response.status if response else None,
                chain=collect.redirect_chain(response),
                text=data["text"],
                lang=data["lang"],
                forms=data["forms"],
                scripts=data["scripts"],
                links=data["links"],
                images=data["images"],
                skeleton=data["skeleton"],
            )
    finally:
        await context.close()

    blocked_count, blocked_hosts = guard.blocked_count, list(guard.blocked_hosts)
    if second_visit and blocked_url is None:
        visit, bot_guard = await bot_visit(browser, url, allowed_origins)
        extra["bot_visit"] = visit
        blocked_count += bot_guard.blocked_count
        blocked_hosts += [host for host in bot_guard.blocked_hosts if host not in blocked_hosts]

    return CaptureResponse(
        final_url=final_url,
        title=title,
        screenshot_path=screenshot_path,
        navigation_blocked=blocked_url is not None,
        internal_requests_blocked=blocked_count,
        internal_hosts_blocked=blocked_hosts,
        profile=profile,
        load_complete=load_complete,
        request_hosts=request_hosts if blocked_url is None else [],
        post_hosts=post_hosts if blocked_url is None else [],
        elapsed_ms=round((time.monotonic() - started) * 1000),
        **extra,
    )
