import sys

from rq import Worker

from app.queue import get_redis


def main() -> int:
    try:
        return 0 if Worker.count(connection=get_redis()) > 0 else 1
    except Exception:
        return 1


if __name__ == "__main__":
    sys.exit(main())
