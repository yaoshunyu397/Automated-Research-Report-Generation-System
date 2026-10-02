from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ArxivSearchItem(BaseModel):
    arxiv_id: str
    title: str
    authors: list[str]
    abstract: str
    pdf_url: str
    published: Optional[str] = None
    updated: Optional[str] = None


class ArxivSearchResponse(BaseModel):
    query: str
    total: int
    items: list[ArxivSearchItem]


class SelectPapersRequest(BaseModel):
    name: str = Field(default="default", description="Selection set name")
    query: Optional[str] = Field(default=None, description="Search keyword used when saving this selection set")
    items: list[ArxivSearchItem] = Field(default_factory=list)
    arxiv_ids: list[str] = Field(default_factory=list, description="兼容旧格式：仅传arXiv IDs")


class SelectionSetResponse(BaseModel):
    selection_set_id: int
    name: str
    count: int
    query: Optional[str] = None


class CreateTaskRequest(BaseModel):
    selection_set_id: int


class TaskResponse(BaseModel):
    task_id: int
    selection_set_id: int
    status: str
    step: str
    progress: int
    message: Optional[str] = None

