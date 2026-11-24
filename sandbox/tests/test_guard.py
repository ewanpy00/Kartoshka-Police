import pytest

from app import guard
from app.guard import is_internal

COMPOSE_NAMES = ["postgres", "redis", "core", "worker", "hunter", "certstream", "console", "adguard", "sandbox"]


@pytest.mark.parametrize("host", COMPOSE_NAMES)
async def test_compose_service_names_are_internal(host):
    assert await is_internal(host)


@pytest.mark.parametrize(
    "host",
    [
        "host.docker.internal",
        "gateway.docker.internal",
        "printer.local",
        "app.localhost",
        "169.254.169.254",
        "10.1.2.3",
        "::1",
        "::ffff:127.0.0.1",
        "100.64.0.1",
        "fd00::1",
    ],
)
async def test_internal_names_and_addresses(host):
    assert await is_internal(host)


async def test_public_ip_literal_is_not_internal():
    assert not await is_internal("93.184.216.34")


async def test_public_name_resolving_to_private_address_is_internal(monkeypatch):
    monkeypatch.setattr(guard, "_resolve", lambda host: ["93.184.216.34", "10.0.0.7"])
    assert await is_internal("looks-public.example.com")


async def test_public_name_resolving_to_public_address_is_not_internal(monkeypatch):
    monkeypatch.setattr(guard, "_resolve", lambda host: ["93.184.216.34"])
    assert not await is_internal("example.com")


async def test_unresolvable_name_is_not_internal(monkeypatch):
    def fail(host):
        raise guard.socket.gaierror("no such host")

    monkeypatch.setattr(guard, "_resolve", fail)
    assert not await is_internal("does-not-exist.example.com")
