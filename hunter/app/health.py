import sys
import time
from pathlib import Path

HEARTBEAT_PATH = Path("/tmp/hunter.heartbeat")
MAX_AGE_SECONDS = 60


def is_healthy(path: Path = HEARTBEAT_PATH, now: float | None = None) -> bool:
    if now is None:
        now = time.time()
    try:
        return now - path.stat().st_mtime <= MAX_AGE_SECONDS
    except FileNotFoundError:
        return False


if __name__ == "__main__":
    sys.exit(0 if is_healthy() else 1)
