import logging
import socketserver
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from app.capture import capture

SERVICE_NAMES = ["postgres", "redis", "core", "worker", "hunter", "certstream", "console", "adguard", "sandbox"]
PRIVATE_IP = "10.20.30.40"
METADATA_IP = "169.254.169.254"
EXTRA_HOSTS = ["host.docker.internal", PRIVATE_IP, METADATA_IP, "127.0.0.1"]


class Canary(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self):
        super().__init__(("127.0.0.1", 0), CanaryHandler)
        self.connections = 0
        self.lock = threading.Lock()

    def reset(self):
        with self.lock:
            self.connections = 0


class CanaryHandler(socketserver.BaseRequestHandler):
    def handle(self):
        with self.server.lock:
            self.server.connections += 1
        self.request.recv(4096)
        self.request.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok")


def page_html(canary_port: int) -> str:
    targets = [f"http://{name}:8000/" for name in SERVICE_NAMES]
    targets += [
        "http://host.docker.internal:8000/",
        f"http://{PRIVATE_IP}/",
        f"http://{METADATA_IP}/",
        f"http://127.0.0.1:{canary_port}/",
    ]
    return f"""<!doctype html>
<title>hostile</title>
<img src="/hold" alt="">
<iframe src="/redirect"></iframe>
<script>
const targets = {targets};
const attempts = targets.map(t => fetch(t, {{mode: "no-cors"}}).catch(() => null));
attempts.push(new Promise(done => {{
  const img = new Image();
  img.onload = img.onerror = done;
  img.src = "http://127.0.0.1:{canary_port}/image.png";
}}));
attempts.push(new Promise(done => {{
  const ws = new WebSocket("ws://127.0.0.1:{canary_port}/socket");
  ws.onopen = ws.onerror = ws.onclose = done;
}}));
Promise.allSettled(attempts).then(() => fetch("/release"));
</script>"""


@pytest.fixture
def servers():
    canary = Canary()
    threading.Thread(target=canary.serve_forever, daemon=True).start()
    canary_port = canary.server_address[1]
    released = threading.Event()

    class Page(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/redirect":
                self.send_response(302)
                self.send_header("Location", f"http://127.0.0.1:{canary_port}/redirected")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if self.path == "/hold":
                released.wait(timeout=10)
            elif self.path == "/release":
                released.set()
            body = page_html(canary_port).encode() if self.path == "/" else b"ok"
            self.send_response(200)
            self.send_header("Content-Type", "text/html" if self.path == "/" else "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    page = ThreadingHTTPServer(("127.0.0.1", 0), Page)
    threading.Thread(target=page.serve_forever, daemon=True).start()
    yield canary, f"http://127.0.0.1:{page.server_address[1]}"
    page.shutdown()
    canary.shutdown()
    page.server_close()
    canary.server_close()


async def test_hostile_page_reaches_nothing_internal(browser, servers, caplog, tmp_path, monkeypatch):
    canary, page_origin = servers
    monkeypatch.setattr("app.capture.CAPTURES_DIR", tmp_path)

    with urllib.request.urlopen(f"http://127.0.0.1:{canary.server_address[1]}/control") as response:
        assert response.read() == b"ok"
    assert canary.connections == 1
    canary.reset()

    with caplog.at_level(logging.WARNING, logger="sandbox.guard"):
        result = await capture(browser, page_origin + "/", allowed_origin=page_origin)

    attempts = len(SERVICE_NAMES) + len(EXTRA_HOSTS) + 2 + 1
    assert canary.connections == 0
    assert result.navigation_blocked is False
    assert result.title == "hostile"
    assert result.internal_requests_blocked >= attempts
    assert set(result.internal_hosts_blocked) == set(SERVICE_NAMES + EXTRA_HOSTS)
    logged = [record.getMessage() for record in caplog.records if record.name == "sandbox.guard"]
    for host in SERVICE_NAMES + EXTRA_HOSTS:
        assert any(f"//{host}" in line and page_origin in line for line in logged), host


async def test_redirect_to_internal_host_blocks_the_navigation(browser, servers, tmp_path, monkeypatch):
    canary, page_origin = servers
    monkeypatch.setattr("app.capture.CAPTURES_DIR", tmp_path)
    canary_url = f"http://127.0.0.1:{canary.server_address[1]}/redirected"

    result = await capture(browser, page_origin + "/redirect", allowed_origin=page_origin)

    assert canary.connections == 0
    assert result.navigation_blocked is True
    assert result.final_url == canary_url
    assert result.title == ""
    assert result.screenshot_path is None
    assert result.internal_requests_blocked == 1
    assert result.internal_hosts_blocked == ["127.0.0.1"]
    assert list(tmp_path.iterdir()) == []
