from __future__ import annotations

import re

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth import create_access_token, get_current_user, hash_password, verify_password
from ..db import get_session
from ..models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])

_USERNAME_RE = re.compile(r"^[a-zA-Z0-9_\u4e00-\u9fa5-]{2,32}$")


class AuthRequest(BaseModel):
    username: str = Field(min_length=2, max_length=32)
    password: str = Field(min_length=6, max_length=128)


class AuthResponse(BaseModel):
    token: str
    user: dict


def _normalize_username(username: str) -> str:
    return username.strip()


def _validate_username(username: str) -> None:
    if not _USERNAME_RE.match(username):
        raise HTTPException(status_code=400, detail="用户名只能包含中文、字母、数字、下划线或短横线，长度 2-32")


@router.post("/register", response_model=AuthResponse)
async def register(payload: AuthRequest, session: AsyncSession = Depends(get_session)):
    username = _normalize_username(payload.username)
    _validate_username(username)
    exists = (await session.execute(select(User.id).where(User.username == username).limit(1))).scalars().first()
    if exists is not None:
        raise HTTPException(status_code=409, detail="用户名已存在")

    user = User(username=username, password_hash=hash_password(payload.password))
    session.add(user)
    try:
        await session.commit()
        await session.refresh(user)
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="用户名已存在") from exc
    return {"token": create_access_token(user), "user": {"id": user.id, "username": user.username}}


@router.post("/login", response_model=AuthResponse)
async def login(payload: AuthRequest, session: AsyncSession = Depends(get_session)):
    username = _normalize_username(payload.username)
    user = (await session.execute(select(User).where(User.username == username).limit(1))).scalars().first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    return {"token": create_access_token(user), "user": {"id": user.id, "username": user.username}}


@router.get("/me")
async def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "username": user.username}
