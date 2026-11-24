from admin_factories import add_check, add_evidence
from app.models import Domain


def confirmed_case(session, domain, by="officer", infrastructure=None, title="Fake login", brand=None):
    """A confirmed domain with one check and an evidence record whose infrastructure is as given."""
    check = add_check(session, domain)
    evidence = add_evidence(session, check, title=title, brand=brand)
    evidence.payload = {**evidence.payload, "infrastructure": infrastructure or {}}
    session.add(Domain(domain=domain, status="confirmed", confirmed_by=by))
    session.flush()
    return evidence
