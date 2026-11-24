import json
import logging
import time
import urllib.error
import urllib.request
from collections import OrderedDict, deque

log = logging.getLogger("hunter")

SEEN_LIMIT = 10_000
WINDOW_SECONDS = 60
POST_TIMEOUT_SECONDS = 5


class Submitter:
    """Sends flagged domains to core for a deep check, once each and at most `per_minute` a minute."""

    def __init__(self, core_url: str, token: str, per_minute: int, clock=time.monotonic) -> None:
        self.endpoint = f"{core_url.rstrip('/')}/v1/check"
        self.token = token
        self.per_minute = per_minute
        self.clock = clock
        self.seen: OrderedDict[str, None] = OrderedDict()
        self.sent: deque[float] = deque()
        if not token:
            log.warning("CORE_WRITE_TOKEN is empty, submission to core is disabled")

    def submit(self, name: str) -> bool:
        """Post one certificate name. Returns whether core accepted it."""
        domain = name.lower().removeprefix("*.")
        if not self.token or domain in self.seen:
            return False
        now = self.clock()
        while self.sent and now - self.sent[0] >= WINDOW_SECONDS:
            self.sent.popleft()
        if len(self.sent) >= self.per_minute:
            log.info("submission cap reached, dropped domain=%s", domain)
            return False
        self.sent.append(now)
        if not self.post(domain):
            return False
        self.seen[domain] = None
        if len(self.seen) > SEEN_LIMIT:
            self.seen.popitem(last=False)
        return True

    def post(self, domain: str) -> bool:
        body = json.dumps({"url": f"https://{domain}/", "source": "hunter", "mode": "deep"}).encode()
        request = urllib.request.Request(
            self.endpoint,
            data=body,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.token}"},
        )
        try:
            with urllib.request.urlopen(request, timeout=POST_TIMEOUT_SECONDS):
                return True
        except urllib.error.HTTPError as error:
            log.warning("submit failed domain=%s status=%d", domain, error.code)
        except Exception as error:
            log.warning("submit failed domain=%s error=%s", domain, type(error).__name__)
        return False
