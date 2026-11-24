import asyncio
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from playwright.async_api import Error as PlaywrightError

from app import capture as capture_module
from app import collect
from app.capture import capture
from app.collect import TEXT_LIMIT

PAGE = """<!doctype html>
<title>Pay your fine</title>
<body>
<h1>Fine payment</h1>
<form action="https://pay.example.net/charge" method="post">
  <input type="text" name="card_number">
  <input type="password" name="secret">
  <select name="ignored"></select>
</form>
<a href="tel:+971501234567">Call</a>
<a href="https://wa.me/971501234567">WhatsApp</a>
<a href="https://api.whatsapp.com/send?phone=971509876543">WhatsApp 2</a>
<a href="https://wa.me/971501234567">duplicate</a>
<a href="https://example.org/about">About</a>
<a href="mailto:x@example.org">Mail</a>
<p>{filler}</p>
</body>"""


@pytest.fixture
def page_origin():
    body = PAGE.format(filler="x" * (TEXT_LIMIT + 500)).encode()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


def typed(form) -> list[tuple[str, str]]:
    return [(item["type"], item["name"]) for item in form["fields"]]


async def test_capture_returns_text_forms_and_contact_links(browser, page_origin, tmp_path, monkeypatch):
    monkeypatch.setattr(capture_module, "CAPTURES_DIR", tmp_path)
    result = await capture(browser, page_origin + "/", allowed_origins=[page_origin])
    assert result.title == "Pay your fine"
    assert result.facts_available
    assert result.text.startswith("Fine payment")
    assert len(result.text) == TEXT_LIMIT
    assert len(result.forms) == 1
    assert result.forms[0]["action"] == "https://pay.example.net/charge"
    assert result.forms[0]["method"] == "post"
    assert typed(result.forms[0]) == [("text", "card_number"), ("password", "secret"), ("select-one", "ignored")]
    contact = [link for link in result.links if link.startswith(("tel:", "https://wa.me/", "https://api.whatsapp.com/"))]
    assert sorted(set(contact)) == [
        "https://api.whatsapp.com/send?phone=971509876543",
        "https://wa.me/971501234567",
        "tel:+971501234567",
    ]
    assert "https://example.org/about" in result.links


@pytest.fixture
def serve():
    servers = []

    def start(body: str) -> str:
        data = body.encode()

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        return f"http://127.0.0.1:{server.server_address[1]}"

    yield start
    for server in servers:
        server.shutdown()
        server.server_close()


async def capture_html(browser, serve, tmp_path, monkeypatch, body):
    monkeypatch.setattr(capture_module, "CAPTURES_DIR", tmp_path)
    origin = serve(body)
    return await capture(browser, origin + "/", allowed_origins=[origin])


async def test_clobbered_form_properties_do_not_hide_the_credential_form(browser, serve, tmp_path, monkeypatch):
    body = """<form action="/pay"><input name="action"><input name="elements"><input type="password" name="pw"></form>"""
    result = await capture_html(browser, serve, tmp_path, monkeypatch, body)
    assert typed(result.forms[0]) == [("text", "action"), ("text", "elements"), ("password", "pw")]
    assert result.forms[0]["action"].endswith("/pay")


async def test_clobbered_document_forms_are_still_found(browser, serve, tmp_path, monkeypatch):
    body = """<img name="forms"><form><input type="password" name="pw"></form>"""
    result = await capture_html(browser, serve, tmp_path, monkeypatch, body)
    assert len(result.forms) == 1


async def test_page_that_replaces_dom_and_array_methods_still_yields_its_forms(browser, serve, tmp_path, monkeypatch):
    body = """<title>t</title><form action="/pay"><input type="password" name="pw"></form>
<a href="tel:+971501234567">x</a>
<script>
document.querySelectorAll = () => [];
Element.prototype.getAttribute = () => null;
HTMLElement.prototype.querySelectorAll = () => [];
Object.defineProperty(HTMLElement.prototype, "innerText", {get() { return "hidden"; }});
Array.prototype.map = () => [];
Array.prototype.slice = () => [];
</script>"""
    result = await capture_html(browser, serve, tmp_path, monkeypatch, body)
    assert result.facts_available
    assert typed(result.forms[0]) == [("password", "pw")]
    assert result.forms[0]["action"].endswith("/pay")
    assert "tel:+971501234567" in result.links


