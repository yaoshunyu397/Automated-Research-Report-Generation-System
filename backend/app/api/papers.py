from __future__ import annotations

from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..db import get_session
from ..models import Paper, PaperAsset, PaperTranslation, Report, ReportSection, Selection, SelectionSet, Task, User
from ..schemas import ArxivSearchItem, SelectPapersRequest, SelectionSetResponse
from ..services.storage import paper_pdf_path, paper_translation_path

router = APIRouter(prefix="/api/papers", tags=["papers"])


async def _ensure_selection_set_columns(session: AsyncSession) -> None:
    result = await session.execute(text("PRAGMA table_info(selection_sets)"))
    columns = {row[1] for row in result.fetchall()}
    changed = False
    if "query" not in columns:
        await session.execute(text("ALTER TABLE selection_sets ADD COLUMN query TEXT")); changed = True
    if "user_id" not in columns:
        await session.execute(text("ALTER TABLE selection_sets ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE CASCADE")); changed = True
    if changed:
        await session.commit()


async def _require_set(selection_set_id: int, user: User, session: AsyncSession) -> SelectionSet:
    await _ensure_selection_set_columns(session)
    row = (await session.execute(select(SelectionSet).where(SelectionSet.id == selection_set_id, SelectionSet.user_id == user.id).limit(1))).scalars().first()
    if row is None:
        raise HTTPException(status_code=404, detail="Selection set not found")
    return row


def _to_paper_fields(item: ArxivSearchItem) -> dict:
    return {"arxiv_id": item.arxiv_id, "title": item.title, "authors": ", ".join(item.authors), "abstract": item.abstract, "pdf_url": item.pdf_url, "published": item.published, "updated": item.updated}


def _existing_file(path_str: str | None, fallback: Path | None = None) -> Path | None:
    for path in [*( [Path(path_str)] if path_str else []), *( [fallback] if fallback is not None else [])]:
        if path.exists() and path.is_file():
            return path
    return None


async def _get_paper(arxiv_id: str, session: AsyncSession) -> Paper:
    paper = (await session.execute(select(Paper).where(Paper.arxiv_id == arxiv_id).limit(1))).scalars().first()
    if paper is None:
        raise HTTPException(status_code=404, detail="Paper not found")
    return paper


async def _require_user_has_paper(paper: Paper, user: User, session: AsyncSession) -> None:
    exists = (await session.execute(select(Selection.id).join(SelectionSet, SelectionSet.id == Selection.selection_set_id).where(Selection.paper_id == paper.id, SelectionSet.user_id == user.id).limit(1))).scalars().first()
    if exists is None:
        raise HTTPException(status_code=404, detail="Paper not found")


@router.post("/select", response_model=SelectionSetResponse)
async def select_papers(payload: SelectPapersRequest, session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)):
    await _ensure_selection_set_columns(session)
    selection_set = None
    if payload.name:
        selection_set = (await session.execute(select(SelectionSet).where(SelectionSet.name == payload.name, SelectionSet.user_id == user.id).limit(1))).scalars().first()
    if selection_set is None:
        selection_set = SelectionSet(name=payload.name or "default", query=(payload.query or "").strip() or None, user_id=user.id)
        session.add(selection_set); await session.flush()
    elif payload.query and payload.query.strip():
        selection_set.query = payload.query.strip()

    items = payload.items or [ArxivSearchItem(arxiv_id=arxiv_id, title="", authors=[], abstract="", pdf_url="") for arxiv_id in payload.arxiv_ids]
    for item in items:
        paper = (await session.execute(select(Paper).where(Paper.arxiv_id == item.arxiv_id).limit(1))).scalars().first()
        if paper is None:
            paper = Paper(**_to_paper_fields(item)); session.add(paper); await session.flush()
        else:
            for k, v in _to_paper_fields(item).items():
                if v is not None and not (isinstance(v, str) and v.strip() == ""):
                    setattr(paper, k, v)
        exists = (await session.execute(select(Selection).where(Selection.selection_set_id == selection_set.id, Selection.paper_id == paper.id))).scalars().first()
        if exists is None:
            session.add(Selection(selection_set_id=selection_set.id, paper_id=paper.id))

    await session.commit()
    count = (await session.execute(select(Selection).where(Selection.selection_set_id == selection_set.id))).scalars().all()
    return SelectionSetResponse(selection_set_id=selection_set.id, name=selection_set.name, count=len(count), query=selection_set.query)


@router.get("/selection_sets")
async def list_selection_sets(session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)):
    await _ensure_selection_set_columns(session)
    sets = (await session.execute(select(SelectionSet).where(SelectionSet.user_id == user.id).order_by(SelectionSet.created_at.desc(), SelectionSet.id.desc()))).scalars().all()
    result = []
    for s in sets:
        count = (await session.execute(select(Selection).where(Selection.selection_set_id == s.id))).scalars().all()
        result.append({"selection_set_id": s.id, "name": s.name, "query": s.query, "count": len(count), "created_at": s.created_at.isoformat() if s.created_at else None})
    return result


