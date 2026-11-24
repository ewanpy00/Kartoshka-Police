"""Expand URL shorteners on the fast path.

Only known shortener hosts are followed here; the sandbox records the full chain on the deep path.
Every hop passes the internal-address test, only headers are read, and the whole walk shares one budget.
"""
import asyncio
import logging
from urllib.parse import urljoin, urlsplit

import httpx

from app.netguard import Unresolvable, is_internal
from app.normalize.url import clean, normalize_host

log = logging.getLogger("core.unshorten")

SHORTENERS = frozenset(
    """bit.ly t.ly tinyurl.com cutt.ly t.co goo.gl ow.ly is.gd buff.ly rebrand.ly shorturl.at rb.gy tiny.cc
    bl.ink s.id v.gd qrco.de bitly.com tr.im soo.gd clck.ru shorte.st adf.ly bc.vc ouo.io lnk.to surl.li
    u.to urlz.fr t2m.io 1url.com short.io link.ly bitly.ws tiny.one shorturl.asia gg.gg cutt.us snip.ly
    rotf.lol shrtco.de 2u.pw kutt.it dub.sh""".split()
)
MAX_HOPS = 10
MOBILE_UA = (
    "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Mobile Safari/537.36"
)


def is_shortener(host: str) -> bool:
    host = normalize_host(host)
    return host in SHORTENERS or host.removeprefix("www.") in SHORTENERS


class Expansion:
    def __init__(self, url: str):
        self.chain = [url]
        self.final = url
        self.complete = True
        self.error: str | None = None


async def hop(client: httpx.AsyncClient, url: str) -> str | None:
    host = urlsplit(url).hostname or ""
    if await asyncio.to_thread(is_internal, host):
        raise PermissionError(f"internal host {host}")
    response = await client.head(url)
    if response.status_code in (405, 501):
        async with client.stream("GET", url) as streamed:
            response = streamed
    if response.is_redirect and "location" in response.headers:
        return urljoin(url, response.headers["location"])
    return None


async def expand(url: str, budget_s: float) -> Expansion:
    """Follow redirects starting at a shortener, until a non-shortener answers or the budget runs out."""
    result = Expansion(clean(url))
    if not is_shortener(urlsplit(result.final).hostname or ""):
        return result
    headers = {"User-Agent": MOBILE_UA, "Accept-Language": "ar-AE,ar;q=0.9,en;q=0.8"}
    try:
        async with httpx.AsyncClient(headers=headers, timeout=budget_s, follow_redirects=False) as client:
            async with asyncio.timeout(budget_s):
                current = result.final
                for _ in range(MAX_HOPS):
                    nxt = await hop(client, current)
                    if nxt is None:
                        break
                    current = clean(nxt)
                    result.chain.append(current)
                    result.final = current
                    if not is_shortener(urlsplit(current).hostname or ""):
                        break
    except TimeoutError:
        result.complete, result.error = False, "timeout"
    except (PermissionError, Unresolvable) as error:
        result.complete, result.error = False, str(error)
        log.warning("shortener expansion stopped url=%s reason=%s", url, error)
    except httpx.HTTPError as error:
        result.complete, result.error = False, type(error).__name__
    return result
