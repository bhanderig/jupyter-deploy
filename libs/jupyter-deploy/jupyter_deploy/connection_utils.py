import http.client
import socket
import ssl
from collections.abc import Generator
from contextlib import contextmanager

import certifi


def resolve_ips(host: str, port: int = 443) -> list[str]:
    """Resolve a hostname to a sorted list of unique IPv4 addresses.

    Raises:
        socket.gaierror: If DNS resolution fails.
        ValueError: If DNS returns no records.
    """
    results = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
    if not results:
        raise ValueError(f"{host} returned no records")
    return sorted(set(str(r[4][0]) for r in results))


@contextmanager
def https_connection(
    host: str, port: int = 443, timeout: int = 10
) -> Generator[http.client.HTTPSConnection, None, None]:
    """Yield an HTTPS connection with certificate verification via certifi."""
    ctx = ssl.create_default_context(cafile=certifi.where())
    conn = http.client.HTTPSConnection(host, port, timeout=timeout, context=ctx)
    try:
        yield conn
    finally:
        conn.close()
