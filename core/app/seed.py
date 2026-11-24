"""Load data/ into the domains table. Idempotent; officer decisions are never overwritten by the seed."""
from pathlib import Path

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, sessionmaker

from app import cache
from app.brands import load_brands
from app.config import get_settings
from app.db import get_engine
from app.models import Domain
from app.normalize.url import normalize_host

PRIORITY = {"allowlisted": 0, "official": 1, "confirmed": 2}


def read_lines(path: Path) -> list[list[str]]:
    if not path.exists():
        return []
    lines = (line.split("#", 1)[0].split() for line in path.read_text(encoding="utf-8").splitlines())
    return [fields for fields in lines if fields]


def collect(data_dir: str) -> dict[str, tuple[str, str | None]]:
    """domain -> (status, brand_id). A stronger status wins when a domain appears in several files."""
    root = Path(data_dir)
    rows: dict[str, tuple[str, str | None]] = {}

    def put(domain: str, status: str, brand_id: str | None) -> None:
        domain = normalize_host(domain)
        current = rows.get(domain)
        if current is None or PRIORITY[status] >= PRIORITY[current[0]]:
            rows[domain] = (status, brand_id)

    for fields in read_lines(root / "tranco_top10k.txt"):
        put(fields[0], "allowlisted", None)
    for fields in read_lines(root / "allowlist.txt"):
        put(fields[0], "allowlisted", None)
    for fields in read_lines(root / "official.txt"):
        put(fields[0], "official", fields[1] if len(fields) > 1 else None)
    for brand in load_brands(data_dir):
        for domain in brand["official_domains"]:
            put(domain, "official", brand["id"])
    for fields in read_lines(root / "blocklist.txt"):
        put(fields[0], "confirmed", fields[1] if len(fields) > 1 else None)
    return rows


def seed(session: Session, data_dir: str) -> int:
    rows = collect(data_dir)
    values = [{"domain": d, "status": s, "brand_id": b, "source": "seed"} for d, (s, b) in rows.items()]
    for start in range(0, len(values), 2000):
        statement = insert(Domain).values(values[start : start + 2000])
        session.execute(
            statement.on_conflict_do_update(
                index_elements=[Domain.domain],
                set_={"status": statement.excluded.status, "brand_id": statement.excluded.brand_id, "updated_at": func.now()},
                where=(Domain.source == "seed")
                & ((Domain.status != statement.excluded.status) | Domain.brand_id.is_distinct_from(statement.excluded.brand_id)),
            )
        )
    return len(values)


if __name__ == "__main__":
    with sessionmaker(get_engine())() as session:
        count = seed(session, get_settings().data_dir)
        session.commit()
    cache.bump_blocklist_version()
    print(f"seeded {count} domains")
