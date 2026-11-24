from admin_factories import add_check, add_evidence
from app.graph.cluster import ingest_evidence

NO_INFRA = {"rdap_status": "ok", "registrar": None, "name_servers": [], "ip": None, "ip_country": None, "proxy": None}


def ingest(session, domain, *, phones=(), payment_hosts=(), brand=None, hub_threshold=None, **infrastructure):
    """Create a check and evidence record for the domain, then ingest it into the graph."""
    check = add_check(session, domain)
    evidence = add_evidence(session, check, brand=brand)
    evidence.payload["identity"]["domain"] = domain
    evidence.payload["infrastructure"] = {**NO_INFRA, **infrastructure}
    evidence.payload["scam"]["phones"] = list(phones)
    evidence.payload["scam"]["payment_hosts"] = list(payment_hosts)
    session.flush()
    ingest_evidence(session, evidence.id, hub_threshold)
    session.flush()
    return evidence
