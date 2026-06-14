"""Web retrieval provider protocols and sanitized error taxonomy."""

from __future__ import annotations

from typing import Protocol

from taskweavn.web_retrieval.models import (
    WebFetchRequest,
    WebFetchResponse,
    WebSearchRequest,
    WebSearchResponse,
)


class WebSearchProvider(Protocol):
    """Provider-neutral web search contract used by execution tools."""

    provider: str

    def search(self, request: WebSearchRequest) -> WebSearchResponse: ...


class WebFetchProvider(Protocol):
    """Provider-neutral page extraction contract used by execution tools."""

    provider: str

    def fetch(self, request: WebFetchRequest) -> WebFetchResponse: ...


class WebSearchConfigError(RuntimeError):
    """Raised when web search is enabled but cannot be configured."""


class WebSearchProviderError(RuntimeError):
    """Raised when a provider returns an unavailable or invalid response."""


class WebSearchRateLimitError(WebSearchProviderError):
    """Raised when a provider rate limit is hit."""


class WebSearchTimeoutError(WebSearchProviderError):
    """Raised when a provider request times out."""
