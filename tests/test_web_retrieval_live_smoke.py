"""Opt-in live Tavily smoke for Product 1.1 web retrieval beta hardening."""

from __future__ import annotations

import os

import pytest

from taskweavn.web_retrieval import (
    TavilyWebFetchProvider,
    TavilyWebSearchProvider,
    WebFetchRequest,
    WebSearchRequest,
)


def test_live_tavily_search_and_extract_smoke() -> None:
    if os.environ.get("PLATO_RUN_LIVE_WEB_RETRIEVAL_SMOKE") != "1":
        pytest.skip("set PLATO_RUN_LIVE_WEB_RETRIEVAL_SMOKE=1 to run live smoke")
    api_key = os.environ.get("TAVILY_API_KEY", "").strip()
    if not api_key:
        pytest.skip("TAVILY_API_KEY is required for live Tavily smoke")

    search_provider = TavilyWebSearchProvider(api_key=api_key)
    fetch_provider = TavilyWebFetchProvider(api_key=api_key)

    search = search_provider.search(
        WebSearchRequest(
            query=os.environ.get(
                "PLATO_LIVE_WEB_RETRIEVAL_QUERY",
                "site:docs.tavily.com Tavily Search API",
            ),
            include_domains=("docs.tavily.com",),
            max_results=3,
        )
    )
    assert search.provider == "tavily"
    assert search.results
    first_url = search.results[0].url
    assert first_url.startswith("https://")

    fetched = fetch_provider.fetch(
        WebFetchRequest(
            urls=(first_url,),
            max_chars_per_url=4000,
            max_total_chars=4000,
        )
    )
    assert fetched.provider == "tavily"
    assert fetched.results
    assert fetched.results[0].url == first_url
    assert fetched.results[0].content.strip()
    assert fetched.results[0].chars <= 4000
