from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from .settings import settings

engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
    connect_args={"timeout": 30},
)


@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.close()


SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


async def ensure_auth_schema() -> None:
    async with engine.begin() as conn:
        result = await conn.execute(text("PRAGMA table_info(selection_sets)"))
        columns = {row[1] for row in result.fetchall()}
        if "user_id" not in columns:
            await conn.execute(text("ALTER TABLE selection_sets ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE CASCADE"))
