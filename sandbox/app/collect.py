"""What the deep path reads from a loaded page. The facts come from the DOM over CDP, outside the page's script
world; only the favicon fetch runs inside the page, so the guard covers it like any other page request."""
import asyncio
import base64
import hashlib
from urllib.parse import urljoin, urlsplit

from playwright.async_api import Error as PlaywrightError, Page, Response

TEXT_LIMIT = 20000
HTML_LIMIT = 2_000_000
FAVICON_LIMIT = 100_000
FULL_PAGE_MAX_HEIGHT = 6000
FACTS_TIMEOUT_S = 5
FAVICON_TIMEOUT_S = 5
MAX_DOM_NODES = 50000
MAX_FORMS = 20
MAX_FIELDS = 50
MAX_LINKS = 500
MAX_SCRIPTS = 100
MAX_ICONS = 5
MAX_IMAGES = 50
MAX_SKELETON = 3000
INPUT_TYPES = frozenset(
    "button checkbox color date datetime-local email file hidden image month number password radio range reset "
    "search submit tel text time url week".split()
)


class DomTooLarge(Exception):
    pass

PHONE = {
    "user_agent": (
        "Mozilla/5.0 (Linux; Android 14; SM-S921B) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Mobile Safari/537.36"
    ),
    "viewport": {"width": 412, "height": 915},
    "device_scale_factor": 1,
    "is_mobile": True,
    "has_touch": True,
    "locale": "ar-AE",
    "timezone_id": "Asia/Dubai",
    "extra_http_headers": {"Accept-Language": "ar-AE,ar;q=0.9,en;q=0.8"},
}
BOT = {
    "user_agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/140.0.0.0 Safari/537.36",
    "viewport": {"width": 1280, "height": 800},
    "locale": "en-US",
    "timezone_id": "UTC",
}
PROFILES = {"phone": PHONE, "bot": BOT}

FAVICON_SCRIPT = """async ([url, limit]) => {
  const timeout = new Promise(done => setTimeout(() => done(null), 3000));
  const fetchIcon = (async () => {
    try {
      const response = await fetch(url, {credentials: "omit"});
      if (!response.ok) return null;
      const bytes = new Uint8Array(await response.arrayBuffer());
      if (bytes.length === 0 || bytes.length > limit) return null;
      let binary = "";
      for (const byte of bytes) binary += String.fromCharCode(byte);
      return {url: response.url, type: response.headers.get("content-type") || "", data: btoa(binary)};
    } catch (error) {
      return null;
    }
  })();
  return Promise.race([fetchIcon, timeout]);
}"""

