from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import get_current_user
from ..db import get_session
from ..models import Paper, PaperAsset, PaperTranslation, Report, ReportSection, Selection, SelectionSet, User
from ..schemas import CreateTaskRequest
from ..services.llm import LLMError, chat_complete_json, chat_complete_text
from ..services.storage import REPORTS_DIR

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _raise_db_http_error(exc: Exception, action: str) -> None:
    message = str(exc).lower()
    if "database is locked" in message:
        raise HTTPException(status_code=503, detail=f"{action}失败：数据库当前繁忙，请稍后重试") from exc
    raise HTTPException(status_code=500, detail=f"{action}失败") from exc


async def _require_selection_set_owner(selection_set_id: int, user: User, session: AsyncSession) -> None:
    exists = (await session.execute(select(SelectionSet.id).where(SelectionSet.id == selection_set_id, SelectionSet.user_id == user.id).limit(1))).scalars().first()
    if exists is None:
        raise HTTPException(status_code=404, detail="Selection set not found")


async def _require_report_owner(report_id: int, user: User, session: AsyncSession) -> Report:
    report = (await session.execute(select(Report).join(SelectionSet, SelectionSet.id == Report.selection_set_id).where(Report.id == report_id, SelectionSet.user_id == user.id).limit(1))).scalars().first()
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@router.post("/create")
async def create_report(payload: CreateTaskRequest, session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)):
    await _require_selection_set_owner(payload.selection_set_id, user, session)

    r = Report(selection_set_id=payload.selection_set_id, title="调研报告")
    session.add(r)
    try:
        await session.commit()
        await session.refresh(r)
    except (OperationalError, IntegrityError) as exc:
        await session.rollback()
        _raise_db_http_error(exc, "创建报告")
    return {"report_id": r.id, "selection_set_id": r.selection_set_id, "title": r.title}


@router.get("/selection_set/{selection_set_id}")
async def list_reports_by_selection_set(selection_set_id: int, session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)):
    await _require_selection_set_owner(selection_set_id, user, session)

    reports = (
        await session.execute(
            select(Report)
            .where(Report.selection_set_id == selection_set_id)
            .order_by(Report.updated_at.desc(), Report.id.desc())
        )
    ).scalars().all()

    result: list[dict] = []
    for report in reports:
        sections = (
            await session.execute(select(ReportSection).where(ReportSection.report_id == report.id))
        ).scalars().all()
        filled_count = sum(1 for section in sections if section.content_md.strip())
        result.append(
            {
                "report_id": report.id,
                "selection_set_id": report.selection_set_id,
                "title": report.title,
                "section_count": len(sections),
                "filled_section_count": filled_count,
                "created_at": report.created_at.isoformat() if report.created_at else None,
                "updated_at": report.updated_at.isoformat() if report.updated_at else None,
            }
        )
    return result


@router.delete("/{report_id}")
async def delete_report(report_id: int, session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)):
    report = await _require_report_owner(report_id, user, session)
    selection_set_id = report.selection_set_id
    try:
        await session.execute(delete(ReportSection).where(ReportSection.report_id == report_id))
        await session.execute(delete(Report).where(Report.id == report_id))
        await session.commit()
    except (OperationalError, IntegrityError) as exc:
        await session.rollback()
        _raise_db_http_error(exc, "删除报告")

    deleted_files: list[str] = []
    for ext in ("md", "docx", "pdf"):
        path = REPORTS_DIR / f"report_{report_id}.{ext}"
        if path.exists() and path.is_file():
            path.unlink()
            deleted_files.append(str(path))

    return {"ok": True, "report_id": report_id, "selection_set_id": selection_set_id, "deleted_files": deleted_files}


def _fallback_outline() -> list[dict]:
    return [
        {"title": "引言与研究背景", "children": []},
        {"title": "相关工作综述", "children": []},
        {"title": "方法与技术路线分类", "children": []},
        {"title": "代表性论文精读", "children": []},
        {"title": "挑战与未来趋势", "children": []},
        {"title": "总结", "children": []},
        {"title": "参考文献", "children": []},
    ]


