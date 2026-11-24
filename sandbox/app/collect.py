"""What the deep path reads from a loaded page. Everything runs inside the page, so every fetch it makes
(the favicon) goes through the guard like any other page request."""
import base64
import hashlib

from playwright.async_api import Error as PlaywrightError, Page, Response

TEXT_LIMIT = 20000
HTML_LIMIT = 2_000_000
FAVICON_LIMIT = 100_000
FULL_PAGE_MAX_HEIGHT = 6000

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

PAGE_SCRIPT = """() => {
  const clip = (value, n) => (value || "").toString().slice(0, n);
  const labelOf = el => {
    let text = "";
    if (el.id) {
      const label = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
      if (label) text = label.innerText;
    }
    if (!text && el.closest("label")) text = el.closest("label").innerText;
    return clip(text || el.getAttribute("aria-label") || "", 120);
  };
  const field = el => ({
    tag: el.tagName.toLowerCase(),
    type: clip(el.type, 20),
    name: clip(el.name, 80),
    id: clip(el.id, 80),
    placeholder: clip(el.placeholder, 120),
    autocomplete: clip(el.autocomplete, 40),
    inputmode: clip(el.inputMode, 20),
    maxlength: el.maxLength > 0 ? el.maxLength : null,
    label: labelOf(el),
  });
  const forms = [...document.querySelectorAll("form")].slice(0, 20).map(form => ({
    action: clip(form.action, 500),
    method: clip(form.method, 10).toLowerCase(),
    fields: [...form.querySelectorAll("input, select, textarea")].slice(0, 50).map(field),
  }));
  const loose = [...document.querySelectorAll("input, select, textarea")].filter(el => !el.form).slice(0, 50);
  if (loose.length) forms.push({action: "", method: "", fields: loose.map(field)});

  const skeleton = [];
  const walk = (node, depth) => {
    if (skeleton.length >= 3000 || depth > 40) return;
    const tag = node.tagName.toLowerCase();
    skeleton.push(tag === "input" ? `input:${(node.type || "text").toLowerCase()}` : tag);
    for (const child of node.children) walk(child, depth + 1);
  };
  if (document.documentElement) walk(document.documentElement, 0);

  return {
    text: clip(document.body ? document.body.innerText : "", %(text_limit)d),
    lang: clip(document.documentElement.lang, 20),
    forms,
    scripts: [...document.scripts].map(s => s.src).filter(Boolean).slice(0, 100),
    links: [...document.querySelectorAll("a[href]")].map(a => clip(a.href, 500)).slice(0, 500),
    icons: [...document.querySelectorAll('link[rel~="icon" i], link[rel="apple-touch-icon" i]')].map(l => l.href).slice(0, 5),
    images: [...document.images].slice(0, 50).map(img => ({alt: clip(img.alt, 120), src: clip(img.currentSrc || img.src, 300)})),
    skeleton: skeleton.join(" "),
    height: Math.max(document.documentElement.scrollHeight || 0, document.body ? document.body.scrollHeight : 0),
  };
}""" % {"text_limit": TEXT_LIMIT}

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

EMPTY_PAGE = {"text": "", "lang": "", "forms": [], "scripts": [], "links": [], "icons": [], "images": [], "skeleton": "", "height": 0}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


async def read_page(page: Page) -> dict:
    try:
        return await page.evaluate(PAGE_SCRIPT)
    except PlaywrightError:
        return dict(EMPTY_PAGE)


async def read_favicon(page: Page, icons: list[str]) -> tuple[bytes, str, str] | None:
    """(bytes, url, content type) of the page icon, fetched by the page itself."""
    candidates = icons[:1] or [await page.evaluate("() => new URL('/favicon.ico', location.href).href")]
    try:
        found = await page.evaluate(FAVICON_SCRIPT, [candidates[0], FAVICON_LIMIT])
    except PlaywrightError:
        return None
    if not found:
        return None
    return base64.b64decode(found["data"]), found["url"], found["type"]


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
