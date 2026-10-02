from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..db import SessionLocal, get_session
from ..models import Paper, PaperAsset, Selection, SelectionSet, Task, User
from ..schemas import CreateTaskRequest, TaskResponse
from ..services.downloader import download_file
from ..services.pdf_extract import extract_pdf_text
from ..services.storage import ensure_dirs, paper_pdf_path, paper_text_path
from ..services.text_clean import clean_text

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _to_task_response(t: Task) -> TaskResponse:
    return TaskResponse(task_id=t.id, selection_set_id=t.selection_set_id, status=t.status, step=t.step, progress=t.progress, message=t.message)


async def _set_task(task_id: int, **fields) -> None:
    async with SessionLocal() as session:
        task = (await session.execute(select(Task).where(Task.id == task_id))).scalars().first()
        if task is None:
            return
        for k, v in fields.items():
            setattr(task, k, v)
        await session.commit()


async def _require_task_owner(task_id: int, user: User, session: AsyncSession) -> Task:
    task = (await session.execute(select(Task).join(SelectionSet, SelectionSet.id == Task.selection_set_id).where(Task.id == task_id, SelectionSet.user_id == user.id).limit(1))).scalars().first()
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


async def _run_download(task_id: int) -> None:
    ensure_dirs(); await _set_task(task_id, status="running", step="download", progress=0, message=None)
    try:
        async with SessionLocal() as session:
            task = (await session.execute(select(Task).where(Task.id == task_id))).scalars().first()
            if task is None:
                return
            rows = (await session.execute(select(Paper).join(Selection, Selection.paper_id == Paper.id).where(Selection.selection_set_id == task.selection_set_id))).scalars().all()
        total = max(len(rows), 1)
        for idx, p in enumerate(rows, start=1):
            out = paper_pdf_path(p.arxiv_id)
            if p.pdf_url:
                await download_file(p.pdf_url, out)
            async with SessionLocal() as session:
                paper = (await session.execute(select(Paper).where(Paper.id == p.id))).scalars().first()
                if paper is None:
                    continue
                asset = (await session.execute(select(PaperAsset).where(PaperAsset.paper_id == paper.id).limit(1))).scalars().first()
                if asset is None:
                    asset = PaperAsset(paper_id=paper.id, pdf_path=str(out)); session.add(asset)
                else:
                    asset.pdf_path = str(out)
                await session.commit()
            await _set_task(task_id, progress=int(idx * 100 / total), message=f"已下载 {idx}/{total}: {p.arxiv_id}")
        await _set_task(task_id, status="completed", progress=100, message="下载完成")
    except Exception as e:
        await _set_task(task_id, status="failed", message=f"下载失败：{type(e).__name__}: {e}")


async def _run_extract(task_id: int) -> None:
    ensure_dirs(); await _set_task(task_id, status="running", step="extract", progress=0, message=None)
    try:
        async with SessionLocal() as session:
            task = (await session.execute(select(Task).where(Task.id == task_id))).scalars().first()
            if task is None:
                return
            rows = (await session.execute(select(Paper).join(Selection, Selection.paper_id == Paper.id).where(Selection.selection_set_id == task.selection_set_id))).scalars().all()
        total = max(len(rows), 1)
        for idx, p in enumerate(rows, start=1):
            pdf_path = paper_pdf_path(p.arxiv_id)
            if not pdf_path.exists():
                raise FileNotFoundError(f"缺少PDF文件：{pdf_path}")
            out = paper_text_path(p.arxiv_id)
            out.write_text(clean_text(extract_pdf_text(pdf_path)), encoding="utf-8")
            async with SessionLocal() as session:
                paper = (await session.execute(select(Paper).where(Paper.id == p.id))).scalars().first()
                if paper is None:
                    continue
                asset = (await session.execute(select(PaperAsset).where(PaperAsset.paper_id == paper.id).limit(1))).scalars().first()
                if asset is None:
                    asset = PaperAsset(paper_id=paper.id, extracted_text_path=str(out)); session.add(asset)
                else:
                    asset.extracted_text_path = str(out)
                await session.commit()
            await _set_task(task_id, progress=int(idx * 100 / total), message=f"已解析 {idx}/{total}: {p.arxiv_id}")
        await _set_task(task_id, status="completed", progress=100, message="解析完成")
    except Exception as e:
        await _set_task(task_id, status="failed", message=f"解析失败：{type(e).__name__}: {e}")


@router.post("/create", response_model=TaskResponse)
async def create_task(payload: CreateTaskRequest, session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)):
    exists = (await session.execute(select(SelectionSet.id).where(SelectionSet.id == payload.selection_set_id, SelectionSet.user_id == user.id).limit(1))).scalars().first()
    if exists is None:
        raise HTTPException(status_code=404, detail="Selection set not found")
    task = Task(selection_set_id=payload.selection_set_id, status="pending", step="created", progress=0)
    session.add(task); await session.commit(); await session.refresh(task)
    return _to_task_response(task)


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(task_id: int, session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)):
    return _to_task_response(await _require_task_owner(task_id, user, session))


@router.post("/{task_id}/download", response_model=TaskResponse)
async def run_download(task_id: int, session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)):
    task = await _require_task_owner(task_id, user, session)
    asyncio.create_task(_run_download(task_id))
    return _to_task_response(task)


@router.post("/{task_id}/extract", response_model=TaskResponse)
async def run_extract(task_id: int, session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)):
    task = await _require_task_owner(task_id, user, session)
    asyncio.create_task(_run_extract(task_id))
    return _to_task_response(task)
