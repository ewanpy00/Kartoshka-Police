import asyncio
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from pydantic import ValidationError

from app import capture as capture_module
from app.capture import TEXT_LIMIT, capture

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


async def test_capture_returns_text_forms_and_contact_links(browser, page_origin, tmp_path, monkeypatch):
    monkeypatch.setattr(capture_module, "CAPTURES_DIR", tmp_path)
    result = await capture(browser, page_origin + "/", allowed_origins=[page_origin])
    assert result.title == "Pay your fine"
    assert result.text.startswith("Fine payment")
    assert len(result.text) == TEXT_LIMIT
    assert [form.model_dump() for form in result.forms] == [
        {
            "action": "https://pay.example.net/charge",
            "inputs": [{"type": "text", "name": "card_number"}, {"type": "password", "name": "secret"}],
        }
    ]
    assert result.links == [
        "https://api.whatsapp.com/send?phone=971509876543",
        "https://wa.me/971501234567",
        "tel:+971501234567",
    ]


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
    assert [(item.type, item.name) for item in result.forms[0].inputs] == [("text", "action"), ("text", "elements"), ("password", "pw")]
    assert result.forms[0].action.endswith("/pay")


async def test_clobbered_document_forms_are_still_found(browser, serve, tmp_path, monkeypatch):
    body = """<img name="forms"><form><input type="password" name="pw"></form>"""
    result = await capture_html(browser, serve, tmp_path, monkeypatch, body)
    assert len(result.forms) == 1


async def test_hanging_script_does_not_hang_the_capture(browser, serve, tmp_path, monkeypatch):
    monkeypatch.setattr(capture_module, "FACTS_TIMEOUT_S", 1)
    body = """<title>stuck</title><body>hello<script>Object.defineProperty(HTMLElement.prototype, "innerText", {get() { for (;;) {} }})</script>"""
    result = await asyncio.wait_for(capture_html(browser, serve, tmp_path, monkeypatch, body), 20)
    assert (result.text, result.forms, result.links) == ("", [], [])


async def test_over_many_and_over_long_values_are_cut(browser, serve, tmp_path, monkeypatch):
    long_name = "n" * (capture_module.STRING_LIMIT + 50)
    forms = "".join(f'<form action="/f{i}"><input name="{long_name}"></form>' for i in range(capture_module.MAX_FORMS + 5))
    inputs = "<form>" + "<input name='x'>" * (capture_module.MAX_INPUTS + 5) + "</form>"
    links = "".join(f'<a href="tel:+9715012{i:05d}">x</a>' for i in range(capture_module.MAX_LINKS + 5))
    result = await capture_html(browser, serve, tmp_path, monkeypatch, forms + inputs + links)
    assert len(result.forms) == capture_module.MAX_FORMS
    assert len(result.forms[0].inputs[0].name) == capture_module.STRING_LIMIT
    assert len(result.links) == capture_module.MAX_LINKS


def test_models_cut_long_values_and_refuse_wrong_types():
    facts = capture_module.PageFacts.model_validate({"text": "t" * (TEXT_LIMIT + 1), "links": ["l" * 5000] * 200})
    assert len(facts.text) == TEXT_LIMIT
    assert len(facts.links) == capture_module.MAX_LINKS
    assert len(facts.links[0]) == capture_module.STRING_LIMIT
    with pytest.raises(ValidationError):
        capture_module.PageFacts.model_validate({"forms": [{"action": 5, "inputs": []}]})
