from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_session
from .models import User
from .settings import settings

security = HTTPBearer(auto_error=False)

_TOKEN_TTL = timedelta(days=7)
_ITERATIONS = 260_000


def _secret() -> str:
    return settings.secret_key or "survey2-local-dev-secret"


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), _ITERATIONS).hex()
    return f"pbkdf2_sha256${_ITERATIONS}${salt}${digest}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations, salt, expected = password_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iterations)).hex()
        return hmac.compare_digest(digest, expected)
    except Exception:
        return False


def create_access_token(user: User) -> str:
    exp = int((datetime.now(timezone.utc) + _TOKEN_TTL).timestamp())
    payload = f"{user.id}:{user.username}:{exp}"
    signature = hmac.new(_secret().encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{payload}:{signature}"


def parse_access_token(token: str) -> dict[str, Any] | None:
    parts = token.split(":")
    if len(parts) != 4:
        return None
    user_id, username, exp_text, signature = parts
    payload = f"{user_id}:{username}:{exp_text}"
    expected = hmac.new(_secret().encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        exp = int(exp_text)
        if exp < int(datetime.now(timezone.utc).timestamp()):
            return None
        return {"user_id": int(user_id), "username": username}
    except ValueError:
        return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    session: AsyncSession = Depends(get_session),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="请先登录")
    payload = parse_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录已失效，请重新登录")
    user = (await session.execute(select(User).where(User.id == payload["user_id"]).limit(1))).scalars().first()
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在，请重新登录")
    return user
