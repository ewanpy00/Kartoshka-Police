import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

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
    assert result.forms == [
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
