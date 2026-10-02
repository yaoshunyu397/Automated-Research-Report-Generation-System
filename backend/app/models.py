from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    selection_sets: Mapped[list["SelectionSet"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Paper(Base):
    __tablename__ = "papers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    arxiv_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(Text)
    authors: Mapped[str] = mapped_column(Text)
    abstract: Mapped[str] = mapped_column(Text)
    pdf_url: Mapped[str] = mapped_column(Text)
    published: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    updated: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    selections: Mapped[list["Selection"]] = relationship(back_populates="paper", cascade="all, delete-orphan")
    asset: Mapped[Optional["PaperAsset"]] = relationship(back_populates="paper", cascade="all, delete-orphan")


class SelectionSet(Base):
    __tablename__ = "selection_sets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=True)
    name: Mapped[str] = mapped_column(String(128), default="default")
    query: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[Optional["User"]] = relationship(back_populates="selection_sets")
    selections: Mapped[list["Selection"]] = relationship(back_populates="selection_set", cascade="all, delete-orphan")


class Selection(Base):
    __tablename__ = "selections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    selection_set_id: Mapped[int] = mapped_column(ForeignKey("selection_sets.id", ondelete="CASCADE"), index=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"), index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    selection_set: Mapped["SelectionSet"] = relationship(back_populates="selections")
    paper: Mapped["Paper"] = relationship(back_populates="selections")


class PaperAsset(Base):
    __tablename__ = "paper_assets"
    __table_args__ = (UniqueConstraint("paper_id", name="uq_paper_assets_paper_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"), index=True)

    pdf_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extracted_text_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    paper: Mapped["Paper"] = relationship(back_populates="asset")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    selection_set_id: Mapped[int] = mapped_column(ForeignKey("selection_sets.id", ondelete="CASCADE"), index=True)

    status: Mapped[str] = mapped_column(String(32), default="pending")
    step: Mapped[str] = mapped_column(String(32), default="created")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class PaperTranslation(Base):
    __tablename__ = "paper_translations"
    __table_args__ = (UniqueConstraint("paper_id", name="uq_paper_translations_paper_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id", ondelete="CASCADE"), index=True)

    title_zh: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    abstract_zh: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    selection_set_id: Mapped[int] = mapped_column(ForeignKey("selection_sets.id", ondelete="CASCADE"), index=True)

    title: Mapped[str] = mapped_column(Text, default="调研报告")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class ReportSection(Base):
    __tablename__ = "report_sections"
    __table_args__ = (UniqueConstraint("report_id", "parent_id", "order_index", name="uq_report_section_order"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), index=True)
    parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("report_sections.id", ondelete="CASCADE"), nullable=True)

    order_index: Mapped[int] = mapped_column(Integer, default=0)
    title: Mapped[str] = mapped_column(Text)
    content_md: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
