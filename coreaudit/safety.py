"""Only fetch public web pages. Blocks private/internal addresses (SSRF protection)."""
import ipaddress
import socket
from urllib.parse import urlparse


class UnsafeURL(ValueError):
    pass


def normalize_url(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        raise UnsafeURL("Empty URL")
    if "://" not in raw:
        raw = "https://" + raw
    p = urlparse(raw)
    if p.scheme not in ("http", "https"):
        raise UnsafeURL("Only http and https are allowed")
    if not p.hostname or "." not in p.hostname:
        raise UnsafeURL("Enter a full domain, like example.com")
    if p.username or p.password:
        raise UnsafeURL("URLs with credentials are not allowed")
    if p.port not in (None, 80, 443):
        raise UnsafeURL("Unusual ports are not allowed")
    return f"{p.scheme}://{p.hostname}{p.path or '/'}"


def assert_public(url: str) -> None:
    host = urlparse(url).hostname
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as e:
        raise UnsafeURL(f"Cannot resolve {host}") from e
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast
                or ip.is_reserved or ip.is_unspecified):
            raise UnsafeURL("That address is not a public website")
