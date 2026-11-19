import ipaddress
import os
import socket
from urllib.parse import urlsplit


class BlockedURL(ValueError):
    """Raised when a URL is blocked due to private address, invalid scheme, or SSRF policy."""
    pass


def check_url(url: str) -> None:
    """Validate URL against SSRF policy.

    - Skip all checks if ALLOW_PRIVATE_URLS == "1"
    - Scheme must be http or https
    - Host is required
    - Resolves host via socket.getaddrinfo(host, port or default)
    - For EVERY resolved address, reject if is_private, is_loopback,
      is_link_local, is_multicast, is_reserved, is_unspecified (including IPv4-mapped IPv6)
    - Raises BlockedURL(f"blocked private address: {host}") on violation
    """
    if os.environ.get("ALLOW_PRIVATE_URLS") == "1":
        return

    if not url or not isinstance(url, str):
        raise BlockedURL("blocked empty or invalid URL")

    url_str = url.strip()

    if "://" in url_str:
        parsed = urlsplit(url_str)
        scheme = parsed.scheme.lower()
        if scheme not in ("http", "https"):
            raise BlockedURL(f"blocked private address: invalid scheme {scheme}")
        host = parsed.hostname
        port = parsed.port or (80 if scheme == "http" else 443)
    else:
        # Scheme missing or other scheme prefix like file:
        if ":" in url_str and not url_str.startswith("["):
            prefix = url_str.split(":", 1)[0].lower()
            if prefix in ("file", "ftp", "data", "javascript", "gopher", "dict", "ldap"):
                raise BlockedURL(f"blocked private address: invalid scheme {prefix}")
        parsed = urlsplit("//" + url_str)
        host = parsed.hostname
        port = parsed.port or 80

    if not host:
        raise BlockedURL("blocked private address: missing host")

    clean_host = host.strip("[]")

    try:
        addr_infos = socket.getaddrinfo(clean_host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        raise BlockedURL(f"blocked private address: cannot resolve {host}: {e}")
    except Exception as e:
        raise BlockedURL(f"blocked private address: {host}: {e}")

    if not addr_infos:
        raise BlockedURL(f"blocked private address: no addresses resolved for {host}")

    for info in addr_infos:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            raise BlockedURL(f"blocked private address: {host}")

        check_ip = ip.ipv4_mapped if (isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped) else ip

        if (
            check_ip.is_private
            or check_ip.is_loopback
            or check_ip.is_link_local
            or check_ip.is_multicast
            or check_ip.is_reserved
            or check_ip.is_unspecified
        ):
            raise BlockedURL(f"blocked private address: {host}")
