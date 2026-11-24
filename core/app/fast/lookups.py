"""Google Safe Browsing and VirusTotal. Each runs only when its key is set; results are cached for an hour."""
import base64
import hashlib

import httpx

from app import cache

TTL = 3600
GSB_URL = "https://safebrowsing.googleapis.com/v4/threatMatches:find?key={key}"
VT_URL = "https://www.virustotal.com/api/v3/urls/{id}"
VT_SUBMIT = "https://www.virustotal.com/api/v3/urls"


def url_key(prefix: str, url: str) -> str:
    return f"kp:{prefix}:{hashlib.sha256(url.encode()).hexdigest()[:32]}"


def gsb_body(url: str) -> dict:
    return {
        "client": {"clientId": "kartoshka-police", "clientVersion": "1.0"},
        "threatInfo": {
            "threatTypes": ["MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE", "POTENTIALLY_HARMFUL_APPLICATION"],
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "threatEntries": [{"url": url}],
        },
    }


def gsb_parse(data: dict) -> dict:
    matches = data.get("matches", [])
    return {"hit": bool(matches), "threat": matches[0]["threatType"].lower().replace("_", " ") if matches else None}


async def gsb(url: str, key: str, timeout_s: float) -> dict:
    cache_key = url_key("gsb", url)
    cached = await cache.get_json(cache_key)
    if cached is not None:
        return cached
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        response = await client.post(GSB_URL.format(key=key), json=gsb_body(url))
    response.raise_for_status()
    result = gsb_parse(response.json())
    await cache.set_json(cache_key, result, TTL)
    return result


def gsb_sync(url: str, key: str, timeout_s: float = 10.0) -> dict:
    cache_key = url_key("gsb", url)
    cached = cache.get_json_sync(cache_key)
    if cached is not None:
        return cached
    response = httpx.post(GSB_URL.format(key=key), json=gsb_body(url), timeout=timeout_s)
    response.raise_for_status()
    result = gsb_parse(response.json())
    cache.set_json_sync(cache_key, result, TTL)
    return result


def vt_id(url: str) -> str:
    return base64.urlsafe_b64encode(url.encode()).decode().rstrip("=")


def vt_parse(data: dict) -> dict:
    stats = data.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
    positives = stats.get("malicious", 0) + stats.get("suspicious", 0)
    total = sum(stats.values()) if stats else 0
    return {"known": True, "positives": positives, "total": total}


async def virustotal(url: str, key: str, timeout_s: float) -> dict:
    cache_key = url_key("vt", url)
    cached = await cache.get_json(cache_key)
    if cached is not None:
        return cached
    async with httpx.AsyncClient(timeout=timeout_s, headers={"x-apikey": key}) as client:
        response = await client.get(VT_URL.format(id=vt_id(url)))
    if response.status_code == 404:
        result = {"known": False, "positives": 0, "total": 0}
    else:
        response.raise_for_status()
        result = vt_parse(response.json())
    await cache.set_json(cache_key, result, TTL)
    return result


def virustotal_sync(url: str, key: str, timeout_s: float = 15.0, submit: bool = True) -> dict:
    """Deep path: look the URL up and, if VirusTotal has never seen it, submit it for a scan."""
    cache_key = url_key("vt", url)
    cached = cache.get_json_sync(cache_key)
    if cached is not None and cached.get("known"):
        return cached
    headers = {"x-apikey": key}
    response = httpx.get(VT_URL.format(id=vt_id(url)), headers=headers, timeout=timeout_s)
    if response.status_code == 404:
        if submit:
            httpx.post(VT_SUBMIT, data={"url": url}, headers=headers, timeout=timeout_s)
        result = {"known": False, "positives": 0, "total": 0, "submitted": submit}
    else:
        response.raise_for_status()
        result = vt_parse(response.json())
    cache.set_json_sync(cache_key, result, TTL)
    return result
