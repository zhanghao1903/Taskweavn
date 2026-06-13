"""Small bounded models for external web search results."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


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