def _fallback_outline_templates() -> list[dict]:
    return [
        {
            "name": "经典综述型模板",
            "description": "适合大多数技术主题，按背景、相关工作、方法分类、代表论文和趋势展开。",
            "outline": _fallback_outline(),
        },
        {
            "name": "技术路线对比型模板",
            "description": "适合对比不同方法流派，突出技术路线、实验指标和优缺点分析。",
            "outline": [
                {"title": "研究问题与应用背景", "children": []},
                {"title": "技术路线总览", "children": [
                    {"title": "主流方法分类", "children": []},
                    {"title": "关键模块与设计差异", "children": []},
                ]},
                {"title": "代表性论文对比", "children": []},
                {"title": "实验设置与评价指标", "children": []},
                {"title": "优势、局限与适用场景", "children": []},
                {"title": "未来研究方向", "children": []},
                {"title": "参考文献", "children": []},
            ],
        },
        {
            "name": "问题驱动型模板",
            "description": "适合围绕核心挑战组织内容，强调问题定义、解决方案和开放挑战。",
            "outline": [
                {"title": "调研范围与核心问题", "children": []},
                {"title": "领域发展脉络", "children": []},
                {"title": "关键挑战一：数据与任务定义", "children": []},
                {"title": "关键挑战二：模型方法与推理机制", "children": []},
                {"title": "关键挑战三：评测、泛化与部署", "children": []},
                {"title": "综合讨论与未来展望", "children": []},
                {"title": "参考文献", "children": []},
            ],
        },
    ]


def _is_references_title(title: str) -> bool:
    normalized = title.strip().lower()
    return normalized in {"参考文献", "references", "reference"}


async def _get_outline_templates(session: AsyncSession, selection_set_id: int) -> list[dict]:
    papers = await _get_papers_context(session, selection_set_id)
    papers_json = json.dumps(papers[:30], ensure_ascii=False)
    system = (
        "你是科研写作助手。请根据当前参考文献选择集，为调研报告推荐三种不同风格的目录模板。"
        "每种模板都必须适合学术调研报告，且必须包含最后一级章节“参考文献”。"
        "请输出 JSON 对象，字段 templates，为数组；每项包含 name、description、outline。"
        "outline 为目录树数组，每项格式 {title:string, children:array}。"
    )
    user = (
        "当前选择集论文信息如下（含arXiv ID、标题、摘要）：\n"
        + papers_json
        + "\n\n请给出三种目录模板，分别侧重：\n"
        "1. 经典综述型：适合大多数技术主题；\n"
        "2. 技术路线对比型：适合比较方法差异；\n"
        "3. 问题驱动型：适合围绕核心挑战展开。\n"
        "每个模板的标题要简洁专业，description 不超过 60 字。"
    )
    try:
        data = await chat_complete_json(system=system, user=user, temperature=0.4)
        templates = data.get("templates")
        if not isinstance(templates, list) or len(templates) < 3:
            raise LLMError("模板数量不足")
        normalized: list[dict] = []
        for idx, item in enumerate(templates[:3], start=1):
            if not isinstance(item, dict):
                continue
            outline = item.get("outline")
            if not isinstance(outline, list) or not outline:
                continue
            normalized.append({
                "template_id": idx,
                "name": str(item.get("name") or f"模板 {idx}").strip(),
                "description": str(item.get("description") or "").strip(),
                "outline": outline,
            })
        if len(normalized) >= 3:
            return normalized[:3]
    except LLMError:
        pass
    return [
        {"template_id": idx + 1, **template}
        for idx, template in enumerate(_fallback_outline_templates())
    ]


