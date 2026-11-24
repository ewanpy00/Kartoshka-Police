from sqlalchemy import func, select

from app.config import get_settings
from app.models import Domain
from app.seed import seed


def test_seed_twice_leaves_the_same_row_count(session):
    count = select(func.count()).select_from(Domain)
    seed(session, get_settings().data_dir)
    first = session.scalar(count)
    seed(session, get_settings().data_dir)
    assert session.scalar(count) == first
    assert session.get(Domain, "uaepass.ae").status == "official"
    assert session.get(Domain, "uaepass-verify.example").brand_id == "uaepass"