async def test_input_outside_any_form_is_one_form_without_an_action(browser, serve, tmp_path, monkeypatch):
    body = """<input type="password" name="pw"><form action="/x"><input name="a"></form>"""
    result = await capture_html(browser, serve, tmp_path, monkeypatch, body)
    assert len(result.forms) == 2
    assert result.forms[0]["action"].endswith("/x")
    assert result.forms[-1]["action"] == ""  # loose inputs are appended last, as the core already expects
    assert typed(result.forms[-1]) == [("password", "pw")]


@pytest.mark.parametrize("failure", ["hang", "error"])
async def test_unreadable_page_facts_fail_closed(browser, serve, tmp_path, monkeypatch, failure):
    async def unreadable(page):
        if failure == "hang":
            await asyncio.sleep(60)
        raise PlaywrightError("page crashed")

    monkeypatch.setattr(collect, "fetch_page", unreadable)
    monkeypatch.setattr(collect, "FACTS_TIMEOUT_S", 1)
    result = await asyncio.wait_for(capture_html(browser, serve, tmp_path, monkeypatch, "<title>x</title>hello"), 20)
    assert result.facts_available is False
    assert (result.text, result.forms, result.links, result.scripts, result.images, result.skeleton) == ("", [], [], [], [], "")
    assert result.title == "x"
    assert result.screenshot_path


async def test_over_many_and_over_long_values_are_cut(browser, serve, tmp_path, monkeypatch):
    long_name = "n" * 500
    forms = "".join(f'<form action="/f{i}"><input name="{long_name}"></form>' for i in range(collect.MAX_FORMS + 5))
    inputs = "<form>" + "<input name='x'>" * (collect.MAX_FIELDS + 5) + "</form>"
    links = "".join(f'<a href="tel:+9715012{i:05d}">x</a>' for i in range(collect.MAX_LINKS + 5))
    scripts = "".join(f'<script src="/s{i}.js"></script>' for i in range(collect.MAX_SCRIPTS + 5))
    images = "".join(f'<img src="/i{i}.png" alt="{"a" * 500}">' for i in range(collect.MAX_IMAGES + 5))
    result = await capture_html(browser, serve, tmp_path, monkeypatch, forms + inputs + links + scripts + images)
    assert result.facts_available
    assert len(result.forms) == collect.MAX_FORMS
    assert len(result.forms[0]["fields"][0]["name"]) == 80
    assert len(result.links) == collect.MAX_LINKS
    assert len(result.scripts) == collect.MAX_SCRIPTS
    assert len(result.images) == collect.MAX_IMAGES
    assert len(result.images[0]["alt"]) == 120


async def test_title_and_final_url_are_cut_to_the_string_limit(browser, serve, tmp_path, monkeypatch):
    limit = capture_module.STRING_LIMIT
    origin = serve(f"<title>{'t' * (limit * 3)}</title>hello")
    monkeypatch.setattr(capture_module, "CAPTURES_DIR", tmp_path)
    result = await capture(browser, f"{origin}/?{'q' * (limit * 2)}", allowed_origins=[origin])
    assert len(result.title) == limit
    assert len(result.final_url) == limit


@pytest.mark.parametrize(
    "body",
    ["<div>" * 5000 + "deep", "<p>x</p>" * 100000 + '<form><input type="password" name="pw"></form>'],
    ids=["5000-nested", "100000-nodes"],
)
async def test_hostile_dom_size_never_fails_the_capture(browser, serve, tmp_path, monkeypatch, body):
    result = await capture_html(browser, serve, tmp_path, monkeypatch, "<title>big</title>" + body)
    assert result.title == "big"
    assert result.screenshot_path
    assert result.facts_available is False or result.forms == [] or result.forms[0]["fields"][0]["type"] == "password"


