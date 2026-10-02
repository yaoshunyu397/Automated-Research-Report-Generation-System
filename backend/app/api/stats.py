from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..db import get_session
from ..models import Paper, PaperAsset, PaperTranslation, Report, ReportSection, SelectionSet, Task, User
from ..services.arxiv_cache import get_search_cache_stats

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/overview")
async def stats_overview(session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)):
    selection_set_count = await session.scalar(
        select(func.count(SelectionSet.id)).where(SelectionSet.user_id == user.id)
    )
    report_count = await session.scalar(
        select(func.count(Report.id))
        .join(SelectionSet, SelectionSet.id == Report.selection_set_id)
        .where(SelectionSet.user_id == user.id)
    )
    task_count = await session.scalar(
        select(func.count(Task.id))
        .join(SelectionSet, SelectionSet.id == Task.selection_set_id)
        .where(SelectionSet.user_id == user.id)
    )
    paper_count = await session.scalar(select(func.count(Paper.id)))
    downloaded_count = await session.scalar(
        select(func.count(PaperAsset.id)).where(PaperAsset.pdf_path.is_not(None))
    )
    parsed_count = await session.scalar(
        select(func.count(PaperAsset.id)).where(PaperAsset.extracted_text_path.is_not(None))
    )
    translated_count = await session.scalar(select(func.count(PaperTranslation.id)))
    report_section_count = await session.scalar(
        select(func.count(ReportSection.id))
        .join(Report, Report.id == ReportSection.report_id)
        .join(SelectionSet, SelectionSet.id == Report.selection_set_id)
        .where(SelectionSet.user_id == user.id)
    )
    filled_section_count = await session.scalar(
        select(func.count(ReportSection.id))
        .join(Report, Report.id == ReportSection.report_id)
        .join(SelectionSet, SelectionSet.id == Report.selection_set_id)
        .where(SelectionSet.user_id == user.id, ReportSection.content_md != "")
    )

    return {
        "selection_sets": selection_set_count or 0,
        "reports": report_count or 0,
        "tasks": task_count or 0,
        "papers": paper_count or 0,
        "downloaded_papers": downloaded_count or 0,
        "parsed_papers": parsed_count or 0,
        "translated_papers": translated_count or 0,
        "report_sections": report_section_count or 0,
        "filled_report_sections": filled_section_count or 0,
        "search_cache": get_search_cache_stats(),
    }
