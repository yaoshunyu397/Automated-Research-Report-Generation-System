from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..db import get_session
from ..models import Report, ReportSection, SelectionSet, User
from ..services.exporter import FlatSection, export_docx, export_pdf, render_markdown
from ..services.storage import REPORTS_DIR, ensure_dirs

router = APIRouter(prefix="/api/reports", tags=["export"])


@router.post("/{report_id}/export")
async def export_report(
    report_id: int,
    format: str = Query(default="md", pattern="^(md|docx|pdf)$"),
    session: AsyncSession = Depends(get_session),
):
    ensure_dirs()
    report = (await session.execute(select(Report).where(Report.id == report_id))).scalars().first()
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")

    secs = (
        await session.execute(
            select(ReportSection).where(ReportSection.report_id == report_id)
        )
    ).scalars().all()

    flat = [
        FlatSection(
            id=s.id,
            parent_id=s.parent_id,
            order_index=s.order_index,
            title=s.title,
            content_md=s.content_md,
        )
        for s in secs
    ]

    if format == "md":
        content = render_markdown(flat)
        out = REPORTS_DIR / f"report_{report_id}.md"
        out.write_text(content, encoding="utf-8")
    elif format == "docx":
        out = REPORTS_DIR / f"report_{report_id}.docx"
        export_docx(report.title, flat, out)
    else:
        out = REPORTS_DIR / f"report_{report_id}.pdf"
        export_pdf(report.title, flat, out)
    return {"ok": True, "format": format, "path": str(out)}


@router.get("/{report_id}/export/download")
async def download_export(
    report_id: int,
    format: str = Query(default="md", pattern="^(md|docx|pdf)$"),
    session: AsyncSession = Depends(get_session),
):
    ensure_dirs()
    report = (await session.execute(select(Report).where(Report.id == report_id))).scalars().first()
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")

    filename = f"report_{report_id}.{format}"
    path = REPORTS_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Export file not found. Run export first.")
    media_type = {"md": "text/markdown", "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "pdf": "application/pdf"}[format]
    return FileResponse(path=path, media_type=media_type, filename=filename)

