"""URL policy for public web-fetch targets."""

from __future__ import annotations

from ipaddress import ip_address
from urllib.parse import urlsplit

_MAX_URL_LENGTH = 2048


class WebFetchUrlPolicyError(ValueError):
    """Raised when a fetch URL is outside the public-web policy."""


def normalize_public_fetch_urls(
    urls: tuple[str, ...],
    *,
    max_urls: int = 5,
) -> tuple[str, ...]:
    """Validate and normalize URLs before they reach a provider.

    V1 fetch is intentionally public-web only. It rejects local files,
    loopback/private/link-local IPs, localhost-style hostnames, and custom
    schemes so a model cannot turn web_fetch into an SSRF primitive.
    """

    bounded_max = min(5, max(1, int(max_urls)))
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in urls:
        candidate = _normalize_one(raw)
        if candidate in seen:
            continue
        normalized.append(candidate)
        seen.add(candidate)
        if len(normalized) >= bounded_max:
            break
    if not normalized:
        raise WebFetchUrlPolicyError("at least one public http(s) URL is required")
    return tuple(normalized)


def _normalize_one(raw_url: str) -> str:
    if not isinstance(raw_url, str) or not raw_url.strip():
        raise WebFetchUrlPolicyError("fetch URL must not be empty")
    value = raw_url.strip()
    if len(value) > _MAX_URL_LENGTH:
        raise WebFetchUrlPolicyError("fetch URL is too long")
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"}:
        raise WebFetchUrlPolicyError("fetch URL must use http or https")
    if parsed.username or parsed.password:
        raise WebFetchUrlPolicyError("fetch URL must not include credentials")
    host = parsed.hostname
    if host is None or not host.strip():
        raise WebFetchUrlPolicyError("fetch URL must include a host")
    _validate_public_host(host)
    return parsed._replace(fragment="").geturl()


def _validate_public_host(host: str) -> None:
    normalized = host.strip().lower().rstrip(".")
    if normalized in {"localhost", "0", "0.0.0.0"}:
        raise WebFetchUrlPolicyError("fetch URL host is not public")
    if normalized.endswith((".localhost", ".local")):
        raise WebFetchUrlPolicyError("fetch URL host is not public")
    try:
        ip = ip_address(normalized.strip("[]"))
    except ValueError:
        return
    if not ip.is_global:
        raise WebFetchUrlPolicyError("fetch URL IP address is not public")
