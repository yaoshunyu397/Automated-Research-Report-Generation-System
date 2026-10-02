from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..schemas import ArxivSearchItem, ArxivSearchResponse
from ..services.arxiv_cache import get_cached_search, set_cached_search
from ..services.arxiv_client import ArxivClient, ArxivClientError

router = APIRouter(prefix="/api/arxiv", tags=["arxiv"])


def _split_keywords(value: str | None) -> list[str]:
    if not value:
        return []
    normalized = value.replace("，", ",").replace(";", ",")
    return [item.strip() for item in normalized.split(",") if item.strip()]


def _term_query(keyword: str) -> str:
    escaped = keyword.replace('"', "")
    return f'all:"{escaped}"' if " " in escaped else f"all:{escaped}"


def _build_advanced_query(q: str, any_keywords: str | None, year_from: int | None, year_to: int | None) -> str:
    parts = [_term_query(q.strip())]
    any_terms = _split_keywords(any_keywords)
    if any_terms:
        parts.append("(" + " OR ".join(_term_query(item) for item in any_terms) + ")")
    if year_from or year_to:
        start_year = year_from or 1991
        end_year = year_to or 2099
        parts.append(f"submittedDate:[{start_year}01010000 TO {end_year}12312359]")
    return " AND ".join(parts)


@router.get("/search", response_model=ArxivSearchResponse)
async def search_arxiv(
    q: str = Query(min_length=1),
    max_results: int = Query(default=20, ge=1, le=100),
    start: int = Query(default=0, ge=0),
    sort_by: str = Query(default="submittedDate", pattern="^(relevance|lastUpdatedDate|submittedDate)$"),
    year_from: int | None = Query(default=None, ge=1991, le=2100),
    year_to: int | None = Query(default=None, ge=1991, le=2100),
    any_keywords: str | None = Query(default=None),
):
    effective_query = _build_advanced_query(q, any_keywords, year_from, year_to)
    cached = get_cached_search(effective_query, max_results, start, sort_by)
    if cached is not None:
        total, items = cached
    else:
        client = ArxivClient()
        try:
            total, items = await client.search(query=effective_query, max_results=max_results, start=start, sort_by=sort_by)
            set_cached_search(effective_query, max_results, start, sort_by, (total, items))
        except ArxivClientError as e:
            message = str(e)
            lowered = message.lower()
            if "http 429" in lowered or "rate" in lowered:
                raise HTTPException(status_code=429, detail="arXiv 请求过于频繁，请稍后再试") from e
            if "网络超时或不可达" in message or "Timeout" in message or "timed out" in lowered:
                raise HTTPException(status_code=504, detail="arXiv 请求超时，请稍后重试") from e
            raise HTTPException(status_code=502, detail="arXiv 当前暂时不可用，请稍后重试") from e

    return ArxivSearchResponse(
        query=q,
        total=total,
        items=[
            ArxivSearchItem(
                arxiv_id=i.arxiv_id,
                title=i.title,
                authors=i.authors,
                abstract=i.abstract,
                pdf_url=i.pdf_url,
                published=i.published,
                updated=i.updated,
            )
            for i in items
        ],
    )
