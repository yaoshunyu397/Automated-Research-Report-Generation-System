from __future__ import annotations

from pathlib import Path

from pdfminer.high_level import extract_text


def extract_pdf_text(pdf_path: Path) -> str:
    # pdfminer is slower but pure-Python and works on Windows without large wheels.
    return extract_text(str(pdf_path))

