from __future__ import annotations

from pathlib import Path

from ..settings import settings


def _storage_root() -> Path:
    return Path(settings.storage_root).expanduser().resolve()


DATA_DIR = _storage_root()
PAPERS_DIR = DATA_DIR / "papers"
TEXT_DIR = DATA_DIR / "text"
REPORTS_DIR = DATA_DIR / "reports"
TRANSLATIONS_DIR = DATA_DIR / "translations"


def ensure_dirs() -> None:
    PAPERS_DIR.mkdir(parents=True, exist_ok=True)
    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    TRANSLATIONS_DIR.mkdir(parents=True, exist_ok=True)


def paper_pdf_path(arxiv_id: str) -> Path:
    return PAPERS_DIR / f"{arxiv_id}.pdf"


def paper_text_path(arxiv_id: str) -> Path:
    return TEXT_DIR / f"{arxiv_id}.txt"


def paper_translation_path(arxiv_id: str) -> Path:
    return TRANSLATIONS_DIR / f"{arxiv_id}.md"
