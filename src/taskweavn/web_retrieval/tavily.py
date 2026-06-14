"""Tavily-backed implementation of the web search provider contract."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any
from urllib import error
from urllib import request as urlrequest
from urllib.parse import urlsplit

from taskweavn.web_retrieval.models import (
    WebFetchFailedResult,
    WebFetchRequest,
    WebFetchResponse,
    WebFetchResult,
    WebSearchRequest,
    WebSearchResponse,
    WebSearchResult,
)
from taskweavn.web_retrieval.providers import (
    WebSearchConfigError,
    WebSearchProviderError,
    WebSearchRateLimitError,
    WebSearchTimeoutError,
)

_DEFAULT_SEARCH_ENDPOINT = "https://api.tavily.com/search"
_DEFAULT_EXTRACT_ENDPOINT = "https://api.tavily.com/extract"
_DEFAULT_TIMEOUT_SECONDS = 12.0
_MAX_SNIPPET_CHARS = 1000
_MAX_TOTAL_SNIPPET_CHARS = 12000
_MAX_FETCH_URLS = 5
_MAX_FETCH_CHARS_PER_URL = 20000
_MAX_FETCH_TOTAL_CHARS = 40000

Transport = Callable[[str, bytes, Mapping[str, str], float], tuple[int, bytes]]


class TavilyWebSearchProvider:
    """Minimal Tavily basic-search adapter.

    The adapter avoids the Tavily SDK so the packaged sidecar does not need a
    new runtime dependency. Tests can inject a small transport function.
    """

    provider = "tavily"

    def __init__(
        self,
        *,
        api_key: str,
        endpoint: str = _DEFAULT_SEARCH_ENDPOINT,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
        transport: Transport | None = None,
    ) -> None:
        stripped_key = api_key.strip()
        if not stripped_key:
            raise WebSearchConfigError("Tavily API key is required.")
        self._api_key = stripped_key
        self._endpoint = endpoint
        self._timeout_seconds = timeout_seconds
        self._transport = transport or _urllib_transport

    def search(self, search_request: WebSearchRequest) -> WebSearchResponse:
        max_results = _bounded_max_results(search_request.max_results)
        payload = {
            "query": search_request.query.strip(),
            "search_depth": "basic",
            "max_results": max_results,
            "include_domains": list(search_request.include_domains),
            "exclude_domains": list(search_request.exclude_domains),
        }
        if search_request.recency is not None:
            payload["time_range"] = search_request.recency
        raw_payload = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        try:
            status, raw_response = self._transport(
                self._endpoint,
                raw_payload,
                headers,
                self._timeout_seconds,
            )
        except TimeoutError as exc:
            raise WebSearchTimeoutError("Tavily search timed out.") from exc
        except OSError as exc:
            raise WebSearchProviderError("Tavily search request failed.") from exc

        if status == 429:
            raise WebSearchRateLimitError("Tavily rate limit exceeded.")
        if status < 200 or status >= 300:
            raise WebSearchProviderError(f"Tavily search failed with HTTP {status}.")

        try:
            parsed = json.loads(raw_response.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise WebSearchProviderError("Tavily returned malformed JSON.") from exc
        if not isinstance(parsed, dict):
            raise WebSearchProviderError("Tavily returned an invalid response shape.")

        return _normalize_tavily_response(
            query=search_request.query,
            max_results=max_results,
            response=parsed,
        )


class TavilyWebFetchProvider:
    """Minimal Tavily Extract adapter for public page content.

    The adapter intentionally uses urllib instead of the Tavily SDK so the
    packaged sidecar does not need another runtime dependency.
    """

    provider = "tavily"

    def __init__(
        self,
        *,
        api_key: str,
        endpoint: str = _DEFAULT_EXTRACT_ENDPOINT,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
        transport: Transport | None = None,
    ) -> None:
        stripped_key = api_key.strip()
        if not stripped_key:
            raise WebSearchConfigError("Tavily API key is required.")
        self._api_key = stripped_key
        self._endpoint = endpoint
        self._timeout_seconds = timeout_seconds
        self._transport = transport or _urllib_transport

    def fetch(self, fetch_request: WebFetchRequest) -> WebFetchResponse:
        urls = fetch_request.urls[:_MAX_FETCH_URLS]
        max_chars_per_url = _bounded_int(
            fetch_request.max_chars_per_url,
            default=12000,
            minimum=1000,
            maximum=_MAX_FETCH_CHARS_PER_URL,
        )
        max_total_chars = _bounded_int(
            fetch_request.max_total_chars,
            default=24000,
            minimum=1000,
            maximum=_MAX_FETCH_TOTAL_CHARS,
        )
        payload: dict[str, Any] = {
            "urls": list(urls),
            "extract_depth": (
                fetch_request.extract_depth
                if fetch_request.extract_depth in {"basic", "advanced"}
                else "basic"
            ),
            "format": (
                fetch_request.response_format
                if fetch_request.response_format in {"markdown", "text"}
                else "markdown"
            ),
            "include_images": False,
        }
        if fetch_request.query is not None and fetch_request.query.strip():
            payload["query"] = fetch_request.query.strip()[:400]
            payload["chunks_per_source"] = 3
        raw_payload = json.dumps(payload).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        try:
            status, raw_response = self._transport(
                self._endpoint,
                raw_payload,
                headers,
                self._timeout_seconds,
            )
        except TimeoutError as exc:
            raise WebSearchTimeoutError("Tavily extract timed out.") from exc
        except OSError as exc:
            raise WebSearchProviderError("Tavily extract request failed.") from exc

        if status == 429:
            raise WebSearchRateLimitError("Tavily rate limit exceeded.")
        if status < 200 or status >= 300:
            raise WebSearchProviderError(f"Tavily extract failed with HTTP {status}.")

        try:
            parsed = json.loads(raw_response.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise WebSearchProviderError("Tavily returned malformed JSON.") from exc
        if not isinstance(parsed, dict):
            raise WebSearchProviderError("Tavily returned an invalid response shape.")

        return _normalize_tavily_extract_response(
            urls=tuple(urls),
            max_chars_per_url=max_chars_per_url,
            max_total_chars=max_total_chars,
            response=parsed,
        )


def _urllib_transport(
    endpoint: str,
    payload: bytes,
    headers: Mapping[str, str],
    timeout_seconds: float,
) -> tuple[int, bytes]:
    req = urlrequest.Request(
        endpoint,
        data=payload,
        headers=dict(headers),
        method="POST",
    )
    try:
        with urlrequest.urlopen(req, timeout=timeout_seconds) as response:  # noqa: S310
            status = int(getattr(response, "status", response.getcode()))
            return status, response.read()
    except error.HTTPError as exc:
        return int(exc.code), exc.read()
    except TimeoutError as exc:
        raise TimeoutError("Tavily search timed out.") from exc


def _normalize_tavily_response(
    *,
    query: str,
    max_results: int,
    response: Mapping[str, Any],
) -> WebSearchResponse:
    raw_results = response.get("results")
    if not isinstance(raw_results, list):
        raise WebSearchProviderError("Tavily response is missing results.")
    results: list[WebSearchResult] = []
    warnings: list[dict[str, str]] = []
    total_chars = 0
    truncated = False
    for item in raw_results[:max_results]:
        if not isinstance(item, Mapping):
            continue
        title = _bounded_text(item.get("title"), max_chars=300)
        url = _bounded_text(item.get("url"), max_chars=2000)
        snippet = _bounded_text(
            item.get("content", item.get("snippet")),
            max_chars=_MAX_SNIPPET_CHARS,
        )
        if not title or not _is_http_url(url):
            continue
        if total_chars + len(snippet) > _MAX_TOTAL_SNIPPET_CHARS:
            available = max(0, _MAX_TOTAL_SNIPPET_CHARS - total_chars)
            snippet = snippet[:available]
            truncated = True
            warnings.append(
                {
                    "code": "observation.truncated",
                    "message": "web search observation payload was truncated",
                }
            )
        total_chars += len(snippet)
        results.append(
            WebSearchResult(
                title=title,
                url=url,
                snippet=snippet,
                published_at=_optional_text(item.get("published_date"), max_chars=120),
                source="tavily",
            )
        )
        if truncated:
            break
    return WebSearchResponse(
        provider="tavily",
        query=query,
        results=tuple(results),
        retrieved_at=datetime.now(UTC),
        truncated=truncated,
        warnings=tuple(warnings),
    )


def _normalize_tavily_extract_response(
    *,
    urls: tuple[str, ...],
    max_chars_per_url: int,
    max_total_chars: int,
    response: Mapping[str, Any],
) -> WebFetchResponse:
    raw_results = response.get("results")
    if not isinstance(raw_results, list):
        raise WebSearchProviderError("Tavily response is missing results.")
    results: list[WebFetchResult] = []
    warnings: list[dict[str, str]] = []
    total_chars = 0
    truncated = False
    for item in raw_results:
        if not isinstance(item, Mapping):
            continue
        url = _bounded_text(item.get("url"), max_chars=2000)
        if not _is_http_url(url):
            continue
        content = _bounded_text(
            item.get("raw_content", item.get("content")),
            max_chars=max_chars_per_url,
        )
        item_truncated = False
        raw_content = item.get("raw_content", item.get("content"))
        if isinstance(raw_content, str) and len(raw_content.strip()) > len(content):
            item_truncated = True
        if total_chars + len(content) > max_total_chars:
            available = max(0, max_total_chars - total_chars)
            content = content[:available]
            item_truncated = True
        if item_truncated and not truncated:
            warnings.append(
                {
                    "code": "web_fetch.truncated",
                    "message": "web fetch observation payload was truncated",
                }
            )
        truncated = truncated or item_truncated
        total_chars += len(content)
        title = _optional_text(item.get("title"), max_chars=300)
        results.append(
            WebFetchResult(
                url=url,
                title=title,
                content=content,
                content_hash=_content_hash(content),
                chars=len(content),
                truncated=item_truncated,
                source="tavily",
            )
        )
        if total_chars >= max_total_chars:
            break
    failed_results = tuple(_normalize_failed_result(item) for item in _failed_items(response))
    return WebFetchResponse(
        provider="tavily",
        urls=urls,
        results=tuple(results),
        failed_results=failed_results,
        retrieved_at=datetime.now(UTC),
        truncated=truncated,
        warnings=tuple(warnings),
    )


def _normalize_failed_result(item: Mapping[str, Any]) -> WebFetchFailedResult:
    return WebFetchFailedResult(
        url=_bounded_text(item.get("url"), max_chars=2000),
        error_code=_bounded_text(item.get("error"), max_chars=120)
        or _bounded_text(item.get("error_code"), max_chars=120)
        or "provider_error",
        message=_bounded_text(item.get("message"), max_chars=500)
        or "provider could not extract this URL",
    )


def _failed_items(response: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    raw_failed = response.get("failed_results")
    if not isinstance(raw_failed, list):
        return ()
    return tuple(item for item in raw_failed if isinstance(item, Mapping))


def _bounded_max_results(value: int) -> int:
    return min(10, max(1, int(value)))


def _bounded_int(value: int, *, default: int, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return min(maximum, max(minimum, parsed))


def _bounded_text(value: object, *, max_chars: int) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()[:max_chars]


def _optional_text(value: object, *, max_chars: int) -> str | None:
    text = _bounded_text(value, max_chars=max_chars)
    return text or None


def _is_http_url(value: str) -> bool:
    parsed = urlsplit(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _content_hash(content: str) -> str:
    return sha256(content.encode("utf-8")).hexdigest()
