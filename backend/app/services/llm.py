from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional

import httpx

from ..settings import settings


@dataclass(frozen=True)
class LLMConfig:
    base_url: str
    api_key: str
    model: str


def get_llm_config() -> LLMConfig:
    return LLMConfig(base_url=settings.llm_base_url.rstrip("/"), api_key=settings.llm_api_key, model=settings.llm_model)


class LLMError(RuntimeError):
    pass


async def chat_complete_json(system: str, user: str, *, temperature: float = 0.2) -> Any:
    cfg = get_llm_config()
    if not cfg.api_key:
        raise LLMError("LLM_API_KEY 未配置")

    url = f"{cfg.base_url}/chat/completions"
    headers = {"Authorization": f"Bearer {cfg.api_key}"}
    payload = {
        "model": cfg.model,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "response_format": {"type": "json_object"},
    }

    async with httpx.AsyncClient(timeout=90.0) as client:
        r = await client.post(url, headers=headers, json=payload)
        if r.status_code >= 400:
            raise LLMError(f"LLM HTTP {r.status_code}: {r.text[:500]}")
        data = r.json()

    try:
        content = data["choices"][0]["message"]["content"]
    except Exception as e:
        raise LLMError(f"LLM响应解析失败: {e}") from e

    try:
        return json.loads(content)
    except Exception as e:
        raise LLMError(f"LLM未返回有效JSON: {e}; content={content[:500]}") from e


async def chat_complete_text(system: str, user: str, *, temperature: float = 0.2) -> str:
    cfg = get_llm_config()
    if not cfg.api_key:
        raise LLMError("LLM_API_KEY 未配置")

    url = f"{cfg.base_url}/chat/completions"
    headers = {"Authorization": f"Bearer {cfg.api_key}"}
    payload = {
        "model": cfg.model,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }

    async with httpx.AsyncClient(timeout=90.0) as client:
        r = await client.post(url, headers=headers, json=payload)
        if r.status_code >= 400:
            raise LLMError(f"LLM HTTP {r.status_code}: {r.text[:500]}")
        data = r.json()

    try:
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        raise LLMError(f"LLM响应解析失败: {e}") from e

