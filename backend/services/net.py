"""SSRF guard for any server-side URL fetch."""
import ipaddress
import socket
from urllib.parse import urlparse


class UnsafeURL(ValueError):
    pass


def assert_public_http_url(url: str, allow_hosts: set[str] | None = None) -> str:
    """Allow only http(s) URLs whose host resolves to public addresses (blocks localhost/RFC1918/link-local/metadata)."""
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise UnsafeURL("Only http(s) URLs are allowed.")
    if allow_hosts and p.hostname in allow_hosts:
        return url
    try:
        infos = socket.getaddrinfo(p.hostname, p.port or (443 if p.scheme == "https" else 80), proto=socket.IPPROTO_TCP)
    except socket.gaierror:
        raise UnsafeURL("Host could not be resolved.")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            raise UnsafeURL("URL points to a non-public address.")
    return url