async def _apply_outline_template(session: AsyncSession, report: Report, template_id: int) -> tuple[list[dict], bool]:
    templates = _fallback_outline_templates()
    template = next((item for i, item in enumerate(templates, start=1) if i == template_id), None)
    if template is None:
        raise HTTPException(status_code=404, detail="Outline template not found")

    outline = template["outline"]
    used_llm = False
    try:
        papers = await _get_papers_context(session, report.selection_set_id)
        system = (
            "你是科研写作助手。请根据给定论文与选定目录模板，细化生成一个适用于调研报告的目录树。"
            "必须保留模板风格，并确保最后包含参考文献章节。仅输出JSON对象，字段 outline。"
        )
        user = json.dumps({"template": template, "papers": papers[:30]}, ensure_ascii=False)
        data = await chat_complete_json(system=system, user=user, temperature=0.25)
        candidate = data.get("outline")
        if isinstance(candidate, list) and candidate:
            outline = candidate
            used_llm = True
    except LLMError:
        pass

    if not any(_is_references_title(str(item.get("title", ""))) for item in outline if isinstance(item, dict)):
        outline.append({"title": "参考文献", "children": []})

    await _replace_outline(session, report, outline)
    papers = await _get_papers_context(session, report.selection_set_id)
    await _ensure_references_section(session, report, papers)
    return outline, used_llm


async def _get_papers_context(session: AsyncSession, selection_set_id: int) -> list[dict]:
    rows = (
        await session.execute(
            select(Paper).join(Selection, Selection.paper_id == Paper.id).where(Selection.selection_set_id == selection_set_id)
        )
    ).scalars().all()

    translations = {
        tr.paper_id: tr
        for tr in (
            await session.execute(select(PaperTranslation).where(PaperTranslation.paper_id.in_([p.id for p in rows])))
        ).scalars().all()
    } if rows else {}

    ctx: list[dict] = []
    for p in rows:
        tr = translations.get(p.id)
        ctx.append(
            {
                "arxiv_id": p.arxiv_id,
                "title": p.title,
                "authors": p.authors,
                "abstract": p.abstract,
                "pdf_url": p.pdf_url,
                "published": p.published,
                "updated": p.updated,
                "title_zh": tr.title_zh if tr else None,
                "abstract_zh": tr.abstract_zh if tr else None,
            }
        )
    return ctx


async def _get_section_generation_context(
    session: AsyncSession,
    selection_set_id: int,
    max_papers: int = 12,
) -> tuple[list[dict], set[str]]:
    rows = (
        await session.execute(
            select(Paper)
            .join(Selection, Selection.paper_id == Paper.id)
            .where(Selection.selection_set_id == selection_set_id)
        )
    ).scalars().all()

    rows = rows[:max_papers]
    allowed = {p.arxiv_id for p in rows}
    paper_ids = [p.id for p in rows]

    translations = {
        tr.paper_id: tr
        for tr in (
            await session.execute(select(PaperTranslation).where(PaperTranslation.paper_id.in_(paper_ids)))
        ).scalars().all()
    } if paper_ids else {}
    assets = {
        asset.paper_id: asset
        for asset in (
            await session.execute(select(PaperAsset).where(PaperAsset.paper_id.in_(paper_ids)))
        ).scalars().all()
    } if paper_ids else {}

    ctx: list[dict] = []
    for p in rows:
        tr = translations.get(p.id)
        asset = assets.get(p.id)
        extracted_preview = None
        if asset and asset.extracted_text_path:
            try:
                extracted_preview = Path(asset.extracted_text_path).read_text(encoding="utf-8")[:2500]
            except Exception:
                extracted_preview = None
        ctx.append(
            {
                "arxiv_id": p.arxiv_id,
                "title": p.title,
                "authors": p.authors,
                "abstract": p.abstract,
                "pdf_url": p.pdf_url,
                "published": p.published,
                "updated": p.updated,
                "title_zh": tr.title_zh if tr else None,
                "abstract_zh": tr.abstract_zh if tr else None,
                "text_preview": extracted_preview,
            }
        )
    return ctx, allowed


