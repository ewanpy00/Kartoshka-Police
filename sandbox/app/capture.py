import os
import uuid
from collections.abc import Collection
from pathlib import Path
from urllib.parse import urlsplit

from playwright.async_api import Browser, Error as PlaywrightError
from pydantic import BaseModel

from app.guard import Guard, Unresolvable

CAPTURES_DIR = Path(os.environ.get("CAPTURES_DIR", "/captures"))
CAPTURE_TIMEOUT_MS = int(os.environ.get("CAPTURE_TIMEOUT_MS", "15000"))


BROWSER_ARGS = ["--disable-site-isolation-trials"]


class InvalidUrl(Exception):
    pass


class InternalHost(Exception):
    pass


class NavigationFailed(Exception):
    pass


class CaptureResponse(BaseModel):
    final_url: str
    title: str
    screenshot_path: str | None
    navigation_blocked: bool
    internal_requests_blocked: int
    internal_hosts_blocked: list[str]


def validate_url(url: str) -> None:
    try:
        parts = urlsplit(url)
        parts.port
    except ValueError as exc:
        raise InvalidUrl(f"malformed url: {exc}") from exc
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise InvalidUrl("url must be http or https with a host")


async def capture(browser: Browser, url: str, allowed_origins: Collection[str] = ()) -> CaptureResponse:
    validate_url(url)
    guard = Guard(url, allowed_origins)
    try:
        if await guard.blocks(url):
            raise InternalHost("host is internal")
    except Unresolvable as exc:
        raise NavigationFailed(f"host does not resolve: {exc}") from exc

    context = await browser.new_context(service_workers="block")
    try:
        await guard.install(context)
        page = await context.new_page()
        await guard.attach(page)
        navigation_error = None
        try:
            await page.goto(url, timeout=CAPTURE_TIMEOUT_MS, wait_until="load")
        except PlaywrightError as exc:
            navigation_error = exc
        blocked_url = guard.main_blocked.get(page)
        if blocked_url is None and navigation_error is not None:
            raise NavigationFailed(str(navigation_error)) from navigation_error
        if blocked_url is not None:
            final_url, title, screenshot_path = blocked_url, "", None
        else:
            final_url, title = page.url, await page.title()
            screenshot_path = str(CAPTURES_DIR / f"{uuid.uuid4().hex}.png")
            await page.screenshot(path=screenshot_path)
    finally:
        await context.close()

    return CaptureResponse(
        final_url=final_url,
        title=title,
        screenshot_path=screenshot_path,
        navigation_blocked=blocked_url is not None,
        internal_requests_blocked=guard.blocked_count,
        internal_hosts_blocked=guard.blocked_hosts,
    )
