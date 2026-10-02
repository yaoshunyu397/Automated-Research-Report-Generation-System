from __future__ import annotations

import re


_MULTI_SPACE = re.compile(r"[ \t]{2,}")
_MULTI_NL = re.compile(r"\n{3,}")
_HYPHEN_NL = re.compile(r"(\w)-\n(\w)")


def clean_text(text: str) -> str:
    t = text.replace("\r\n", "\n").replace("\r", "\n")
    t = _HYPHEN_NL.sub(r"\1\2", t)
    t = _MULTI_SPACE.sub(" ", t)
    t = _MULTI_NL.sub("\n\n", t)
    return t.strip()


def chunk_text(text: str, max_chars: int = 1500) -> list[str]:
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    buf: list[str] = []
    cur = 0
    for p in paras:
        if cur + len(p) + (2 if buf else 0) > max_chars and buf:
            chunks.append("\n\n".join(buf).strip())
            buf = []
            cur = 0
        buf.append(p)
        cur += len(p) + (2 if buf else 0)
    if buf:
        chunks.append("\n\n".join(buf).strip())
    return chunks

