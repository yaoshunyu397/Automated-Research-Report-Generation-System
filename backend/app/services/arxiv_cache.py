from __future__ import annotations

from ..services.arxiv_client import ArxivItem
from ..services.cache import TTLCache

SearchResult = tuple[int, list[ArxivItem]]

search_cache: TTLCache[SearchResult] = TTLCache(ttl_seconds=600, max_size=128)


def make_search_cache_key(query: str, max_results: int, start: int, sort_by: str) -> str:
    normalized_query = " ".join(query.strip().lower().split())
    return f"q={normalized_query}|max={max_results}|start={start}|sort={sort_by}"


def get_cached_search(query: str, max_results: int, start: int, sort_by: str) -> SearchResult | None:
    return search_cache.get(make_search_cache_key(query, max_results, start, sort_by))


def set_cached_search(query: str, max_results: int, start: int, sort_by: str, value: SearchResult) -> None:
    search_cache.set(make_search_cache_key(query, max_results, start, sort_by), value)


def get_search_cache_stats() -> dict[str, int]:
    return search_cache.stats()
