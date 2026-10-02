from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..db import get_session
from ..models import Paper, PaperAsset, PaperTranslation, Selection, SelectionSet, User
from ..schemas import ArxivSearchItem
from ..services.storage import ensure_dirs, paper_translation_path
from ..services.translator import TranslationError, translate_long_text, translate_texts

router = APIRouter(prefix="/api/translate", tags=["translate"])

SUMMARY_BATCH_SIZE = 10
FULL_TEXT_CONCURRENCY = 5


def _read_extracted_text(path_str: str | None) -> str:
    if not path_str:
        return ""
    path = Path(path_str)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


async def _translate_summary(title: str, abstract: str) -> tuple[str, str]:
    translated = await translate_texts([title, abstract])
    return translated[0].strip(), translated[1].strip()


async def _translate_summary_batch(items: list[dict[str, str]]) -> dict[str, dict[str, str | None]]:
    if not items:
        return {}

    texts: list[str] = []
    mapping: list[tuple[str, str]] = []
    for item in items:
        arxiv_id = item["arxiv_id"]
        texts.append(item.get("title", ""))
        mapping.append((arxiv_id, "title_zh"))
        texts.append(item.get("abstract", ""))
        mapping.append((arxiv_id, "abstract_zh"))

    translated_texts = await translate_texts(texts)
    result: dict[str, dict[str, str | None]] = {}
    for translated, (arxiv_id, field) in zip(translated_texts, mapping):
        result.setdefault(arxiv_id, {"title_zh": None, "abstract_zh": None})
        result[arxiv_id][field] = translated.strip() or None
    return result


async def _translate_summaries_in_batches(items: list[dict[str, str]]) -> dict[str, dict[str, str | None]]:
    translations: dict[str, dict[str, str | None]] = {}
    for start in range(0, len(items), SUMMARY_BATCH_SIZE):
        batch = items[start:start + SUMMARY_BATCH_SIZE]
        translations.update(await _translate_summary_batch(batch))
    return translations


async def _translate_full_text(title: str, text: str) -> str:
    return await translate_long_text(text)


@router.post("/summaries")
async def translate_summaries(items: list[ArxivSearchItem], user: User = Depends(get_current_user)):
    summary_items = [
        {"arxiv_id": item.arxiv_id, "title": item.title, "abstract": item.abstract}
        for item in items[:50]
    ]
    try:
        translations = await _translate_summaries_in_batches(summary_items)
    except TranslationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True, "translated": len(translations), "translations": translations}


@router.post("/selection_set/{selection_set_id}")
async def translate_selection_set(selection_set_id: int, session: AsyncSession = Depends(get_session)):
    papers = (
        await session.execute(
            select(Paper).join(Selection, Selection.paper_id == Paper.id).where(Selection.selection_set_id == selection_set_id)
        )
    ).scalars().all()
    if not papers:
        raise HTTPException(status_code=404, detail="No papers in selection set")

    paper_ids = [paper.id for paper in papers]
    assets = {
        asset.paper_id: asset
        for asset in (
            await session.execute(select(PaperAsset).where(PaperAsset.paper_id.in_(paper_ids)))
        ).scalars().all()
    } if paper_ids else {}
    existing_translations = {
        tr.paper_id: tr
        for tr in (
            await session.execute(select(PaperTranslation).where(PaperTranslation.paper_id.in_(paper_ids)))
        ).scalars().all()
    } if paper_ids else {}

    candidates: list[tuple[Paper, str]] = []
    skipped: list[str] = []
    already_translated: list[str] = []
    translations: dict[str, dict[str, str | None]] = {}
    for paper in papers:
        existing_translation_file = paper_translation_path(paper.arxiv_id)
        existing_translation = existing_translations.get(paper.id)
        if existing_translation_file.exists() or (existing_translation and (existing_translation.title_zh or existing_translation.abstract_zh)):
            already_translated.append(paper.arxiv_id)
            translations[paper.arxiv_id] = {
                "title_zh": existing_translation.title_zh if existing_translation else None,
                "abstract_zh": existing_translation.abstract_zh if existing_translation else None,
            }
            continue

        asset = assets.get(paper.id)
        full_text = _read_extracted_text(asset.extracted_text_path if asset else None)
        if not full_text.strip():
            skipped.append(paper.arxiv_id)
            continue
        candidates.append((paper, full_text))

    if not candidates:
        return {
            "ok": True,
            "translated": 0,
            "saved_files": [],
            "skipped": skipped,
            "already_translated": already_translated,
            "translations": translations,
        }

    summary_items = [
        {"arxiv_id": paper.arxiv_id, "title": paper.title, "abstract": paper.abstract}
        for paper, _ in candidates
    ]
    try:
        summary_translations = await _translate_summaries_in_batches(summary_items)
    except TranslationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    semaphore = asyncio.Semaphore(FULL_TEXT_CONCURRENCY)

    async def translate_one(paper: Paper, full_text: str) -> tuple[Paper, str]:
        async with semaphore:
            return paper, await _translate_full_text(paper.title, full_text)

    try:
        full_text_results = await asyncio.gather(*(translate_one(paper, full_text) for paper, full_text in candidates))
    except TranslationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    ensure_dirs()
    saved_files: list[str] = []

    for paper, full_text_zh in full_text_results:
        summary = summary_translations.get(paper.arxiv_id, {})
        title_zh = summary.get("title_zh") or ""
        abstract_zh = summary.get("abstract_zh") or ""

        tr = (
            await session.execute(select(PaperTranslation).where(PaperTranslation.paper_id == paper.id).limit(1))
        ).scalars().first()
        if tr is None:
            tr = PaperTranslation(paper_id=paper.id, title_zh=title_zh, abstract_zh=abstract_zh)
            session.add(tr)
        else:
            tr.title_zh = title_zh
            tr.abstract_zh = abstract_zh

        output = (
            f"# {title_zh or paper.title}\n\n"
            f"- arXiv ID: {paper.arxiv_id}\n"
            f"- 原文标题: {paper.title}\n"
            f"- 作者: {paper.authors}\n\n"
            f"## 中文摘要\n\n{abstract_zh or '（无翻译内容）'}\n\n"
            f"## 全文中文翻译\n\n{full_text_zh or '（正文翻译为空）'}\n\n"
            f"## 英文摘要\n\n{paper.abstract or '（无原文摘要）'}\n"
        )
        out_path = paper_translation_path(paper.arxiv_id)
        out_path.write_text(output, encoding="utf-8")
        saved_files.append(str(out_path))
        translations[paper.arxiv_id] = {"title_zh": title_zh or None, "abstract_zh": abstract_zh or None}

    await session.commit()
    return {
        "ok": True,
        "translated": len(full_text_results),
        "saved_files": saved_files,
        "skipped": skipped,
        "already_translated": already_translated,
        "translations": translations,
    }


@router.get("/{arxiv_id}")
async def get_translation(arxiv_id: str, session: AsyncSession = Depends(get_session)):
    paper = (
        await session.execute(select(Paper).where(Paper.arxiv_id == arxiv_id).limit(1))
    ).scalars().first()
    if paper is None:
        raise HTTPException(status_code=404, detail="Paper not found")

    tr = (
        await session.execute(select(PaperTranslation).where(PaperTranslation.paper_id == paper.id).limit(1))
    ).scalars().first()

    if tr is None:
        return {"title_zh": None, "abstract_zh": None}

    return {"title_zh": tr.title_zh, "abstract_zh": tr.abstract_zh}
