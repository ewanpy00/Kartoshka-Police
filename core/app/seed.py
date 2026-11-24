from pathlib import Path

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, sessionmaker

from app.brands import load_brands
from app.config import get_settings
from app.db import get_engine
from app.models import Domain


def read_lines(path: Path) -> list[list[str]]:
    lines = (line.split("#", 1)[0].split() for line in path.read_text(encoding="utf-8").splitlines())
    return [fields for fields in lines if fields]


def upsert(session: Session, domain: str, status: str, brand_id: str | None) -> None:
    statement = insert(Domain).values(domain=domain.lower(), status=status, brand_id=brand_id)
    session.execute(
        statement.on_conflict_do_update(
            index_elements=[Domain.domain],
            set_={"status": status, "brand_id": brand_id, "updated_at": func.now()},
            where=(Domain.status != status) | Domain.brand_id.is_distinct_from(brand_id),
        )
    )


def seed(session: Session, data_dir: str) -> None:
    root = Path(data_dir)
    for brand in load_brands(data_dir):
        for domain in brand["official_domains"]:
            upsert(session, domain, "official", brand["id"])
    for (domain,) in read_lines(root / "allowlist.txt"):
        upsert(session, domain, "allowlisted", None)
    for domain, brand_id in read_lines(root / "blocklist.txt"):
        upsert(session, domain, "confirmed", brand_id)


if __name__ == "__main__":
    with sessionmaker(get_engine())() as session:
        seed(session, get_settings().data_dir)
        session.commit()
