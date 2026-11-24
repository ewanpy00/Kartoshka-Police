"""Step 1 of the engine: split a URL the way a browser would read it."""
import re
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from urllib.parse import parse_qsl, urlsplit, urlunsplit

import idna
import tldextract

SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")


@lru_cache
def extractor() -> tldextract.TLDExtract:
    # Bundled public suffix snapshot (no network), private suffixes included so that
    # victim.github.io and scam.pages.dev are their own registrable domains.
    return tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None, include_psl_private_domains=True)


def encode_label(label: str) -> str:
    try:
        return idna.encode(label).decode("ascii")
    except idna.IDNAError:
        return label


def normalize_host(host: str) -> str:
    """Map a host as browsers do (UTS 46, non-transitional), drop trailing dots and punycode each label.

    A label that fails to encode is kept as given, so one odd label cannot stop its parents from matching.
    It is invalid or non-ASCII, so it cannot equal a seeded label.
    """
    try:
        host = idna.uts46_remap(host, std3_rules=False, transitional=False)
    except idna.IDNAError:
        host = host.lower()
    return ".".join(encode_label(label) for label in host.rstrip(".").split("."))


def to_unicode(host: str) -> str:
    labels = []
    for label in host.split("."):
        try:
            labels.append(idna.decode(label) if label.startswith("xn--") else label)
        except idna.IDNAError:
            labels.append(label)
    return ".".join(labels)


def clean(url: str) -> str:
    """Browsers read a backslash as a slash and add http:// to a bare host."""
    url = url.strip().replace("\\", "/")
    if not SCHEME_RE.match(url):
        url = "http://" + url.lstrip("/")
    return url


def host_and_parents(url: str) -> list[str]:
    """The host a browser would visit, then its parent domains."""
    parsed = urlsplit(clean(url))
    labels = normalize_host(parsed.hostname or "").split(".")
    return [".".join(labels[i:]) for i in range(len(labels) - 1)] or [".".join(labels)]


def strip_query(url: str) -> str:
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


@dataclass
class NormalizedURL:
    original: str
    url: str
    final: str
    scheme: str
    host: str
    host_unicode: str
    domain: str
    subdomain: str
    tld: str
    path: str
    query: str
    fragment: str
    port: int | None
    params: dict[str, str]
    is_ip: bool
    is_private_suffix: bool
    userinfo: bool
    chain: list[str] = field(default_factory=list)

    @property
    def domain_label(self) -> str:
        """The registrable name without its suffix: uaepass-verify for uaepass-verify.top."""
        return self.domain[: -len(self.tld) - 1] if self.tld and self.domain.endswith("." + self.tld) else self.domain

    def as_dict(self) -> dict:
        return asdict(self)


def normalize(url: str, final: str | None = None, chain: list[str] | None = None) -> NormalizedURL:
    cleaned = clean(url)
    target = clean(final) if final else cleaned
    parts = urlsplit(target)
    host = normalize_host(parts.hostname or "")
    try:
        port = parts.port
    except ValueError:
        port = None
    extracted = extractor()(host)
    is_ip = bool(re.fullmatch(r"[0-9.]+", host)) or ":" in host
    if is_ip:
        domain, subdomain, tld = host, "", ""
    else:
        domain = extracted.top_domain_under_public_suffix or host
        subdomain, tld = extracted.subdomain, extracted.suffix
    return NormalizedURL(
        original=url,
        url=cleaned,
        final=target,
        scheme=parts.scheme.lower(),
        host=host,
        host_unicode=to_unicode(host),
        domain=domain,
        subdomain=subdomain,
        tld=tld,
        path=parts.path or "/",
        query=parts.query,
        fragment=parts.fragment,
        port=port,
        params=dict(parse_qsl(parts.query, keep_blank_values=True)[:50]),
        is_ip=is_ip,
        is_private_suffix=bool(getattr(extracted, "is_private", False)),
        userinfo="@" in parts.netloc,
        chain=chain or [cleaned],
    )
