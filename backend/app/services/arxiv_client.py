from __future__ import annotations

import asyncio
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Optional

import httpx

from ..settings import settings


ATOM_NS = {"atom": "http://www.w3.org/2005/Atom"}


def _text(el: Optional[ET.Element]) -> str:
    if el is None or el.text is None:
        return ""
    return el.text.strip()


def _first(el: ET.Element, path: str) -> Optional[ET.Element]:
    return el.find(path, ATOM_NS)


def _all(el: ET.Element, path: str) -> list[ET.Element]:
    return el.findall(path, ATOM_NS)


_ARXIV_ID_RE = re.compile(r"arxiv\.org/abs/([^v]+)(v\d+)?$")


def _extract_arxiv_id_from_id_url(id_url: str) -> str:
    """
    arXiv Atom feed <id> is like: http://arxiv.org/abs/2401.12345v2
    We store stable id without version: 2401.12345
    """
    m = _ARXIV_ID_RE.search(id_url.strip())
    if not m:
        return id_url.strip()
    return m.group(1)


@dataclass(frozen=True)
class ArxivItem:
    arxiv_id: str
    title: str
    authors: list[str]
    abstract: str
    pdf_url: str
    published: Optional[str]
    updated: Optional[str]


class ArxivClientError(RuntimeError):
    pass


_request_lock = asyncio.Lock()
_last_request_at = 0.0
_MIN_REQUEST_INTERVAL_SECONDS = 3.0


async def _wait_for_rate_limit() -> None:
    global _last_request_at
    async with _request_lock:
        elapsed = time.monotonic() - _last_request_at
        wait_seconds = _MIN_REQUEST_INTERVAL_SECONDS - elapsed
        if wait_seconds > 0:
            await asyncio.sleep(wait_seconds)
        _last_request_at = time.monotonic()


class ArxivClient:
    BASE_URLS = (
        "https://export.arxiv.org/api/query",
        "https://arxiv.org/api/query",
    )
    MAX_RETRIES = 1

    async def search(self, query: str, max_results: int = 20, start: int = 0, sort_by: str = "submittedDate") -> tuple[int, list[ArxivItem]]:
        normalized_query = query.strip()
        search_query = normalized_query if any(token in normalized_query for token in (":", " AND ", " OR ", "NOT ")) else f"all:{normalized_query}"
        params = {
            "search_query": search_query,
            "start": start,
            "max_results": max_results,
            "sortBy": sort_by,
        }
        last_error = "未知错误"
        proxies = settings.arxiv_proxy.strip() or None
        timeout = httpx.Timeout(15.0, connect=15.0)

        async with httpx.AsyncClient(timeout=timeout, proxy=proxies, follow_redirects=True) as client:
            for base_url in self.BASE_URLS:
                for attempt in range(self.MAX_RETRIES + 1):
                    try:
                        await _wait_for_rate_limit()
                        r = await client.get(base_url, params=params, headers={"User-Agent": "SurveyGen/0.1"})
                        r.raise_for_status()
                        root = ET.fromstring(r.text)
                        return self._parse_response(root)
                    except (httpx.TimeoutException, httpx.NetworkError) as e:
                        last_error = f"{base_url} 网络超时或不可达：{type(e).__name__}"
                        if attempt < self.MAX_RETRIES:
                            await asyncio.sleep(1.5 * (attempt + 1))
                    except httpx.HTTPStatusError as e:
                        last_error = f"{base_url} 返回 HTTP {e.response.status_code}"
                        if e.response.status_code == 429:
                            raise ArxivClientError(f"arXiv 检索失败，已触发请求频率限制。最后错误：{last_error}") from e
                        break
                    except ET.ParseError as e:
                        last_error = f"{base_url} 返回内容不是有效 XML：{e}"
                        break

        raise ArxivClientError(f"arXiv 检索失败，已尝试多个地址。最后错误：{last_error}")

    def _parse_response(self, root: ET.Element) -> tuple[int, list[ArxivItem]]:
        total_el = _first(root, "atom:totalResults") or root.find("{http://a9.com/-/spec/opensearch/1.1/}totalResults")
        total = int(_text(total_el) or "0")

        items: list[ArxivItem] = []
        for entry in _all(root, "atom:entry"):
            id_url = _text(_first(entry, "atom:id"))
            arxiv_id = _extract_arxiv_id_from_id_url(id_url)
            title = _text(_first(entry, "atom:title"))
            abstract = _text(_first(entry, "atom:summary"))
            authors = [_text(a) for a in _all(entry, "atom:author/atom:name")]
            published = _text(_first(entry, "atom:published")) or None
            updated = _text(_first(entry, "atom:updated")) or None

            pdf_url = ""
            for link in _all(entry, "atom:link"):
                if link.attrib.get("title") == "pdf" and "href" in link.attrib:
                    pdf_url = link.attrib["href"]
                    break
            if not pdf_url:
                pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

            items.append(
                ArxivItem(
                    arxiv_id=arxiv_id,
                    title=title,
                    authors=authors,
                    abstract=abstract,
                    pdf_url=pdf_url,
                    published=published,
                    updated=updated,
                )
            )
        return total, items
