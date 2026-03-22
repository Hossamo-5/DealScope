"""
URL Validator — SSRF Protection
================================
Validates user-supplied URLs before passing to scrapers.
Blocks private/internal IPs, non-HTTP schemes, and cloud metadata endpoints.
"""

import ipaddress
import logging
import socket
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Cloud metadata endpoints commonly targeted in SSRF
_BLOCKED_HOSTS = frozenset({
    "metadata.google.internal",
    "metadata.google",
    "169.254.169.254",
    "100.100.100.200",  # Alibaba Cloud
})


def _is_private_ip(hostname: str) -> bool:
    """Check if the hostname resolves to a private/internal IP."""
    try:
        addr = ipaddress.ip_address(hostname)
        return (
            addr.is_private
            or addr.is_loopback
            or addr.is_reserved
            or addr.is_link_local
            or addr.is_multicast
        )
    except ValueError:
        # Not a bare IP — try DNS resolution
        pass

    try:
        for info in socket.getaddrinfo(hostname, None):
            addr = ipaddress.ip_address(info[4][0])
            if (
                addr.is_private
                or addr.is_loopback
                or addr.is_reserved
                or addr.is_link_local
            ):
                return True
    except (socket.gaierror, OSError):
        pass

    return False


def validate_scrape_url(url: str) -> bool:
    """
    Return True if the URL is safe to scrape.
    Rejects:
      - Non-HTTP(S) schemes
      - Private/loopback/link-local IPs
      - Known cloud metadata hostnames
      - URLs without a valid hostname
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return False

    # Scheme check
    if parsed.scheme not in ("http", "https"):
        return False

    hostname = parsed.hostname
    if not hostname:
        return False

    # Blocked hosts
    if hostname.lower() in _BLOCKED_HOSTS:
        logger.warning("SSRF blocked: %s (blocked host)", url)
        return False

    # Private IP check
    if _is_private_ip(hostname):
        logger.warning("SSRF blocked: %s (private/internal IP)", url)
        return False

    return True


class URLValidator:
    """Compatibility wrapper that returns structured validation results."""

    def validate(self, url: str) -> dict:
        valid = validate_scrape_url(url)
        return {
            "valid": valid,
            "reason": None if valid else "blocked_or_invalid_url",
            "url": url,
        }