async def _replace_outline(session: AsyncSession, report: Report, outline: list[dict]) -> None:
    await session.execute(delete(ReportSection).where(ReportSection.report_id == report.id))
    await session.flush()

    async def insert_nodes(nodes: list[dict], parent_id: int | None):
        for idx, n in enumerate(nodes):
            title = str(n.get("title", "")).strip() or "未命名章节"
            sec = ReportSection(report_id=report.id, parent_id=parent_id, order_index=idx, title=title, content_md="")
            session.add(sec)
            await session.flush()
            children = n.get("children") or []
            if isinstance(children, list) and children:
                await insert_nodes(children, sec.id)

    await insert_nodes(outline, None)


@router.get("/{report_id}/outline/templates")
async def recommend_outline_templates(report_id: int, session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)):
    report = await _require_report_owner(report_id, user, session)
    templates = await _get_outline_templates(session, report.selection_set_id)
    return {"report_id": report.id, "templates": templates}


@router.post("/{report_id}/outline/apply")
async def apply_outline_template(report_id: int, payload: dict, session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)):
    report = await _require_report_owner(report_id, user, session)
    outline = payload.get("outline")
    if not isinstance(outline, list) or not outline:
        raise HTTPException(status_code=400, detail="outline is required")
    if not any(_is_references_title(str(item.get("title", ""))) for item in outline if isinstance(item, dict)):
        outline.append({"title": "参考文献", "children": []})
    try:
        await _replace_outline(session, report, outline)
        papers = await _get_papers_context(session, report.selection_set_id)
        await _ensure_references_section(session, report, papers)
        await session.commit()
    except (OperationalError, IntegrityError) as exc:
        await session.rollback()
        _raise_db_http_error(exc, "应用目录模板")
    sections = (
        await session.execute(
            select(ReportSection).where(ReportSection.report_id == report_id).order_by(ReportSection.parent_id, ReportSection.order_index)
        )
    ).scalars().all()
    return {
        "report_id": report.id,
        "sections": [
            {
                "id": s.id,
                "parent_id": s.parent_id,
                "order_index": s.order_index,
                "title": s.title,
                "content_md": s.content_md,
            }
            for s in sections
        ],
    }


@router.post("/{report_id}/outline/generate")
async def generate_outline(report_id: int, session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)):
    report = await _require_report_owner(report_id, user, session)

    papers = await _get_papers_context(session, report.selection_set_id)

    system = (
        "你是科研写作助手。你要为“前沿进展调研报告”生成一个可编辑的目录树。"
        "要求：中文标题；结构清晰；至少6个一级章节；可包含二级章节；避免虚构论文；最后必须包含一级章节“参考文献”。"
        "仅输出JSON对象，字段：outline(数组)，每项 {title:string, children:array}。"
    )
    user = "已选论文列表如下（含arXiv ID、标题、摘要）：\n" + json.dumps(papers[:30], ensure_ascii=False)

    used_llm = False
    try:
        data = await chat_complete_json(system=system, user=user, temperature=0.2)
        outline = data.get("outline")
        if not isinstance(outline, list):
            outline = _fallback_outline()
        else:
            used_llm = True
    except LLMError:
        outline = _fallback_outline()

    if not any(_is_references_title(str(item.get("title", ""))) for item in outline if isinstance(item, dict)):
        outline.append({"title": "参考文献", "children": []})

    try:
        await _replace_outline(session, report, outline)
        await _ensure_references_section(session, report, papers)
        await session.commit()
    except (OperationalError, IntegrityError) as exc:
        await session.rollback()
        _raise_db_http_error(exc, "生成目录")
    return {"report_id": report.id, "outline": outline, "used_llm": used_llm}


@router.get("/{report_id}/sections")
async def get_sections(report_id: int, session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)):
    await _require_report_owner(report_id, user, session)
    secs = (
        await session.execute(
            select(ReportSection).where(ReportSection.report_id == report_id).order_by(ReportSection.parent_id, ReportSection.order_index)
        )
    ).scalars().all()
    return [
        {
            "id": s.id,
            "parent_id": s.parent_id,
            "order_index": s.order_index,
            "title": s.title,
            "content_md": s.content_md,
        }
        for s in secs
    ]


