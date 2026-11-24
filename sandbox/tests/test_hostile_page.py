import logging
import socketserver
import threading
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from app.capture import capture
from app.guard import Guard

SERVICE_NAMES = ["postgres", "redis", "core", "worker", "hunter", "certstream", "console", "adguard", "sandbox"]
PRIVATE_IP = "10.20.30.40"
METADATA_IP = "169.254.169.254"
EXTRA_HOSTS = ["host.docker.internal", PRIVATE_IP, METADATA_IP, "127.0.0.1"]
# 13 fetches, 1 image, 1 WebSocket, 1 iframe redirect hop, then cross-site frame fetch,
# cross-site frame redirect hop and worker fetch
ATTEMPTS = 19
CANARY_PATHS = ["/image.png", "/socket", "/redirected", "/from-frame", "/redirected-from-frame", "/from-worker"]


class Canary(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self):
        super().__init__(("127.0.0.1", 0), CanaryHandler)
        self.paths = []
        self.lock = threading.Lock()

    @property
    def connections(self):
        return len(self.paths)

    def reset(self):
        with self.lock:
            self.paths.clear()


class CanaryHandler(socketserver.BaseRequestHandler):
    def handle(self):
        request_line = self.request.recv(4096).split(b"\r\n")[0].decode(errors="replace")
        with self.server.lock:
            self.server.paths.append(request_line.split(" ")[1] if " " in request_line else request_line)
        self.request.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok")


def main_page(port: int, canary_port: int) -> str:
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
<iframe src="http://localhost:{port}/frame"></iframe>
<iframe src="http://localhost:{port}/redirect-from-frame"></iframe>
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
attempts.push(new Promise(done => {{
  const worker = new Worker("/worker.js");
  worker.onmessage = done;
}}));
attempts.push(new Promise(done => {{
  window.onmessage = event => event.data === "frame-done" && done();
}}));
Promise.allSettled(attempts).then(() => fetch("/release"));
</script>"""


def frame_page(canary_port: int) -> str:
    return f"""<!doctype html>
<script>
fetch("http://127.0.0.1:{canary_port}/from-frame", {{mode: "no-cors"}})
  .catch(() => null)
  .finally(() => parent.postMessage("frame-done", "*"));
</script>"""


def worker_script(canary_port: int) -> str:
    return f"""fetch("http://127.0.0.1:{canary_port}/from-worker", {{mode: "no-cors"}})
  .catch(() => null)
  .finally(() => postMessage("worker-done"));"""


@pytest.fixture
def servers():
    canary = Canary()
    threading.Thread(target=canary.serve_forever, daemon=True).start()
    canary_port = canary.server_address[1]
    released = threading.Event()

    class Page(BaseHTTPRequestHandler):
        def do_GET(self):
            port = self.server.server_address[1]
            if self.path in ("/redirect", "/redirect-from-frame"):
                target = "/redirected" if self.path == "/redirect" else "/redirected-from-frame"
                self.send_response(302)
                self.send_header("Location", f"http://127.0.0.1:{canary_port}{target}")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if self.path == "/hold":
                released.wait(timeout=10)
            elif self.path == "/release":
                released.set()
            kind, body = {
                "/": ("text/html", main_page(port, canary_port)),
                "/frame": ("text/html", frame_page(canary_port)),
                "/worker.js": ("text/javascript", worker_script(canary_port)),
            }.get(self.path, ("text/plain", "ok"))
            self.send_response(200)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body.encode())

        def log_message(self, *args):
            pass

    page = ThreadingHTTPServer(("127.0.0.1", 0), Page)
    threading.Thread(target=page.serve_forever, daemon=True).start()
    port = page.server_address[1]
    yield canary, [f"http://127.0.0.1:{port}", f"http://localhost:{port}"]
    page.shutdown()
    canary.shutdown()
    page.server_close()
    canary.server_close()


def prove_canary_reachable(canary):
    with urllib.request.urlopen(f"http://127.0.0.1:{canary.server_address[1]}/control") as response:
        assert response.read() == b"ok"
    assert canary.paths == ["/control"]
    canary.reset()


async def test_hostile_page_reaches_nothing_internal(browser, servers, caplog, tmp_path, monkeypatch):
    canary, origins = servers
    monkeypatch.setattr("app.capture.CAPTURES_DIR", tmp_path)
    prove_canary_reachable(canary)

    with caplog.at_level(logging.WARNING, logger="sandbox.guard"):
        result = await capture(browser, origins[0] + "/", allowed_origins=origins)

    assert canary.paths == []
    assert result.navigation_blocked is False
    assert result.title == "hostile"
    assert result.internal_requests_blocked == ATTEMPTS
    assert set(result.internal_hosts_blocked) == set(SERVICE_NAMES + EXTRA_HOSTS)
    logged = [record.getMessage() for record in caplog.records if record.name == "sandbox.guard"]
    assert len(logged) == ATTEMPTS
    for host in SERVICE_NAMES + EXTRA_HOSTS:
        assert any(f"//{host}" in line and origins[0] in line for line in logged), host


async def test_unguarded_page_reaches_the_canary_everywhere(browser, servers, tmp_path, monkeypatch):
    canary, origins = servers
    monkeypatch.setattr("app.capture.CAPTURES_DIR", tmp_path)

    async def allow_everything(self, url):
        return False

    monkeypatch.setattr(Guard, "blocks", allow_everything)
    prove_canary_reachable(canary)

    await capture(browser, origins[0] + "/", allowed_origins=origins)

    assert set(CANARY_PATHS) <= set(canary.paths)


async def test_redirect_to_internal_host_blocks_the_navigation(browser, servers, tmp_path, monkeypatch):
    canary, origins = servers
    monkeypatch.setattr("app.capture.CAPTURES_DIR", tmp_path)
    canary_url = f"http://127.0.0.1:{canary.server_address[1]}/redirected"

    result = await capture(browser, origins[0] + "/redirect", allowed_origins=origins)

    assert canary.paths == []
    assert result.navigation_blocked is True
    assert result.final_url == canary_url
    assert result.title == ""
    assert result.screenshot_path is None
    assert result.internal_requests_blocked == 1
    assert result.internal_hosts_blocked == ["127.0.0.1"]
    assert list(tmp_path.iterdir()) == []
