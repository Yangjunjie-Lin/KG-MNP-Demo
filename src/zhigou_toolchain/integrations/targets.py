from __future__ import annotations

import ipaddress
import socket
from collections.abc import Set as AbstractSet
from urllib.parse import urlsplit


def validate_endpoint(url: str, *, allowed_hosts: AbstractSet[str] = frozenset(), allow_local_graphdb: bool = False) -> tuple[str, str, int]:
    parsed = urlsplit(url)
    if parsed.scheme not in {"https", "http"} or parsed.username or parsed.password or not parsed.hostname or parsed.query or parsed.fragment:
        raise ValueError("endpoint scheme, userinfo or host is not allowed")
    host = parsed.hostname
    local_name = host in {"localhost", "127.0.0.1", "::1"}
    if local_name and not allow_local_graphdb:
        raise ValueError("loopback target is not explicitly approved")
    if host not in allowed_hosts and not (allow_local_graphdb and local_name):
        raise ValueError("target host is not allowlisted")
    addresses = {item[4][0] for item in socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)}
    for address in addresses:
        parsed_ip = ipaddress.ip_address(address)
        if (parsed_ip.is_private or parsed_ip.is_link_local or parsed_ip.is_loopback or parsed_ip.is_reserved) and not (allow_local_graphdb and local_name and parsed_ip.is_loopback):
            raise ValueError("private or link-local egress is not allowed")
    return parsed.scheme, host, parsed.port or (443 if parsed.scheme == "https" else 80)