EMPTY_PAGE = {
    "text": "", "lang": "", "forms": [], "scripts": [], "links": [], "icons": [], "images": [],
    "skeleton": "", "height": 0, "facts_available": False,
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def clip(value, limit: int) -> str:
    return value[:limit] if isinstance(value, str) else ""


def attributes(node: dict) -> dict[str, str]:
    flat = node.get("attributes", [])
    return dict(zip(flat[::2], flat[1::2]))


def label_text(node: dict) -> str:
    """Text of a label's subtree, read from the DOM tree and cut early; a bounded walk, not innerText."""
    parts, size, budget = [], 0, 200
    stack = [node]
    while stack and size < 120 and budget > 0:
        budget -= 1
        current = stack.pop()
        if current.get("nodeType") == 3:
            parts.append(current.get("nodeValue", ""))
            size += len(parts[-1])
        elif current.get("nodeName", "").upper() not in ("SCRIPT", "STYLE"):
            stack.extend(reversed(current.get("children", [])))
    return " ".join("".join(parts).split())


def field_of(node: dict, attrs: dict, label_node: dict | None) -> dict:
    tag = node["nodeName"].lower()
    if tag == "input":
        kind = attrs.get("type", "").strip().lower()
        kind = kind if kind in INPUT_TYPES else "text"
    elif tag == "select":
        kind = "select-multiple" if "multiple" in attrs else "select-one"
    else:
        kind = "textarea"
    return {
        "tag": tag,
        "type": kind,
        "name": clip(attrs.get("name", ""), 80),
        "id": clip(attrs.get("id", ""), 80),
        "placeholder": clip(attrs.get("placeholder", ""), 120) if tag != "select" else "",
        "autocomplete": clip(attrs.get("autocomplete", ""), 40),
        "inputmode": clip(attrs.get("inputmode", "").strip().lower(), 20) if tag != "select" else "",
        "maxlength": maxlength(attrs.get("maxlength")) if tag != "select" else None,
        "label": "",
        "_label_node": label_node,
        "_label_for": attrs.get("id", ""),
        "_aria": attrs.get("aria-label", ""),
    }


def maxlength(raw: str | None) -> int | None:
    try:
        value = int((raw or "").strip())
    except ValueError:
        return None
    return value if 0 < value < 2**31 else None


def finish_field(field: dict, labels_for: dict) -> dict:
    node = labels_for.get(field["_label_for"]) if field["_label_for"] else None
    text = label_text(node) if node else ""
    if not text and field["_label_node"] is not None:
        text = label_text(field["_label_node"])
    field = {key: value for key, value in field.items() if not key.startswith("_")} | {
        "label": clip(text or field_aria(field), 120)
    }
    return field


def field_aria(field: dict) -> str:
    return field.get("_aria", "")


def parse_dom(root: dict) -> dict:
    """Page facts from the DOM the browser reports over CDP.

    No script of the page runs and nothing the page defines can shadow this code. Every list is capped while the
    tree is walked, and a document of more than MAX_DOM_NODES nodes raises DomTooLarge.
    """
    html_lang = ""
    forms: list[dict] = []
    by_id: dict[str, dict] = {}
    loose: list[dict] = []
    pending: list[tuple[dict, dict | None, str | None]] = []  # (field, form, form attribute)
    labels_for: dict[str, dict] = {}
    scripts, links, icons, images, skeleton = [], [], [], [], []
    stack = [(root, None, None, root.get("baseURL") or root.get("documentURL") or "", -1, True)]
    visited = 0
    while stack:
        visited += 1
        if visited > MAX_DOM_NODES:
            raise DomTooLarge
        node, form, label, base, depth, in_main = stack.pop()
        if node.get("nodeType") == 1:
            name, attrs = node.get("nodeName", "").upper(), attributes(node)
            if in_main and depth <= 40 and len(skeleton) < MAX_SKELETON:
                tag = name.lower()
                skeleton.append(f"input:{field_type(attrs)}" if tag == "input" else tag)
            if in_main and depth == 0 and name == "HTML":
                html_lang = clip(attrs.get("lang", ""), 20)
            if name == "FORM":
                action = urljoin(base, attrs["action"].strip()) if attrs.get("action", "").strip() else base
                method = attrs.get("method", "").strip().lower()
                form = {"action": clip(action, 500), "method": method if method in ("post", "dialog") else "get", "fields": []}
                forms.append(form)
                if attrs.get("id") and attrs["id"] not in by_id:
                    by_id[attrs["id"]] = form
            elif name == "LABEL":
                label = node
                if attrs.get("for") and attrs["for"] not in labels_for:
                    labels_for[attrs["for"]] = node
            elif name in ("INPUT", "SELECT", "TEXTAREA"):
                field = field_of(node, attrs, label)
                if attrs.get("form"):
                    pending.append((field, None, attrs["form"]))
                elif form is not None:
                    form["fields"].append(field) if len(form["fields"]) < MAX_FIELDS else None
                else:
                    loose.append(field) if len(loose) < MAX_FIELDS else None
            elif name == "A" and attrs.get("href") is not None and len(links) < MAX_LINKS:
                links.append(clip(urljoin(base, attrs["href"]), 500))
            elif name == "SCRIPT" and attrs.get("src") and len(scripts) < MAX_SCRIPTS:
                scripts.append(urljoin(base, attrs["src"]))
            elif name == "LINK" and len(icons) < MAX_ICONS and attrs.get("href") is not None:
                rel = attrs.get("rel", "").lower().split()
                if "icon" in rel or attrs.get("rel", "").lower() == "apple-touch-icon":
                    icons.append(urljoin(base, attrs["href"]))
            elif name == "IMG" and len(images) < MAX_IMAGES:
                source = attrs.get("src") or (attrs.get("srcset", "").split(",")[0].split() or [""])[0]
                images.append({"alt": clip(attrs.get("alt", ""), 120), "src": clip(urljoin(base, source) if source else "", 300)})
        content = [node["contentDocument"]] if "contentDocument" in node else []
        # Popped last-in first-out: children come out first and in document order, then shadow roots, then frames.
        for group, main in ((content, False), (node.get("shadowRoots", []), False), (node.get("children", []), in_main)):
            for child in reversed(group):
                child_base = child.get("baseURL") or base if child.get("nodeType") == 9 else base
                stack.append((child, form, label, child_base, depth + 1, main))
    for field, _, form_id in pending:
        target = by_id.get(form_id)
        bucket = target["fields"] if target else loose
        if len(bucket) < MAX_FIELDS:
            bucket.append(field)
    for form in forms:
        form["fields"] = [finish_field(field, labels_for) for field in form["fields"]]
    result_forms = forms[:MAX_FORMS]
    if loose:
        result_forms.append({"action": "", "method": "", "fields": [finish_field(field, labels_for) for field in loose]})
    return {
        "lang": html_lang, "forms": result_forms, "scripts": scripts, "links": links, "icons": icons, "images": images,
        "skeleton": " ".join(skeleton),
    }


def field_type(attrs: dict) -> str:
    kind = attrs.get("type", "").strip().lower()
    return kind if kind in INPUT_TYPES else "text"


async def fetch_page(page: Page) -> dict:
    """Text through Playwright's own world and the DOM over CDP; no script of the page is evaluated."""
    session = await page.context.new_cdp_session(page)
    try:
        # The size is checked before the tree or the text is requested: a huge document must be refused before
        # Chromium serialises it and Python parses it. Nodes counts the page's live DOM (text nodes and detached
        # ones included, and possibly other pages in the same renderer process), so it can over-count, which only
        # makes the refusal come sooner. No count means no fetch.
        await session.send("Performance.enable")
        counts = {item.get("name"): item.get("value") for item in (await session.send("Performance.getMetrics")).get("metrics", [])}
        nodes = counts.get("Nodes")
        if not isinstance(nodes, (int, float)):
            raise ValueError("node count unavailable")
        if nodes > MAX_DOM_NODES:
            raise DomTooLarge
        text, document, metrics = await asyncio.gather(
            page.locator("body").inner_text(timeout=FACTS_TIMEOUT_S * 1000),
            session.send("DOM.getDocument", {"depth": -1, "pierce": True}),
            session.send("Page.getLayoutMetrics"),
            return_exceptions=True,
        )
        for part in (text, document, metrics):
            if isinstance(part, BaseException):
                raise part
        facts = parse_dom(document["root"])
        size = metrics.get("cssContentSize") or metrics.get("contentSize") or {}
        height = size.get("height", 0)
        facts["height"] = int(height) if isinstance(height, (int, float)) and 0 <= height < 10**7 else 0
        facts["text"] = clip(text, TEXT_LIMIT)
        facts["facts_available"] = True
        return facts
    finally:
        try:
            await asyncio.wait_for(session.detach(), 1)
        except Exception:
            pass


async def read_page(page: Page) -> dict:
    """The facts of the page. When they cannot be read in time, `facts_available` is false and every fact is empty."""
    try:
        return await asyncio.wait_for(fetch_page(page), FACTS_TIMEOUT_S)
    except Exception:
        return dict(EMPTY_PAGE)


async def read_favicon(page: Page, icons: list[str]) -> tuple[bytes, str, str] | None:
    """(bytes, url, content type) of the page icon, fetched by the page itself so the request guard covers it.

    The script runs in the page's world, so it can be overridden and its answer is untrusted: it is time-limited,
    and the answer is type-checked and size-bounded before use.
    """
    candidate = icons[0] if icons else urljoin(page.url, "/favicon.ico")
    if urlsplit(candidate).scheme not in ("http", "https"):
        return None
    try:
        found = await asyncio.wait_for(page.evaluate(FAVICON_SCRIPT, [candidate, FAVICON_LIMIT]), FAVICON_TIMEOUT_S)
        if not isinstance(found, dict) or not all(isinstance(found.get(key), str) for key in ("data", "url", "type")):
            return None
        if len(found["data"]) > FAVICON_LIMIT * 4 // 3 + 8:
            return None
        data = base64.b64decode(found["data"], validate=True)
    except (PlaywrightError, asyncio.TimeoutError, ValueError):
        return None
    if not data or len(data) > FAVICON_LIMIT:
        return None
    return data, found["url"][:2000], found["type"][:80]


def redirect_chain(response: Response | None) -> list[str]:
    chain = []
    request = response.request if response else None
    while request is not None:
        chain.append(request.url)
        request = request.redirected_from
    return list(reversed(chain))


async def connection(response: Response | None) -> tuple[dict | None, str | None]:
    """TLS certificate details and the server IP of the main document."""
    if response is None:
        return None, None
    tls, server_ip = None, None
    try:
        details = await response.security_details()
        if details:
            tls = {key: details.get(key) for key in ("issuer", "subjectName", "protocol", "validFrom", "validTo")}
    except PlaywrightError:
        pass
    try:
        address = await response.server_addr()
        if address:
            server_ip = address.get("ipAddress")
    except PlaywrightError:
        pass
    return tls, server_ip
