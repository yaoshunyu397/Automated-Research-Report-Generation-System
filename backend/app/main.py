from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .api import arxiv, auth, export, papers, reports, stats, tasks, translate
from .db import ensure_auth_schema, engine
from .models import Base
from .services.storage import ensure_dirs
from .settings import settings


app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await ensure_auth_schema()
    ensure_dirs()


@app.get("/api/health")
async def health():
    database_ok = False
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        database_ok = True
    except Exception:
        database_ok = False

    storage_path = Path(settings.storage_root)
    storage_ok = storage_path.exists() and storage_path.is_dir()
    return {
        "ok": database_ok and storage_ok,
        "database": "ok" if database_ok else "error",
        "storage": {
            "ok": storage_ok,
            "root": str(storage_path),
        },
        "arxiv": {
            "timeout_seconds": settings.arxiv_timeout_seconds,
            "proxy_configured": bool(settings.arxiv_proxy.strip()),
        },
        "llm": {
            "configured": bool(settings.llm_api_key.strip()),
            "model": settings.llm_model,
        },
        "translation": {
            "provider": settings.translation_provider,
            "fallback_to_llm": settings.translation_fallback_to_llm,
            "volcengine_configured": bool(settings.volc_access_key_id and settings.volc_secret_access_key),
        },
    }


app.include_router(auth.router)
app.include_router(arxiv.router)
app.include_router(papers.router)
app.include_router(tasks.router)
app.include_router(reports.router)
app.include_router(translate.router)
app.include_router(export.router)
app.include_router(stats.router)
