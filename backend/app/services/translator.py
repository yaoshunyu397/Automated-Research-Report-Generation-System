from __future__ import annotations

import asyncio
import json
from typing import Any

from ..settings import settings
from .llm import LLMError, chat_complete_text
from .text_clean import chunk_text


class TranslationError(RuntimeError):
    pass


def _clean_texts(texts: list[str]) -> list[str]:
    return [text if isinstance(text, str) else str(text) for text in texts]


async def _llm_translate_text(text: str) -> str:
    if not text.strip():
        return ""
    system = (
        "你是学术翻译助手。请把英文内容准确翻译为中文，保持术语准确和学术书面风格。"
        "直接输出中文译文，不要输出代码块，不要添加解释。"
    )
    user = f"请翻译以下英文内容：\n\n{text}"
    return (await chat_complete_text(system=system, user=user, temperature=0.1)).strip()


async def _llm_translate_texts(texts: list[str]) -> list[str]:
    results: list[str] = []
    for text in texts:
        results.append(await _llm_translate_text(text))
    return results


def _get_volc_service() -> Any:
    try:
        from volcengine.ApiInfo import ApiInfo
        from volcengine.Credentials import Credentials
        from volcengine.ServiceInfo import ServiceInfo
        from volcengine.base.Service import Service
    except ImportError as exc:
        raise TranslationError("volcengine-python-sdk 未安装，请先安装依赖") from exc

    if not settings.volc_access_key_id or not settings.volc_secret_access_key:
        raise TranslationError("火山翻译 AccessKey 未配置")

    service_info = ServiceInfo(
        "open.volcengineapi.com",
        {"Content-Type": "application/json"},
        Credentials(
            settings.volc_access_key_id,
            settings.volc_secret_access_key,
            "translate",
            settings.volc_region,
        ),
        10,
        60,
    )
    api_info = {
        "TranslateText": ApiInfo(
            "POST",
            "/",
            {"Action": "TranslateText", "Version": "2020-06-01"},
            {},
            {},
        )
    }
    return Service(service_info, api_info)


def _extract_volc_translations(data: Any, expected_count: int) -> list[str]:
    if isinstance(data, (bytes, bytearray)):
        data = json.loads(data.decode("utf-8"))
    elif isinstance(data, str):
        data = json.loads(data)

    if not isinstance(data, dict):
        raise TranslationError("火山翻译响应格式错误")

    metadata = data.get("ResponseMetadata")
    if isinstance(metadata, dict) and metadata.get("Error"):
        error = metadata.get("Error") or {}
        message = error.get("Message") if isinstance(error, dict) else str(error)
        raise TranslationError(f"火山翻译失败：{message}")

    items = data.get("TranslationList") or data.get("Translations") or data.get("translation_list")
    if not isinstance(items, list):
        raise TranslationError(f"火山翻译响应缺少 TranslationList：{str(data)[:300]}")

    translations: list[str] = []
    for item in items:
        if isinstance(item, dict):
            translations.append(str(item.get("Translation") or item.get("translation") or item.get("TranslatedText") or "").strip())
        else:
            translations.append(str(item).strip())

    if len(translations) != expected_count:
        raise TranslationError(f"火山翻译返回数量不一致：期望 {expected_count}，实际 {len(translations)}")
    return translations


def _volc_translate_texts_sync(texts: list[str]) -> list[str]:
    service = _get_volc_service()
    body = {
        "SourceLanguage": settings.volc_translate_source_language,
        "TargetLanguage": settings.volc_translate_target_language,
        "TextList": texts,
    }
    try:
        response = service.json("TranslateText", {}, json.dumps(body, ensure_ascii=False))
    except TypeError:
        response = service.json("TranslateText", {}, body)
    except Exception as exc:
        raise TranslationError(f"火山翻译请求失败：{exc}") from exc
    return _extract_volc_translations(response, len(texts))


async def _volc_translate_texts(texts: list[str]) -> list[str]:
    return await asyncio.to_thread(_volc_translate_texts_sync, texts)


def _batch_texts(texts: list[str], max_chars: int) -> list[list[str]]:
    batches: list[list[str]] = []
    current: list[str] = []
    current_chars = 0
    for text in texts:
        text_len = len(text)
        if current and current_chars + text_len > max_chars:
            batches.append(current)
            current = []
            current_chars = 0
        current.append(text)
        current_chars += text_len
    if current:
        batches.append(current)
    return batches


async def translate_texts(texts: list[str]) -> list[str]:
    cleaned = _clean_texts(texts)
    if not cleaned:
        return []

    provider = settings.translation_provider.strip().lower()
    if provider == "volcengine":
        try:
            results: list[str] = []
            for batch in _batch_texts(cleaned, settings.volc_translate_max_chars):
                results.extend(await _volc_translate_texts(batch))
            return results
        except TranslationError:
            if not settings.translation_fallback_to_llm:
                raise
        except Exception as exc:
            if not settings.translation_fallback_to_llm:
                raise TranslationError(f"火山翻译异常：{exc}") from exc

    try:
        return await _llm_translate_texts(cleaned)
    except LLMError as exc:
        raise TranslationError(str(exc)) from exc


async def translate_text(text: str) -> str:
    return (await translate_texts([text]))[0]


async def translate_long_text(text: str, *, max_chars: int | None = None, concurrency: int | None = None) -> str:
    chunks = chunk_text(text, max_chars=max_chars or settings.volc_translate_max_chars)
    if not chunks:
        return ""

    sem = asyncio.Semaphore(concurrency or settings.volc_translate_concurrency)

    async def translate_chunk(chunk: str) -> str:
        async with sem:
            return await translate_text(chunk)

    translated = await asyncio.gather(*(translate_chunk(chunk) for chunk in chunks))
    return "\n\n".join(part.strip() for part in translated if part.strip())
