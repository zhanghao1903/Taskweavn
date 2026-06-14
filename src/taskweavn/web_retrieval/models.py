"""Small bounded models for external web retrieval results."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal


@dataclass(frozen=True)
class WebSearchRequest:
    query: str
    max_results: int = 5
    include_domains: tuple[str, ...] = ()
    exclude_domains: tuple[str, ...] = ()
    recency: str | None = None


@dataclass(frozen=True)
class WebSearchResult:
    title: str
    url: str
    snippet: str
    published_at: str | None = None
    source: str = "web"


@dataclass(frozen=True)
class WebSearchResponse:
    provider: str
    query: str
    results: tuple[WebSearchResult, ...]
    retrieved_at: datetime
    truncated: bool = False
    warnings: tuple[dict[str, str], ...] = ()


@dataclass(frozen=True)
class WebFetchRequest:
    urls: tuple[str, ...]
    query: str | None = None
    max_chars_per_url: int = 12000
    max_total_chars: int = 24000
    extract_depth: Literal["basic", "advanced"] = "basic"
    response_format: Literal["markdown", "text"] = "markdown"


@dataclass(frozen=True)
class WebFetchResult:
    url: str
    content: str
    title: str | None = None
    content_hash: str | None = None
    chars: int = 0
    truncated: bool = False
    source: str = "web"


@dataclass(frozen=True)
class WebFetchFailedResult:
    url: str
    error_code: str
    message: str


@dataclass(frozen=True)
class WebFetchResponse:
    provider: str
    urls: tuple[str, ...]
    results: tuple[WebFetchResult, ...]
    failed_results: tuple[WebFetchFailedResult, ...]
    retrieved_at: datetime
    truncated: bool = False
    warnings: tuple[dict[str, str], ...] = ()