@router.get("/selection_set/{selection_set_id}")
async def get_selection_set_papers(selection_set_id: int, session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)):
    await _require_set(selection_set_id, user, session)
    papers = (await session.execute(select(Paper).join(Selection, Selection.paper_id == Paper.id).where(Selection.selection_set_id == selection_set_id).order_by(Paper.id.desc()))).scalars().all()
    paper_ids = [p.id for p in papers]
    translations = {tr.paper_id: tr for tr in (await session.execute(select(PaperTranslation).where(PaperTranslation.paper_id.in_(paper_ids)))).scalars().all()} if paper_ids else {}
    assets = {a.paper_id: a for a in (await session.execute(select(PaperAsset).where(PaperAsset.paper_id.in_(paper_ids)))).scalars().all()} if paper_ids else {}
    result = []
    for p in papers:
        tr, asset = translations.get(p.id), assets.get(p.id)
        pdf_file = _existing_file(asset.pdf_path if asset else None, paper_pdf_path(p.arxiv_id))
        text_file = _existing_file(asset.extracted_text_path if asset else None)
        translation_file = _existing_file(None, paper_translation_path(p.arxiv_id))
        result.append({"arxiv_id": p.arxiv_id, "title": p.title, "authors": p.authors.split(", ") if p.authors else [], "abstract": p.abstract, "pdf_url": p.pdf_url, "published": p.published, "updated": p.updated, "title_zh": tr.title_zh if tr else None, "abstract_zh": tr.abstract_zh if tr else None, "has_pdf": pdf_file is not None, "has_parsed_text": text_file is not None, "has_translation": translation_file is not None, "local_pdf_url": f"/api/papers/{p.arxiv_id}/pdf" if pdf_file else None, "translation_url": f"/api/papers/{p.arxiv_id}/translation_file" if translation_file else None})
    return result


@router.get("/{arxiv_id}/pdf")
async def view_paper_pdf(arxiv_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)):
    paper = await _get_paper(arxiv_id, session); await _require_user_has_paper(paper, user, session)
    asset = (await session.execute(select(PaperAsset).where(PaperAsset.paper_id == paper.id).limit(1))).scalars().first()
    path = _existing_file(asset.pdf_path if asset else None, paper_pdf_path(paper.arxiv_id))
    if path is None:
        raise HTTPException(status_code=404, detail="PDF file not found")
    return FileResponse(path, media_type="application/pdf", filename=f"{paper.arxiv_id}.pdf", headers={"Content-Disposition": f'inline; filename="{paper.arxiv_id}.pdf"'})


@router.get("/{arxiv_id}/translation_file")
async def view_paper_translation_file(arxiv_id: str, session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)):
    paper = await _get_paper(arxiv_id, session); await _require_user_has_paper(paper, user, session)
    path = _existing_file(None, paper_translation_path(paper.arxiv_id))
    if path is None:
        raise HTTPException(status_code=404, detail="Translation file not found")
    return PlainTextResponse(path.read_text(encoding="utf-8"), media_type="text/plain; charset=utf-8")


@router.delete("/selection_set/{selection_set_id}")
async def delete_selection_set(selection_set_id: int, session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)):
    await _require_set(selection_set_id, user, session)
    report_ids = (await session.execute(select(Report.id).where(Report.selection_set_id == selection_set_id))).scalars().all()
    if report_ids:
        await session.execute(delete(ReportSection).where(ReportSection.report_id.in_(report_ids)))
        await session.execute(delete(Report).where(Report.id.in_(report_ids)))
    await session.execute(delete(Task).where(Task.selection_set_id == selection_set_id))
    await session.execute(delete(Selection).where(Selection.selection_set_id == selection_set_id))
    await session.execute(delete(SelectionSet).where(SelectionSet.id == selection_set_id))
    await session.commit()
    return {"ok": True, "selection_set_id": selection_set_id}


@router.get("/selection_set/{selection_set_id}/statuses")
async def get_selection_statuses(selection_set_id: int, session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)):
    await _require_set(selection_set_id, user, session)
    papers = (await session.execute(select(Paper).join(Selection, Selection.paper_id == Paper.id).where(Selection.selection_set_id == selection_set_id))).scalars().all()
    result = []
    for p in papers:
        asset = (await session.execute(select(PaperAsset).where(PaperAsset.paper_id == p.id).limit(1))).scalars().first()
        translation = (await session.execute(select(PaperTranslation).where(PaperTranslation.paper_id == p.id).limit(1))).scalars().first()
        pdf_file = _existing_file(asset.pdf_path if asset else None, paper_pdf_path(p.arxiv_id))
        text_file = _existing_file(asset.extracted_text_path if asset else None)
        translation_file = _existing_file(None, paper_translation_path(p.arxiv_id))
        result.append({"arxiv_id": p.arxiv_id, "downloaded": pdf_file is not None, "parsed": text_file is not None, "translated": bool(translation and (translation.title_zh or translation.abstract_zh)) or translation_file is not None, "local_pdf_url": f"/api/papers/{p.arxiv_id}/pdf" if pdf_file else None, "translation_url": f"/api/papers/{p.arxiv_id}/translation_file" if translation_file else None})
    return result