@router.put("/{report_id}/sections/{section_id}")
async def update_section(report_id: int, section_id: int, payload: dict, session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)):
    await _require_report_owner(report_id, user, session)
    sec = (
        await session.execute(
            select(ReportSection).where(ReportSection.id == section_id, ReportSection.report_id == report_id).limit(1)
        )
    ).scalars().first()
    if sec is None:
        raise HTTPException(status_code=404, detail="Section not found")
    if "title" in payload and isinstance(payload["title"], str):
        sec.title = payload["title"].strip() or sec.title
    if "content_md" in payload and isinstance(payload["content_md"], str):
        sec.content_md = payload["content_md"]
    try:
        await session.commit()
    except (OperationalError, IntegrityError) as exc:
        await session.rollback()
        _raise_db_http_error(exc, "更新章节")
    return {"ok": True}


_CITE_RE = re.compile(r"\[arxiv:([^\]]+)\]")


def _sanitize_citations(md: str, allowed: set[str]) -> str:
    def repl(m: re.Match) -> str:
        arxiv_id = m.group(1).strip()
        return m.group(0) if arxiv_id in allowed else ""

    return _CITE_RE.sub(repl, md)


def _format_reference_item(index: int, paper: dict) -> str:
    authors = str(paper.get("authors") or "").strip()
    title = str(paper.get("title") or "未命名论文").strip()
    arxiv_id = str(paper.get("arxiv_id") or "").strip()
    published = str(paper.get("published") or "").strip()
    pdf_url = str(paper.get("pdf_url") or "").strip()
    parts = [f"[{index}] {authors}." if authors else f"[{index}]", title]
    if published:
        parts.append(f"{published}.")
    if arxiv_id:
        parts.append(f"arXiv:{arxiv_id}.")
    if pdf_url:
        parts.append(pdf_url)
    return " ".join(part for part in parts if part).strip()


def _build_references_content(papers: list[dict]) -> str:
    lines = [
        "以下参考文献均来自当前参考文献选择集。正文中的引用使用 `[arxiv:ID]` 标注，与下列条目对应。",
        "",
    ]
    for idx, paper in enumerate(papers, start=1):
        lines.append(_format_reference_item(idx, paper))
    return "\n".join(lines).strip() + "\n"


async def _ensure_references_section(session: AsyncSession, report: Report, papers: list[dict]) -> ReportSection:
    top_level_sections = (
        await session.execute(
            select(ReportSection).where(ReportSection.report_id == report.id, ReportSection.parent_id.is_(None))
        )
    ).scalars().all()
    refs = next((sec for sec in top_level_sections if _is_references_title(sec.title)), None)
    if refs is None:
        max_order = max((sec.order_index for sec in top_level_sections), default=-1)
        refs = ReportSection(
            report_id=report.id,
            parent_id=None,
            order_index=max_order + 1,
            title="参考文献",
            content_md="",
        )
        session.add(refs)
        await session.flush()
    else:
        refs.title = "参考文献"
    refs.content_md = _build_references_content(papers)
    return refs


async def _generate_section_content_from_context(sec: ReportSection, papers: list[dict], allowed: set[str]) -> str:
    system = (
        "你是科研写作助手。根据给定论文信息，为指定章节写一段中文调研报告内容（Markdown）。"
        "要求：结构化（小标题/要点/对比）；所有事实性判断、方法归纳、性能对比和趋势分析都必须尽量引用给定论文。"
        "正文引用格式严格为 [arxiv:ID]，ID必须来自允许列表；每个核心段落至少包含1个引用。"
        "只能引用给定论文，不要编造未给出的论文、作者、实验结果或结论；不确定时用保守表述。"
        "不要生成参考文献列表，参考文献章节会由系统自动生成。"
    )
    user = (
        f"章节标题：{sec.title}\n"
        f"允许引用的arXiv ID列表：{sorted(list(allowed))}\n\n"
        "论文上下文（含标题/摘要/部分正文预览，可能包含中文翻译字段）：\n"
        + json.dumps(papers, ensure_ascii=False)
        + "\n\n请输出该章节的Markdown正文（不要输出代码块围栏）。"
    )

    try:
        md = await chat_complete_text(system=system, user=user, temperature=0.3)
        md = md.strip()
        if not md:
            raise LLMError("LLM返回空内容")
        return _sanitize_citations(md, allowed)
    except LLMError:
        return (
            f"## {sec.title}\n\n"
            "- 本章可围绕已选论文的主要贡献与技术路线做归纳对比。\n"
            "- 建议从问题定义、核心方法、实验设置与局限性等维度总结，并在观点后使用 [arxiv:ID] 标注对应参考文献。\n"
        )


