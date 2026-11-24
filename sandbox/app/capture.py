import asyncio
import os
import uuid
from collections.abc import Collection
from pathlib import Path
from typing import Annotated
from urllib.parse import urljoin, urlsplit

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
    available: bool = False


def keep_valid[T: BaseModel](model: type[T], items: list[dict], limit: int) -> list[T]:
    """The first `limit` items that validate; a malformed item is dropped on its own."""
    kept = []
    for item in items:
        try:
            kept.append(model.model_validate(item))
        except ValidationError:
            continue
    return kept[:limit]


def attributes(node: dict) -> dict[str, str]:
    flat = node.get("attributes", [])
    return dict(zip(flat[::2], flat[1::2]))


def parse_dom(root: dict) -> tuple[list[dict], list[str]]:
    """Forms, with inputs outside any form gathered into one form without an action, and the contact links.

    Reads the DOM the browser reports over CDP, so no script of the page runs and nothing the page defines can shadow it.
    """
    base = root.get("baseURL") or root.get("documentURL") or ""
    loose = {"action": "", "inputs": []}
    forms, links = [], []
    stack = [(root, None)]
    while stack:
        node, form = stack.pop()
        name, attrs = node.get("nodeName", ""), attributes(node)
        if name == "FORM":
            form = {"action": urljoin(base, attrs.get("action", "")) if attrs.get("action") else "", "inputs": []}
            forms.append(form)
        elif name == "INPUT":
            (form or loose)["inputs"].append({"type": attrs.get("type", "text").lower(), "name": attrs.get("name", "")})
        elif name == "A" and "href" in attrs:
            link = urljoin(base, attrs["href"])
            if link.startswith(LINK_PREFIXES):
                links.append(link)
        children = [*node.get("children", []), *node.get("shadowRoots", [])]
        if "contentDocument" in node:
            children.append(node["contentDocument"])
        stack.extend((child, form) for child in reversed(children))
    return ([loose] if loose["inputs"] else []) + forms, links


async def fetch_facts(page: Page) -> PageFacts:
    """Read text through Playwright's isolated world and the DOM over CDP; no page script is evaluated."""
    session = await page.context.new_cdp_session(page)
    text, document = await asyncio.gather(
        page.locator("body").inner_text(timeout=FACTS_TIMEOUT_S * 1000),
        session.send("DOM.getDocument", {"depth": -1, "pierce": True}),
    )
    forms, links = parse_dom(document["root"])
    return PageFacts(
        text=text,
        forms=[
            PageForm(action=form["action"], inputs=keep_valid(PageInput, form["inputs"], MAX_INPUTS))
            for form in forms[:MAX_FORMS]
        ],
        links=sorted({link[:STRING_LIMIT] for link in links})[:MAX_LINKS],
        available=True,
    )


async def read_page_facts(page: Page) -> PageFacts:
    """What the page shows. When it cannot be read in time, `available` stays false so the caller can fail closed."""
    try:
        return await asyncio.wait_for(fetch_facts(page), FACTS_TIMEOUT_S)
    except (TimeoutError, PlaywrightError, ValidationError, KeyError):
        return PageFacts()


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
    facts_available: bool
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
        final_url=final_url[:STRING_LIMIT],
        title=title[:STRING_LIMIT],
        text=facts.text,
        forms=facts.forms,
        links=facts.links,
        facts_available=facts.available,
        screenshot_path=screenshot_path,
        navigation_blocked=blocked_url is not None,
        internal_requests_blocked=guard.blocked_count,
        internal_hosts_blocked=guard.blocked_hosts,
    )
