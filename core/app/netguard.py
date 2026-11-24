"""Internal-address test for core's own outbound requests (shortener expansion, RDAP redirects).

Same rule as the sandbox guard: a host is internal if it is a single-label name, ends in .internal,
.local or .localhost, or resolves to any address that is not globally routable.
"""
import ipaddress
import socket

INTERNAL_SUFFIXES = (".internal", ".local", ".localhost")


class Unresolvable(Exception):
    pass


def resolve(host: str) -> list[str]:
    return [info[4][0] for info in socket.getaddrinfo(host, None)]


def is_global(address: str) -> bool:
    ip = ipaddress.ip_address(address.split("%")[0])
    if ip.version == 6 and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return ip.is_global


def is_internal(host: str) -> bool:
    host = (host or "").lower().rstrip(".")
    if not host:
        return True
    try:
        return not is_global(host.strip("[]"))
    except ValueError:
        pass
    if "." not in host or host.endswith(INTERNAL_SUFFIXES):
        return True
    try:
        addresses = resolve(host)
    except (socket.gaierror, UnicodeError) as exc:
        raise Unresolvable(host) from exc
    return any(not is_global(address) for address in addresses)