async def _generate_section_content(report: Report, sec: ReportSection, session: AsyncSession) -> str:
    papers, allowed = await _get_section_generation_context(session, report.selection_set_id)
    return await _generate_section_content_from_context(sec, papers, allowed)


@router.post("/{report_id}/sections/{section_id}/generate")
async def generate_section(report_id: int, section_id: int, session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)):
    report = await _require_report_owner(report_id, user, session)
    sec = (
        await session.execute(
            select(ReportSection).where(ReportSection.id == section_id, ReportSection.report_id == report_id).limit(1)
        )
    ).scalars().first()
    if sec is None:
        raise HTTPException(status_code=404, detail="Section not found")

    papers, allowed = await _get_section_generation_context(session, report.selection_set_id)
    if _is_references_title(sec.title):
        sec.content_md = _build_references_content(papers)
    else:
        sec.content_md = await _generate_section_content_from_context(sec, papers, allowed)
    try:
        await session.commit()
    except (OperationalError, IntegrityError) as exc:
        await session.rollback()
        _raise_db_http_error(exc, "生成章节")
    return {"section_id": sec.id, "content_md": sec.content_md}


@router.post("/{report_id}/generate_all")
async def generate_all(report_id: int, session: AsyncSession = Depends(get_session), user: User = Depends(get_current_user)):
    report = await _require_report_owner(report_id, user, session)

    secs = (
        await session.execute(
            select(ReportSection).where(ReportSection.report_id == report_id).order_by(ReportSection.parent_id, ReportSection.order_index)
        )
    ).scalars().all()

    if not secs:
        try:
            await _replace_outline(session, report, _fallback_outline())
            await session.flush()
            secs = (
                await session.execute(
                    select(ReportSection)
                    .where(ReportSection.report_id == report_id)
                    .order_by(ReportSection.parent_id, ReportSection.order_index)
                )
            ).scalars().all()
        except (OperationalError, IntegrityError) as exc:
            await session.rollback()
            _raise_db_http_error(exc, "初始化报告结构")

    papers, allowed = await _get_section_generation_context(session, report.selection_set_id)
    try:
        await _ensure_references_section(session, report, papers)
        await session.flush()
        secs = (
            await session.execute(
                select(ReportSection)
                .where(ReportSection.report_id == report_id)
                .order_by(ReportSection.parent_id, ReportSection.order_index)
            )
        ).scalars().all()
    except (OperationalError, IntegrityError) as exc:
        await session.rollback()
        _raise_db_http_error(exc, "生成参考文献")

    generation_targets = [sec for sec in secs if not _is_references_title(sec.title)]
    semaphore = asyncio.Semaphore(3)

    async def generate_one(sec: ReportSection) -> tuple[int, str]:
        async with semaphore:
            content = await _generate_section_content_from_context(sec, papers, allowed)
            return sec.id, content

    generated_contents = await asyncio.gather(*(generate_one(sec) for sec in generation_targets))
    content_by_section_id = dict(generated_contents)

    for sec in secs:
        if _is_references_title(sec.title):
            sec.content_md = _build_references_content(papers)
        elif sec.id in content_by_section_id:
            sec.content_md = content_by_section_id[sec.id]

    try:
        await session.commit()
    except (OperationalError, IntegrityError) as exc:
        await session.rollback()
        _raise_db_http_error(exc, "整篇生成")
    return {"ok": True, "count": len(secs)}
