import asyncio
import os
import uuid
from collections.abc import Collection
from pathlib import Path
from typing import Annotated
from urllib.parse import urlsplit

from playwright.async_api import Browser, Error as PlaywrightError, Page
from pydantic import BaseModel, BeforeValidator, Strict, ValidationError

from app.guard import Guard, Unresolvable

CAPTURES_DIR = Path(os.environ.get("CAPTURES_DIR", "/captures"))
CAPTURE_TIMEOUT_MS = int(os.environ.get("CAPTURE_TIMEOUT_MS", "15000"))


SITE_ISOLATION_FLAG = "--disable-site-isolation-trials"
BLOCK_POPUPS_FLAG = "--block-new-web-contents"
BROWSER_ARGS = [SITE_ISOLATION_FLAG, BLOCK_POPUPS_FLAG]


TEXT_LIMIT = 20000
STRING_LIMIT = 2000
MAX_FORMS = 20
MAX_INPUTS = 50
MAX_LINKS = 100
FACTS_TIMEOUT_S = 5
LINK_PREFIXES = ("tel:", "https://wa.me/", "https://api.whatsapp.com/")

# The page controls document.forms, form.action and form.elements, so the script only uses calls it cannot shadow.
PAGE_FACTS_SCRIPT = """([limits, prefixes]) => {
  const cut = (value, limit) => String(value ?? "").slice(0, limit);
  const absolute = value => { try { return new URL(value, location.href).href; } catch { return ""; } };
  const forms = [...document.querySelectorAll("form")].slice(0, limits.forms).map(form => ({
    action: cut(absolute(form.getAttribute("action") || ""), limits.string),
    inputs: [...form.querySelectorAll("input")].slice(0, limits.inputs).map(input => ({
      type: cut(input.getAttribute("type") || "text", limits.string),
      name: cut(input.getAttribute("name"), limits.string),
    })),
  }));
  const links = [...document.querySelectorAll("a[href]")]
    .map(a => absolute(a.getAttribute("href")))
    .filter(href => prefixes.some(prefix => href.startsWith(prefix)))
    .slice(0, limits.links)
    .map(href => cut(href, limits.string));
  return {text: cut(document.querySelector("body")?.innerText, limits.text), forms, links};
}"""


def cut_string(limit: int):
    return BeforeValidator(lambda value: value[:limit] if isinstance(value, str) else value)


def cut_list(limit: int):
    return BeforeValidator(lambda value: value[:limit] if isinstance(value, list) else value)


Text = Annotated[str, Strict(), cut_string(STRING_LIMIT)]


class PageInput(BaseModel):
    type: Text
    name: Text


class PageForm(BaseModel):
    action: Text
    inputs: Annotated[list[PageInput], cut_list(MAX_INPUTS)]


class PageFacts(BaseModel):
    text: Annotated[str, Strict(), cut_string(TEXT_LIMIT)] = ""
    forms: Annotated[list[PageForm], cut_list(MAX_FORMS)] = []
    links: Annotated[list[Text], cut_list(MAX_LINKS)] = []


async def read_page_facts(page: Page) -> PageFacts:
    """What the page shows. A page that hangs, throws or returns malformed data yields empty facts."""
    limits = {"text": TEXT_LIMIT, "string": STRING_LIMIT, "forms": MAX_FORMS, "inputs": MAX_INPUTS, "links": MAX_LINKS}
    try:
        raw = await asyncio.wait_for(page.evaluate(PAGE_FACTS_SCRIPT, [limits, list(LINK_PREFIXES)]), FACTS_TIMEOUT_S)
        facts = PageFacts.model_validate(raw)
    except (TimeoutError, PlaywrightError, ValidationError):
        return PageFacts()
    return facts.model_copy(update={"links": sorted({link for link in facts.links if link.startswith(LINK_PREFIXES)})})


class InvalidUrl(Exception):
    pass


class InternalHost(Exception):
    pass


class NavigationFailed(Exception):
    pass


class CaptureResponse(BaseModel):
    final_url: str
    title: str
    text: str
    forms: list[PageForm]
    links: list[str]
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
            facts = PageFacts()
        else:
            final_url, title = page.url, await page.title()
            screenshot_path = str(CAPTURES_DIR / f"{uuid.uuid4().hex}.png")
            await page.screenshot(path=screenshot_path)
            facts = await read_page_facts(page)
    finally:
        await context.close()

    return CaptureResponse(
        final_url=final_url,
        title=title,
        text=facts.text,
        forms=facts.forms,
        links=facts.links,
        screenshot_path=screenshot_path,
        navigation_blocked=blocked_url is not None,
        internal_requests_blocked=guard.blocked_count,
        internal_hosts_blocked=guard.blocked_hosts,
    )
