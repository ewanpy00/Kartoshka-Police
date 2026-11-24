"""Link strength (docs/admin-dashboard.md, "Campaign graph rules").

Only strong links merge domains into one campaign. Weak ones (ASN, registrar, name server, CDN
addresses) are recorded and shown, because unrelated sites share them all the time, and a bulk confirm
over a campaign built on them could block a legitimate site.
"""
from functools import lru_cache
from pathlib import Path

from app.config import get_settings

STRONG_KINDS = ("phone", "whatsapp", "payment", "kit_hash", "favicon_hash", "cert", "ip")
WEAK_KINDS = ("asn", "registrar", "ns", "kit_sim")
# Kinds written before the rules existed: an IP on a CDN and a big DNS provider.
LEGACY_WEAK = ("ip_shared", "ns_provider")
LINKING = STRONG_KINDS


@lru_cache
def favicon_deny() -> frozenset[str]:
    """SHA-256 of favicons that CMS and hosting defaults serve to everyone (data/favicon_deny.txt)."""
    path = Path(get_settings().data_dir) / "favicon_deny.txt"
    if not path.is_file():
        return frozenset()
    return frozenset(line.split()[0].lower() for line in path.read_text().splitlines() if line.strip() and not line.startswith("#"))


def strength(kind: str, value: str, shared_infra: bool = False) -> str:
    """`shared_infra`: the site sits on a CDN or big cloud, so its addresses and certificate say nothing
    about who runs it (Cloudflare's shared certificates list many unrelated customers).

    A certificate node is keyed by issuer, subject and start date, so two different sites can only share
    one through a multi-SAN certificate; a single-domain Let's Encrypt certificate never links anyone."""
    if kind not in STRONG_KINDS:
        return "weak"
    if kind in ("ip", "cert") and shared_infra:
        return "weak"
    if kind == "favicon_hash" and value.lower() in favicon_deny():
        return "weak"
    return "strong"
