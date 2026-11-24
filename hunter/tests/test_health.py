import os
import time

from app.health import is_healthy


def test_fresh_heartbeat_is_healthy(tmp_path):
    beat = tmp_path / "beat"
    beat.touch()
    assert is_healthy(beat)


def test_stale_heartbeat_is_unhealthy(tmp_path):
    beat = tmp_path / "beat"
    beat.touch()
    old = time.time() - 120
    os.utime(beat, (old, old))
    assert not is_healthy(beat)


def test_missing_heartbeat_is_unhealthy(tmp_path):
    assert not is_healthy(tmp_path / "absent")