def test_dom_over_the_node_budget_is_refused():
    node = {"nodeName": "DIV", "children": [{"nodeName": "P"}] * collect.MAX_DOM_NODES}
    with pytest.raises(collect.DomTooLarge):
        collect.parse_dom(node)


async def test_dom_above_the_node_bound_fails_closed(browser, serve, tmp_path, monkeypatch):
    monkeypatch.setattr(collect, "MAX_DOM_NODES", 200)
    body = "<title>big</title>" + "<p>x</p>" * 500 + '<form><input type="password" name="pw"></form>'
    result = await capture_html(browser, serve, tmp_path, monkeypatch, body)
    assert result.facts_available is False
    assert (result.text, result.forms, result.links, result.skeleton) == ("", [], [], "")
    assert result.screenshot_path


async def test_page_whose_script_never_returns_is_neither_a_hang_nor_clean_facts(browser, serve, tmp_path, monkeypatch):
    monkeypatch.setattr(collect, "FACTS_TIMEOUT_S", 2)
    monkeypatch.setattr(capture_module, "PAGE_CALL_TIMEOUT_S", 3)
    monkeypatch.setattr(collect, "FAVICON_TIMEOUT_S", 2)
    body = """<title>busy</title><form action="/pay"><input type="password" name="pw"></form>
<script>setTimeout(() => { while (true) {} }, 300);</script>"""
    result = await asyncio.wait_for(capture_html(browser, serve, tmp_path, monkeypatch, body), 90)
    assert result.facts_available is False
    assert (result.text, result.forms, result.links, result.skeleton) == ("", [], [], "")


async def test_overridden_builtins_and_clobbered_names_cannot_change_the_fields(browser, serve, tmp_path, monkeypatch):
    body = """<title>t</title><form action="/pay" method="POST" id="f">
<label for="card">Card number</label><input id="card" name="card" inputmode="numeric" maxlength="19" autocomplete="cc-number">
<input name="action"><input name="elements"><input name="querySelectorAll"><img name="querySelectorAll">
</form>
<script>
const nothing = () => [];
document.querySelectorAll = nothing; Document.prototype.querySelectorAll = nothing; Element.prototype.querySelectorAll = nothing;
Element.prototype.getAttribute = () => "x"; Array.prototype.map = nothing; Array.prototype.filter = nothing;
Array.from = nothing; JSON.stringify = () => "[]"; JSON.parse = () => ({});
</script>"""
    result = await capture_html(browser, serve, tmp_path, monkeypatch, body)
    assert result.facts_available
    form = result.forms[0]
    assert (form["method"], form["action"].endswith("/pay")) == ("post", True)
    assert typed(form)[0] == ("text", "card")
    assert [item["name"] for item in form["fields"]][1:] == ["action", "elements", "querySelectorAll"]
    assert form["fields"][0]["label"] == "Card number"
    assert form["fields"][0]["maxlength"] == 19 and form["fields"][0]["autocomplete"] == "cc-number"


async def test_favicon_answer_from_the_page_is_bounded_and_time_limited(browser, serve, tmp_path, monkeypatch):
    origin = serve("<title>t</title>x")
    context = await browser.new_context()
    page = await context.new_page()
    await page.goto(origin + "/")
    try:
        monkeypatch.setattr(collect, "FAVICON_TIMEOUT_S", 1)
        await page.evaluate("() => { window.fetch = () => new Promise(() => {}); }")
        assert await asyncio.wait_for(collect.read_favicon(page, []), 15) is None
        await page.evaluate("() => { window.fetch = async () => ({ok: true, url: 'x', headers: {get: () => 't'}, arrayBuffer: async () => new ArrayBuffer(10)}); }")
        got = await collect.read_favicon(page, [])
        assert got is None or len(got[0]) <= collect.FAVICON_LIMIT
    finally:
        await context.close()
