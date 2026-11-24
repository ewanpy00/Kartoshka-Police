"""The deep-path fields of a capture: forms, links, favicon, artifacts and the cloaking visit."""
import hashlib
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from app.capture import capture

ICON = b"\x89PNG\r\n\x1a\nfake-icon-bytes"
PHONE_PAGE = """<!doctype html>
<html lang="ar"><head><title>Pay your fine</title><link rel="icon" href="/icon.png"></head>
<body>
<h1>Traffic fine: pay within 24 hours</h1>
<form action="http://127.0.0.1:{port}/collect" method="post">
  <label for="card">Card number</label><input id="card" name="cardnumber" inputmode="numeric" maxlength="19">
  <input name="cvv" placeholder="CVV" maxlength="3">
  <input name="otp" placeholder="رمز التحقق" autocomplete="one-time-code">
  <button>Pay</button>
</form>
<a href="tel:+971501234567">Call us</a>
<a href="https://wa.me/971501234567">WhatsApp</a>
<script src="/kit.js"></script>
</body></html>"""
BOT_PAGE = "<!doctype html><title>Welcome</title><p>Under construction</p>"


@pytest.fixture
def phish_server():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            port = self.server.server_address[1]
            if self.path == "/icon.png":
                kind, body = "image/png", ICON
            elif self.path == "/kit.js":
                kind, body = "text/javascript", b"window.kit = 1;"
            elif "HeadlessChrome" in self.headers.get("User-Agent", ""):
                kind, body = "text/html", BOT_PAGE.encode()
            else:
                kind, body = "text/html", PHONE_PAGE.format(port=port).encode()
            self.send_response(200)
            self.send_header("Content-Type", kind)
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


async def test_deep_capture_reads_forms_links_favicon_and_artifacts(browser, phish_server, tmp_path, monkeypatch):
    monkeypatch.setattr("app.capture.CAPTURES_DIR", tmp_path)

    result = await capture(browser, phish_server + "/", allowed_origins=[phish_server], second_visit=True)

    assert result.navigation_blocked is False
    assert result.internal_requests_blocked == 0
    assert result.status == 200
    assert result.lang == "ar"
    assert "pay within 24 hours" in result.text
    fields = {f["name"]: f for f in result.forms[0]["fields"]}
    assert fields["cardnumber"]["label"] == "Card number"
    assert fields["cardnumber"]["inputmode"] == "numeric"
    assert fields["otp"]["autocomplete"] == "one-time-code"
    assert result.forms[0]["method"] == "post"
    assert result.forms[0]["action"].endswith("/collect")
    assert "tel:+971501234567" in result.links
    assert "https://wa.me/971501234567" in result.links
    assert result.scripts == [phish_server + "/kit.js"]
    assert "form" in result.skeleton and "input:text" in result.skeleton
    assert result.favicon is not None
    assert result.favicon.sha256 == hashlib.sha256(ICON).hexdigest()
    for ref in (result.screenshot, result.full_screenshot, result.html, result.favicon):
        data = (tmp_path / ref.path.rsplit("/", 1)[-1]).read_bytes()
        assert hashlib.sha256(data).hexdigest() == ref.sha256
    assert result.screenshot.path == result.screenshot_path
    assert result.bot_visit is not None
    assert result.bot_visit.title == "Welcome"
    assert "Under construction" in result.bot_visit.text


async def test_capture_without_second_visit_has_no_bot_visit(browser, phish_server, tmp_path, monkeypatch):
    monkeypatch.setattr("app.capture.CAPTURES_DIR", tmp_path)
    result = await capture(browser, phish_server + "/", allowed_origins=[phish_server])
    assert result.bot_visit is None
    assert result.profile == "phone"
